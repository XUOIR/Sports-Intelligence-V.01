"""Extract factual goalie reports from public HTML, without executing scripts.

No network, article prose, rankings, odds, images, or confirmation grants.
"""
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
import ipaddress
import json
import re
import unicodedata

from .clock import aware

CONTRACT = 'dfo-public-goalie-report-v1'
ORIGIN = 'https://www.dailyfaceoff.com'
MAX_HTML = 2_000_000


class SourceFormatError(ValueError):
    pass


def page_url(day):
    return f'{ORIGIN}/starting-goalies/{date.fromisoformat(str(day))}'


def canonical(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower())


def label(value, maximum=160):
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= maximum or any(ord(c) < 32 for c in value):
        raise SourceFormatError('Source name is missing or malformed')
    return value.strip()


def reporter_url(value):
    if not value:
        return None
    try:
        if not isinstance(value, str) or len(value) > 1000 or any(ord(c) < 33 for c in value):
            raise ValueError()
        url = urlsplit(value)
        host = url.hostname or ''
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443) or '.' not in host:
            raise ValueError()
        if host.endswith(('.local', '.internal', '.localhost')):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        # Original reporter links are references only, never fetched. Drop
        # tracking queries/fragments rather than retaining arbitrary tokens.
        return urlunsplit(('https', host, url.path or '/', '', ''))
    except (ValueError, TypeError):
        raise SourceFormatError('Reporter link is not a public HTTPS reference') from None


def robots_allowed(body, url):
    """Most-specific agent/path rules, with Allow winning an equal-length tie."""
    groups, agents, rules = [], [], []
    text = body.decode('utf-8', errors='strict')
    for line in text.splitlines()+['User-agent: __end__']:
        key, separator, value = line.split('#', 1)[0].partition(':')
        if not separator:
            continue
        key, value = key.strip().lower(), value.strip()
        if key == 'user-agent':
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.casefold())
        elif key in {'allow', 'disallow', 'crawl-delay', 'request-rate'} and agents:
            rules.append((key, value))
    applicable = []
    for group_agents, group_rules in groups:
        matches = [len(a) if a != '*' else 0 for a in group_agents if a == '*' or a in 'gsportsintelligence']
        if matches:
            applicable.append((max(matches), group_rules))
    if not applicable:
        return True
    specificity = max(score for score, _ in applicable)
    selected = [rule for score, group in applicable if score == specificity for rule in group]
    decisions = []
    path = urlsplit(url).path
    for key, value in selected:
        if key == 'crawl-delay':
            if not re.fullmatch(r'\d+(?:\.\d+)?', value) or float(value) > 600:
                raise SourceFormatError('Source crawl delay requires a slower collection policy')
        elif key == 'request-rate':
            if not re.fullmatch(r'\d+/\d+', value):
                raise SourceFormatError('Source request-rate policy requires review')
            count, seconds = map(int, value.split('/'))
            if count <= 0 or seconds/count > 600:
                raise SourceFormatError('Source request rate requires a slower collection policy')
        elif value:
            if len(value) > 1000 or value.count('*') > 8:
                raise SourceFormatError('Source crawler rule exceeds the supported bounds')
            anchored = value.endswith('$')
            pattern = value[:-1] if anchored else value
            expression = '^'+re.escape(pattern).replace(r'\*', '.*')+('$' if anchored else '')
            if re.match(expression, path):
                decisions.append((len(pattern.replace('*', '')), key == 'allow'))
    return max(decisions)[1] if decisions else True


class EmbeddedPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.found = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.active = dict(attrs).get('id') == '__NEXT_DATA__'
            self.found += int(self.active)

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False


def parse_page(body, day, observed):
    """Validate the entire page before returning any reports; no zero filling."""
    day = date.fromisoformat(str(day))
    observed = aware(observed)
    if len(body) > MAX_HTML:
        raise SourceFormatError('Public page exceeds its decoded size limit')
    try:
        parser = EmbeddedPage()
        parser.feed(body.decode('utf-8', errors='strict'))
        if parser.found != 1:
            raise SourceFormatError('Public page data structure changed')
        payload = json.loads(''.join(parser.parts))
        props = payload['props']['pageProps']
        rows = props['data']
        if payload['page'] != '/starting-goalies/[[...date]]' or props['date'] != str(day):
            raise SourceFormatError('Source page date or route differs from the requested date')
        if not isinstance(rows, list) or len(rows) > 32:
            raise SourceFormatError('Source game list changed')
        result = []
        identities = set()
        for row in rows:
            start = aware(row['dateGmt'])
            if row['date'] != str(day) or abs((start.date()-day).days) > 1:
                raise SourceFormatError('Source game date changed')
            teams = {side: label(row[side+'TeamName']) for side in ('home', 'away')}
            identity = (canonical(teams['home']), canonical(teams['away']), start.isoformat())
            if identity in identities or identity[0] == identity[1]:
                raise SourceFormatError('Duplicate or ambiguous source game')
            identities.add(identity)
            sides = {}
            for side in ('home', 'away'):
                raw_status = row.get(side+'NewsStrengthName')
                status = {'Confirmed': 'confirmed', 'Expected': 'expected', 'Likely': 'expected',
                          'Unconfirmed': 'unconfirmed', None: 'unconfirmed'}.get(raw_status, 'unknown')
                name = label(row[side+'GoalieName'], 100) if row.get(side+'GoalieName') else None
                published = aware(row[side+'NewsCreatedAt']) if row.get(side+'NewsCreatedAt') else None
                url = reporter_url(row.get(side+'NewsSourceUrl'))
                if published and published > observed:
                    raise SourceFormatError('Source report time is in the future')
                if status == 'confirmed' and not all((name, published, url)):
                    raise SourceFormatError('Confirmed report lacks its named goalie, time or source')
                sides[side] = {'name': name, 'reported_status': status,
                    'reported_at': published.isoformat() if published else None, 'reporter_url': url}
            result.append({'home': teams['home'], 'away': teams['away'], 'start_at': start.isoformat(), 'sides': sides})
        return {'contract': CONTRACT, 'date': str(day), 'games': result}
    except SourceFormatError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        raise SourceFormatError('Public goalie page schema changed') from None
