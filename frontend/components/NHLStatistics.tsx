'use client';
import {useState} from 'react';
import type {NHLStatistics as Statistics,NHLTeamStatistics,NHLGoalieStatistics} from '@/lib/types';
import {pacificTime} from '@/lib/time.mjs';

const value=(v:string|undefined,digits=2)=>v!==undefined&&Number.isFinite(Number(v))?Number(v).toFixed(digits):'—';
const share=(v:string|undefined)=>v!==undefined&&Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(1)}%`:'—';

export default function NHLStatistics({data}:{data:Statistics|null|undefined}){
  const [selected,setSelected]=useState<Record<string,string>>({});
  if(!data)return null;
  if(!data.sides)return <section className="nhl-statistics" aria-label="NHL Matchup Statistics"><h3>NHL Matchup Statistics</h3><p className="muted">{data.message||'Statistics are awaiting verification.'}</p></section>;
  return <section className="nhl-statistics" aria-label="NHL Matchup Statistics"><div className="nhl-statistics-heading"><h3>NHL Matchup Statistics</h3><span className={`badge ${data.status==='stale'?'hold':'watch'}`}>{data.status==='stale'?'LAST VALID DATA':'GAME HISTORY'}</span></div><p className="nhl-statistics-source">Games through {data.verified_through} · Retrieved {data.observed_at?pacificTime(data.observed_at)+' PT':'—'}</p>{data.status==='stale'&&<p className="notice" role="status">These statistics need a newer import. The last valid values are retained.</p>}
  <div className="nhl-team-comparison">{(['away','home'] as const).map(side=>{
    const team=data.sides![side],metrics=team.metrics,goalies=team.goalies||[];
    const goalie=goalies.find(g=>g.player_id===selected[side]);
    return <article key={side}><span className="eyebrow">{side==='away'?'AWAY':'HOME'}</span><h4>{team.team}</h4><TeamMetrics metrics={metrics}/><label className="nhl-goalie-select">Compare goalie<select aria-label={`${side} goalie statistics`} value={selected[side]||''} onChange={e=>setSelected(current=>({...current,[side]:e.target.value}))}><option value="">Select a goalie</option>{goalies.map(g=><option key={g.player_id} value={g.player_id}>{g.name}</option>)}</select></label>{goalie?<GoalieMetrics goalie={goalie}/>:<p className="nhl-statistics-note">Choose a goalie to inspect their history. This selection does not confirm the starter.</p>}</article>;
  })}</div><p className="nhl-statistics-note">5v5 share uses total expected goals for ÷ total expected goals for and against. GSAx uses expected goals against − actual goals against. Windows use up to ten prior games; actual samples are shown.</p><p className="nhl-statistics-note">{data.note}</p><a className="text-button" href={data.source_url||'https://moneypuck.com/data.htm'} target="_blank" rel="noreferrer">Data: MoneyPuck.com ↗</a></section>;
}

function TeamMetrics({metrics}:{metrics:NHLTeamStatistics|null|undefined}){
  if(!metrics||metrics.status!=='available')return <p className="muted">{metrics?.status==='insufficient_sample'?'Too few eligible games for this comparison.':'Team statistics are unavailable.'}</p>;
  return <><div className="nhl-primary-stat"><strong>{share(metrics.xg_share)}</strong><span>5v5 expected-goal share</span></div><dl className="nhl-stat-rows"><div><dt>Expected goals for / 60</dt><dd>{value(metrics.xgf_per_60)}</dd></div><div><dt>Expected goals against / 60</dt><dd>{value(metrics.xga_per_60)}</dd></div><div><dt>Sample</dt><dd>{metrics.sample_games} games</dd></div><div><dt>Latest game</dt><dd>{metrics.latest_game_date||'—'}</dd></div></dl></>;
}

function GoalieMetrics({goalie}:{goalie:NHLGoalieStatistics}){
  return <div className="nhl-goalie-stat"><span className="badge hold">STARTER UNCONFIRMED</span>{goalie.status==='available'?<><div className="nhl-primary-stat"><strong>{Number(goalie.gsax)>0?'+':''}{value(goalie.gsax,3)}</strong><span>Goals saved above expected</span></div><dl className="nhl-stat-rows"><div><dt>Expected goals against</dt><dd>{value(goalie.xga,3)}</dd></div><div><dt>Goals conceded</dt><dd>{value(goalie.goals_against,0)}</dd></div><div><dt>Sample</dt><dd>{goalie.sample_games} appearances</dd></div><div><dt>Latest appearance</dt><dd>{goalie.latest_game_date||'—'}</dd></div></dl></>:<p className="muted">Only {goalie.sample_games} eligible appearance{goalie.sample_games===1?'':'s'}. At least three are required to show the rolling comparison.</p>}</div>;
}
