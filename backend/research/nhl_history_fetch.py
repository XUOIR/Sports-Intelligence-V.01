"""Explicit, small acquisition budget for public NHL historical results.

Separate from model fitting and production. No keys, paid hosts, retries,
redirects, application settings, production database, or background polling.
Every attempted URL consumes a durable admission, including failed requests.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.parse
import urllib.request

BASE = 'https://api.nhle.com/stats/rest/en/'
MAX_ATTEMPTS = 10
MAX_BYTES = 12_000_000
MAX_TOTAL_BYTES = 48_000_000
ROUTES = {'game', 'game/meta', 'team'}


@contextmanager
def ledger(directory):
    conn = sqlite3.connect(Path(directory) / 'admission.sqlite3', timeout=10)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Historical collector does not follow redirects')


def acquire(directory, route, query, opener=None):
    if route not in ROUTES:
        raise ValueError('Only fixed public NHL historical routes are permitted')
    if not isinstance(query, dict) or any(not isinstance(k, str) or not isinstance(v, (int, str)) for k, v in query.items()):
        raise ValueError('Invalid public query')
    url = BASE + route + ('?' + urllib.parse.urlencode(sorted(query.items())) if query else '')
    key = hashlib.sha256(url.encode()).hexdigest()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (key + '.json')
    with ledger(directory) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS attempt (id TEXT PRIMARY KEY, url TEXT NOT NULL, at TEXT NOT NULL, status TEXT NOT NULL, bytes INTEGER NOT NULL DEFAULT 0, sha256 TEXT, error TEXT)')
        conn.execute('BEGIN IMMEDIATE')
        previous = conn.execute('SELECT status, bytes, sha256 FROM attempt WHERE id=?', (key,)).fetchone()
        if previous:
            conn.commit()
            if previous[0] != 'SUCCEEDED':
                raise ValueError('This URL was already attempted; inspect the ledger, no automatic retry')
            raw = target.read_bytes()
            if len(raw) != previous[1] or hashlib.sha256(raw).hexdigest() != previous[2]:
                raise ValueError('Cached source hash/length mismatch')
            return json.loads(raw), {'url': url, 'cache_hit': True, 'path': str(target), 'sha256': previous[2], 'bytes': len(raw)}
        attempts, total = conn.execute('SELECT COUNT(*), COALESCE(SUM(bytes),0) FROM attempt').fetchone()
        if attempts >= MAX_ATTEMPTS or total + MAX_BYTES > MAX_TOTAL_BYTES:
            raise ValueError('Offline historical acquisition budget exhausted')
        # Reserve before any network access. A crash is an uncertain attempt,
        # which remains consumed and cannot silently be retried.
        conn.execute('INSERT INTO attempt(id,url,at,status,bytes) VALUES(?,?,?,?,?)', (key, url, utc_now(), 'STARTED', MAX_BYTES))
        conn.commit()
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Sports-Intelligence-NHL-Research/0.1 (bounded historical study)', 'Accept': 'application/json', 'Accept-Encoding': 'identity'})
        active_opener = opener or urllib.request.build_opener(NoRedirects())
        with active_opener.open(request, timeout=25) as response:
            if response.status != 200:
                raise ValueError('Unexpected historical response status')
            length = response.headers.get('Content-Length')
            if length and int(length) > MAX_BYTES:
                raise ValueError('Historical source exceeds byte cap')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Historical source exceeds byte cap')
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
            raise ValueError('Unexpected historical JSON contract')
        digest = hashlib.sha256(raw).hexdigest()
        # Exclusive write prevents a concurrent/accidental source overwrite.
        with target.open('xb') as handle:
            handle.write(raw)
        with ledger(directory) as conn:
            conn.execute('UPDATE attempt SET status=?, bytes=?, sha256=? WHERE id=?', ('SUCCEEDED', len(raw), digest, key))
        return payload, {'url': url, 'cache_hit': False, 'path': str(target), 'sha256': digest, 'bytes': len(raw), 'observed_at': utc_now()}
    except Exception as exc:
        with ledger(directory) as conn:
            conn.execute('UPDATE attempt SET status=?, error=? WHERE id=?', ('FAILED', str(exc)[:200], key))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--route', choices=sorted(ROUTES), default='game')
    parser.add_argument('--query', default='{}', help='Public JSON query parameters only')
    args = parser.parse_args()
    payload, meta = acquire(args.cache, args.route, json.loads(args.query))
    print(json.dumps({'source': meta, 'total': payload.get('total'), 'rows': len(payload['data']), 'first_two_rows': payload['data'][:2]}, indent=2))


if __name__ == '__main__':
    main()
