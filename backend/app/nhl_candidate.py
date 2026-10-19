"""Separate forward candidate cohort using saved inputs and saved prices only."""
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now,aware
from .config import settings
from .limits import limits
from .models import Fixture,ProviderState,PaperForecast,PaperInputArchive,PaperPriceObservation
from .market_display import latest_quotes
from .nhl_candidate_features import FEATURES,vector
from .nhl_candidate_model import load_bundle,probability
from .nhl_paper_model import load_bundle as load_base
from .nhl_paper import version as base_version,quote_observation,identity


def version(digest):return 'nhl-xg-paper-v1-'+digest[:12]


def forecast(bundle,base,fixture,statistics,goaltending,at):
    start=aware(fixture.commence_time)
    if (start<=at or start.date()!=at.date() or base is None or base.captured_at is None
            or not aware(base.captured_at)<=at<aware(base.start_at) or aware(base.start_at)!=start
            or base.home!=fixture.home or base.away!=fixture.away
            or base.inputs.get('model_sha256')!=bundle['base_model_sha256']):
        raise ValueError('A compatible genuinely saved pregame baseline is required')
    if (statistics is None or statistics.info.get('schema_version')!=1
            or statistics.info.get('as_of_date')!=str(start.date())
            or not timedelta(0)<=at-aware(statistics.observed_at)<=timedelta(hours=26)
            or statistics.info.get('model_approved_by_import') is not False):
        raise ValueError('Today\u2019s verified pregame statistics are required')
    batch=statistics.info
    if any(aware(item['observed_at'])>at or aware(item['published_at'])>at for item in batch['sources'].values()):
        raise ValueError('Future advanced source rejected')
    derived_at=aware(statistics.observed_at)
    goalie_teams=batch.get('team_goaltending')
    if goalie_teams is None:
        if (goaltending is None or goaltending.info.get('as_of_date')!=batch['as_of_date']
                or goaltending.info.get('goalie_source_sha256')!=batch['sources']['goalie']['sha256']
                or goaltending.info.get('parent_observed_at')!=aware(statistics.observed_at).isoformat()
                or aware(goaltending.observed_at)>at):
            raise ValueError('Awaiting the next saved team-goaltending feature batch')
        goalie_teams=goaltending.info['teams'];derived_at=aware(goaltending.observed_at)
    teams,goalies={},{}
    for side in ('home','away'):
        code=fixture.metrics.get(side+'_abbrev')
        if not code or code not in batch['teams'] or code not in goalie_teams:
            raise ValueError('Candidate team statistics are missing')
        teams[side],goalies[side]=batch['teams'][code],goalie_teams[code]
        if teams[side].get('team')!=code:raise ValueError('Candidate team identity changed')
    values=vector(base.inputs['features'],teams,goalies,start.date())
    inputs={'features':values,'feature_names':FEATURES,'base_forecast_id':base.id,
        'base_model_sha256':bundle['base_model_sha256'],'base_input_archive_sha256':base.inputs['input_archive_sha256'],
        'statistics_observed_at':aware(statistics.observed_at).isoformat(),'derived_features_observed_at':derived_at.isoformat(),
        'teams':teams,'team_goaltending':goalies,'sources':batch['sources'],
        'lineup_policy':'Team goaltending form; expected or unknown named starters permitted. No named-goalie adjustment.',
        'market':'h2h_final_including_ot_so','approved_for_wagers':False}
    return Decimal(str(probability(bundle,values))),inputs


async def collect():
    if 'NHL' not in settings.active_sports:return
    bundle,digest=load_bundle();base_bundle,base_digest=load_base()
    if bundle['base_model_sha256']!=base_digest:raise ValueError('Frozen baseline reference changed')
    at=now();model=version(digest)
    async with db.Session() as session:
        ids=(await session.scalars(select(Fixture.id).where(Fixture.sport=='NHL',Fixture.id.like('nhl:%'),
            Fixture.commence_time>at,Fixture.commence_time<at+timedelta(hours=48)).limit(100))).all()
    captured=blocked=positions=0
    for fid in ids:
        async with db.Session.begin() as session:
            fixture=await session.get(Fixture,fid,with_for_update=True);at=now()
            if fixture.metrics.get('nhl_game_type')!=2 or aware(fixture.commence_time)<=at:continue
            await session.execute(insert(PaperForecast).values(fixture_id=fid,model_version=model,
                first_seen_at=at,start_at=fixture.commence_time,home=fixture.home,away=fixture.away,inputs={})
                .on_conflict_do_nothing(index_elements=['fixture_id','model_version']))
            row=await session.scalar(select(PaperForecast).where(PaperForecast.fixture_id==fid,
                PaperForecast.model_version==model).with_for_update())
            if row.resolution or aware(row.start_at)!=aware(fixture.commence_time):continue
            if row.captured_at is None:
                try:
                    if aware(fixture.commence_time).date()!=at.date():
                        raise ValueError('Awaiting match-day statistics')
                    base=await session.scalar(select(PaperForecast).where(PaperForecast.fixture_id==fid,
                        PaperForecast.model_version==base_version(base_digest)))
                    if base is None or not base.captured_at:raise ValueError('Awaiting a saved baseline forecast')
                    archive=await session.get(PaperInputArchive,base.inputs.get('input_archive_sha256') or '')
                    if archive is None:raise ValueError('Baseline official input archive is missing')
                    raw={key:value for key,value in archive.data.items() if key!='observed_at'}
                    if (hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=archive.sha256
                            or aware(archive.observed_at)>aware(base.captured_at)):
                        raise ValueError('Baseline archive integrity or observation time mismatch')
                    stats=await session.get(ProviderState,'nhl-advanced-statistics')
                    goalie=await session.get(ProviderState,'nhl-candidate-goaltending') if stats and 'team_goaltending' not in stats.info else None
                    p,inputs=forecast(bundle,base,fixture,stats,goalie,at)
                    captured_at=now()
                    if captured_at>=aware(fixture.commence_time):raise ValueError('Game started before candidate capture finished')
                    row.home_probability=p.quantize(Decimal('.0000000001'))
                    row.inputs={**inputs,'model_sha256':digest};row.captured_at=captured_at;row.issue=None;captured+=1
                except (ValueError,TypeError,KeyError) as exc:
                    row.issue=str(exc)[:400];blocked+=1;continue
            quotes=(await latest_quotes(session,[fid])).get(fid,[]);at=now()
            if at>=aware(fixture.commence_time):continue
            status,data=quote_observation(fixture,quotes,Decimal(row.home_probability),at)
            added=await session.execute(insert(PaperPriceObservation).values(forecast_id=row.id,
                identity=identity({'status':status,'quotes':data['quotes']}),observed_at=at,status=status,data=data)
                .on_conflict_do_nothing().returning(PaperPriceObservation.id))
            oid=added.scalar_one_or_none()
            if oid and status=='VALID' and data.get('qualifies') and row.position is None:
                row.position={**data['qualifies'],'observed_at':at.isoformat(),'observation_id':oid};positions+=1
    await limits.observe('nhl-xg-collection',{'model_version':model,'captured':captured,'blocked':blocked,
        'new_positions':positions,'paid_credits':0})
