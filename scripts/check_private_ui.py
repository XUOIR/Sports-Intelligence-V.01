"""Verify local production login boundaries without real keys or wagers."""
import hashlib,hmac,time
import httpx

base='http://127.0.0.1:3000'
with httpx.Client(base_url=base,follow_redirects=False,timeout=10) as client:
    for path in ('/','/settings','/development'):
        result=client.get(path)
        assert result.status_code==307 and result.headers['location']=='/login',path
        assert 'BANKROLL / CAD' not in result.text and 'match-feed-teams' not in result.text
    assert client.get('/login').status_code==200
    for path in ('dashboard','matches','operations'):
        assert client.get('/api/data/'+path).status_code==401
    for value in ('bad','1.fake','9'*13+'.'+'a'*64):
        assert client.get('/',headers={'Cookie':'si_session='+value}).status_code==307
    assert client.post('/api/session',json={'password':'local-qa-password-only'}).status_code==403
    result=client.post('/api/session',headers={'Origin':base},json={'password':'local-qa-password-only'})
    assert result.status_code==200
    cookie=result.cookies['si_session'];flags=result.headers['set-cookie'].lower()
    assert 'httponly' in flags and 'samesite=strict' in flags and 'secure' in flags
    headers={'Cookie':'si_session='+cookie}
    assert client.get('/',headers=headers).status_code==200
    assert client.get('/settings',headers=headers).status_code==200
    for suffix in ('.extra','x'):
        assert client.get('/',headers={'Cookie':'si_session='+cookie+suffix}).status_code==307
    expires=str(int(time.time()*1000)-1000)
    signature=hmac.new(b'local-qa-only-token-32-characters-long',expires.encode(),hashlib.sha256).hexdigest()
    assert client.get('/',headers={'Cookie':f'si_session={expires}.{signature}'}).status_code==307
    feed=client.get('/api/data/matches',headers=headers)
    assert feed.status_code==200 and feed.json()['games'][0]['game_state']=='LIVE'
    assert client.get('/api/data/matches?date=bad',headers=headers).status_code==422
    assert client.post('/api/data/matches/sync',headers=headers,json={'date':feed.json()['date']}).status_code==403
    assert client.delete('/api/session',headers={'Origin':base}).status_code==200
print('PASS: private pages, login, cookie integrity/expiry, CSRF and NHL score proxy (no provider calls).')
