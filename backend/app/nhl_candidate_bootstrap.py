"""One-time feature bootstrap from the exact already-admitted goalie ZIP version.

Explicit operator command only; never scheduled or exposed as a browser action.
It cannot refresh statistics dates, reset the daily import, or retry a failure.
"""
import asyncio
from datetime import timedelta
import io
from pathlib import Path
import tempfile
import zipfile
import httpx
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now,aware
from .config import settings
from .limits import limits,BudgetExceeded
from .models import ProviderState,AuditLog
from .nhl_advanced import CACHE_KEY,GOALIE_URL,MAX_GOALIE_WIRE,MAX_GOALIE_DECODED,download
from .nhl_data import csv_rows,GOALIE_FIELDS,validate_goalie
from .nhl_candidate_features import team_goaltending

CONTROL='nhl-xg-bootstrap'
OUTPUT='nhl-candidate-goaltending'


async def run(*,transport=None):
    at=now()
    async with db.Session.begin() as session:
        cache=await session.get(ProviderState,CACHE_KEY)
        if (cache is None or cache.info.get('schema_version')!=1 or cache.info.get('as_of_date')!=str(at.date())
                or not timedelta(0)<=at-aware(cache.observed_at)<=timedelta(hours=26)):
            raise BudgetExceeded('A current verified statistics import is required')
        if 'team_goaltending' in cache.info:return {'status':'already_in_import','paid_credits':0}
        added=await session.execute(insert(ProviderState).values(provider=CONTROL,observed_at=at,
            info={'status':'started','purpose':'one_time_candidate_feature_bootstrap','reserved_bytes':MAX_GOALIE_WIRE})
            .on_conflict_do_nothing().returning(ProviderState.provider))
        if added.scalar_one_or_none() is None:raise BudgetExceeded('The one-time feature bootstrap was already attempted')
        monthly=f'moneypuck-wire:{at:%Y-%m}'
        await limits._increment(session,monthly,MAX_GOALIE_WIRE,settings.nhl_advanced_monthly_bytes)
        parent=cache.info;parent_time=aware(cache.observed_at).isoformat()
        expected=parent['sources']['goalie']['sha256']
        session.add(AuditLog(action='NHL_FEATURE_BOOTSTRAP_ADMITTED',entity_id='MoneyPuck',
            details={'reserved_bytes':MAX_GOALIE_WIRE,'expected_source_sha256':expected,'paid_credits':0}))
    try:
        with tempfile.TemporaryDirectory(prefix='nhl-candidate-') as directory:
            path=Path(directory)/'goalies.zip'
            async with httpx.AsyncClient(timeout=15,follow_redirects=False,transport=transport) as client:
                metadata=await download(client,GOALIE_URL,path)
            if metadata['sha256']!=expected:
                raise ValueError('The source version changed; wait for the scheduled import')
            rows=[];seen=set()
            with zipfile.ZipFile(path) as archive:
                members=archive.infolist()
                if len(members)!=1 or not members[0].filename.endswith('.csv') or members[0].file_size>MAX_GOALIE_DECODED:
                    raise ValueError('Goalie ZIP contract changed')
                with archive.open(members[0]) as raw,io.TextIOWrapper(raw,encoding='utf-8-sig',newline='') as handle:
                    for row in csv_rows(handle,GOALIE_FIELDS,20_000):
                        season,day=validate_goalie(row)
                        key=(row['gameId'],row['playerId'],row['situation'])
                        if season!=2026 or day>=at.date() or key in seen:raise ValueError('Goalie bootstrap identity changed')
                        seen.add(key);rows.append(row)
            if len({row['gameId'] for row in rows})!=parent['team_games']:
                raise ValueError('Goalie bootstrap coverage differs from the admitted import')
            teams={code:team_goaltending(rows,at.date(),code,2026) for code in parent['teams']}
        observed=now()
        async with db.Session.begin() as session:
            cache=await session.get(ProviderState,CACHE_KEY)
            if (aware(cache.observed_at).isoformat()!=parent_time or cache.info['sources']['goalie']['sha256']!=expected):
                raise ValueError('The parent statistics import changed during derivation')
            await session.execute(insert(ProviderState).values(provider=OUTPUT,observed_at=observed,info={
                'as_of_date':parent['as_of_date'],'parent_observed_at':parent_time,'goalie_source_sha256':expected,
                'derived_at':observed.isoformat(),'teams':teams,'paid_credits':0}).on_conflict_do_nothing())
            control=await session.get(ProviderState,CONTROL,with_for_update=True)
            control.info={**control.info,'status':'succeeded','source_sha256':expected,'derived_at':observed.isoformat()}
            # Retain the full conservative transfer reservation. No daily import
            # counter, original source observation or statistics date is changed.
            session.add(AuditLog(action='NHL_FEATURE_BOOTSTRAP_SAVED',entity_id='MoneyPuck',
                details={'teams':len(teams),'source_sha256':expected,'paid_credits':0}))
        return {'status':'succeeded','teams':len(teams),'paid_credits':0}
    except (Exception,asyncio.CancelledError) as exc:
        async with db.Session.begin() as session:
            control=await session.get(ProviderState,CONTROL,with_for_update=True)
            control.info={**control.info,'status':'failed','category':type(exc).__name__,
                'reason':'Feature bootstrap did not complete; wait for the next scheduled import. No automatic retry.'}
        if isinstance(exc,asyncio.CancelledError):raise
        return {'status':'failed','category':type(exc).__name__,'paid_credits':0}
