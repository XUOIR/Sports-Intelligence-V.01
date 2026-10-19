"""Explicit, bounded historical goalie downloads for offline research only.

Published MoneyPuck game-by-game ZIPs; no page scraping, paid requests,
redirects or retries. Every URL has one durable admission, including failures.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request

MAX_BYTES = 2_000_000
MAX_TOTAL = 24_000_000
MAX_ATTEMPTS = 11
BASE = 'https://peter-tanner.com/moneypuck/downloads/seasonPlayersSummary/goalies/'


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('Historical download redirect rejected')


def acquire(directory, season, opener=None):
    if type(season) is not int or not 2015 <= season <= 2025:
        raise ValueError('Only declared completed research seasons are allowed')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{season}.zip'
    url = BASE + f'{season}.zip'
    with closing(sqlite3.connect(directory / 'admission.sqlite3', timeout=10)) as conn:
        with conn:
            conn.execute('CREATE TABLE IF NOT EXISTS attempt (season INTEGER PRIMARY KEY, url TEXT NOT NULL, observed_at TEXT NOT NULL, status TEXT NOT NULL, bytes INTEGER NOT NULL, sha256 TEXT, category TEXT)')
        conn.execute('BEGIN IMMEDIATE')
        prior = conn.execute('SELECT status,bytes,sha256 FROM attempt WHERE season=?', (season,)).fetchone()
        if prior:
            conn.commit()
            if prior[0] != 'SUCCEEDED':
                raise ValueError('This source was already attempted; inspect the failure, no automatic retry')
            raw = target.read_bytes()
            if len(raw) != prior[1] or hashlib.sha256(raw).hexdigest() != prior[2]:
                raise ValueError('Saved historical archive integrity mismatch')
            return {'season':season, 'bytes':len(raw), 'sha256':prior[2], 'cache_hit':True}
        count, used = conn.execute('SELECT count(*),coalesce(sum(bytes),0) FROM attempt').fetchone()
        if count >= MAX_ATTEMPTS or used + MAX_BYTES > MAX_TOTAL:
            raise ValueError('Historical acquisition allowance exhausted')
        conn.execute('INSERT INTO attempt VALUES(?,?,?,?,?,?,?)',
            (season,url,datetime.now(timezone.utc).isoformat(),'STARTED',MAX_BYTES,None,None))
        conn.commit()
    try:
        request = urllib.request.Request(url, headers={
            'User-Agent':'GSportsIntelligence/0.1 (bounded historical research)',
            'Accept-Encoding':'identity'})
        active = opener or urllib.request.build_opener(NoRedirects())
        with active.open(request, timeout=25) as response:
            length = response.headers.get('Content-Length')
            if (response.status != 200 or response.headers.get('Content-Encoding','identity') != 'identity'
                    or length and (not length.isdigit() or int(length) > MAX_BYTES)):
                raise ValueError('Historical archive response rejected')
            raw = response.read(MAX_BYTES + 1)
        if not raw.startswith(b'PK\x03\x04') or len(raw) > MAX_BYTES or length and len(raw) != int(length):
            raise ValueError('Historical archive is incomplete or exceeds its allowance')
        digest = hashlib.sha256(raw).hexdigest()
        with target.open('xb') as handle:
            handle.write(raw)
        with closing(sqlite3.connect(directory / 'admission.sqlite3')) as conn, conn:
            conn.execute("UPDATE attempt SET status='SUCCEEDED',bytes=?,sha256=? WHERE season=?", (len(raw),digest,season))
        return {'season':season,'bytes':len(raw),'sha256':digest,'cache_hit':False}
    except BaseException as exc:
        with closing(sqlite3.connect(directory / 'admission.sqlite3')) as conn, conn:
            conn.execute("UPDATE attempt SET status='FAILED',category=? WHERE season=?", (type(exc).__name__,season))
        raise ValueError('Historical download did not complete; reservation retained, no automatic retry') from None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--season', required=True, type=int)
    args = parser.parse_args()
    print(json.dumps(acquire(args.directory,args.season)))
