"""Bounded public-source response metadata. No body reads or network calls."""
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
import re

PUBLIC_HOSTS = {'moneypuck.com', 'www.moneypuck.com', 'peter-tanner.com', 'www.peter-tanner.com'}
PUBLIC_PATHS = {'/', '/data.htm', '/moneypuck/playerData/careers/gameByGame/all_teams.csv',
                '/moneypuck/downloads/seasonPlayersSummary/goalies/2026.zip'}


class SourceResponseError(ValueError):
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def public_date(value):
    try:
        if not value or len(value) > 80:
            return None
        parsed = parsedate_to_datetime(value)
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def redirect_destination(value, source_url):
    # Only known public origins and exact dataset/page paths can be retained.
    # Arbitrary paths, hostnames, user info, query strings and fragments can
    # contain credentials/challenge tokens. Never persist them or follow them.
    result = {'classification': 'unrecognized_destination', 'origin': None, 'path': None,
              'details_withheld': True}
    if not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
        return result
    try:
        url = urlsplit(urljoin(source_url or '', value))
        if url.hostname not in PUBLIC_HOSTS or url.scheme not in {'https', 'http'} or url.port not in {None,80,443}:
            return result
        result['origin'] = f'{url.scheme}://{url.hostname}'
        result['classification'] = 'public_source_redirect' if url.scheme == 'https' else 'insecure_redirect'
        if url.path in PUBLIC_PATHS:
            result['path'] = url.path
        result['details_withheld'] = bool(url.username or url.password or url.query or url.fragment
                                          or result['path'] is None or url.port is not None)
        return result
    except (ValueError, TypeError):
        return result


def response_metadata(response, *, source_url=None):
    headers = response.headers
    code = response.status_code
    kind = ('redirect' if 300 <= code < 400 else 'access_denied' if code == 403 else
            'rate_limited' if code == 429 else 'server_error' if code >= 500 else
            'success' if code == 200 else 'http_error')
    server = headers.get('server', '').lower()
    family = next((name for name in ('cloudflare','cloudfront','openresty','nginx','apache')
                   if server == name or server.startswith(name+'/')), 'other' if server else 'not_reported')
    encoding = headers.get('content-encoding', 'identity').lower()
    length = headers.get('content-length', '')
    content_type = headers.get('content-type', '').split(';')[0].lower().strip()
    result = {'http_status': code, 'response_kind': kind, 'server_family': family,
              'content_type': content_type if content_type in {'text/html','text/csv','application/zip',
                  'application/gzip','application/octet-stream','text/plain'} else 'other',
              'encoding': encoding if encoding in {'gzip','identity','br','deflate'} else 'unrecognized',
              'content_length': length if length.isascii() and length.isdigit() and len(length) <= 12 else None,
              'last_modified': public_date(headers.get('last-modified')),
              'response_date': public_date(headers.get('date')),
              'challenge_reported': headers.get('cf-mitigated') == 'challenge'}
    ray = headers.get('cf-ray', '')
    if re.fullmatch(r'[a-fA-F0-9]{16,32}-[A-Z]{3}', ray):
        result['edge_reference'] = ray
    retry = headers.get('retry-after', '')
    if retry.isascii() and retry.isdigit() and len(retry) <= 5 and int(retry) <= 86400:
        result['retry_after_seconds'] = int(retry)
    if 300 <= code < 400:
        result['redirect'] = redirect_destination(headers.get('location'), source_url)
    return result
