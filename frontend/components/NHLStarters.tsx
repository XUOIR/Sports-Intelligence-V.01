'use client';
import {useRef,useState} from 'react';
import GoalieSourceReport from './GoalieSourceReport';
import type {NHLStarterPreview,GoalieSourceReport as Report} from '@/lib/types';
import {starterStatus} from '@/lib/starters.mjs';
import {pacificTime} from '@/lib/time.mjs';

export default function NHLStarters({data,home,away,clock,fixtureId,onSaved,canVerify=true,report}:{report?:Report|null;clock:number;data?:NHLStarterPreview|null;home:string;away:string;fixtureId:string;onSaved:()=>void|Promise<void>;canVerify?:boolean}){
  const [selected,setSelected]=useState<Record<'home'|'away',string>>({home:data?.sides.home.confirmed_player_id||'',away:data?.sides.away.confirmed_player_id||''});
  const [saving,setSaving]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  const requestId=useRef<string|null>(null);
  if(!data)return null;
  const options=data.selection;
  const selectionValid=!!options&&(['home','away'] as const).every(side=>options.sides[side].some(row=>row.player_id===selected[side]))&&selected.home!==selected.away;
  async function confirm(){
    if(!selectionValid||!canVerify||saving||!options)return;
    setSaving(true);setError('');setMessage('');requestId.current??=crypto.randomUUID();
    try{
      const response=await fetch(`/api/data/fixtures/${encodeURIComponent(fixtureId)}/starting-goalies`,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({request_id:requestId.current,candidate_version:options.version,home_player_id:selected.home,away_player_id:selected.away}),signal:AbortSignal.timeout(12000)});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Could not save the goalie selection. Reload this match and try again.');
      setMessage('Manual Confirmation Saved. Other readiness checks still apply.');
      await onSaved();
      requestId.current=null;
    }catch(caught){setError(caught instanceof Error&&caught.name!=='TimeoutError'?caught.message:'The response was interrupted. Reload the match to check whether your selection saved before retrying.');}
    finally{setSaving(false);}
  }
  return <section className="nhl-statistics" aria-label="Starting Goalies">
    <div className="nhl-statistics-heading"><h3>Starting Goalies</h3><a className="text-button" href="https://www.dailyfaceoff.com/starting-goalies" target="_blank" rel="noreferrer">Check Daily Faceoff ↗</a></div>
    <div className="nhl-team-comparison">{(['away','home'] as const).map(side=>{
      const row=data.sides[side],status=starterStatus(row,data,clock),choices=options?.sides[side]||[];
      const manual=row.confirmation_method==='manual_operator';
      return <article key={side}><h4>{side==='home'?home:away}</h4>
        <span className={`badge ${status==='confirmed'?'recommend':status==='projected'?'watch':'hold'}`}>
          {status==='confirmed'?(manual?'MANUALLY CONFIRMED':'CONFIRMED STARTER'):status==='projected'?'PROJECTED STARTER':'STARTER UNKNOWN'}
        </span>
        <p><strong>{status==='confirmed'?row.confirmed_name:status==='projected'?row.projected_name:'Awaiting Confirmation'}</strong></p>
        <label className="nhl-goalie-select">{side==='home'?'Home':'Away'} Starting Goalie
          <select aria-label={`${side} starting goalie`} value={choices.some(choice=>choice.player_id===selected[side])?selected[side]:''} disabled={!canVerify||saving||!choices.length}
            onChange={event=>{setSelected(current=>({...current,[side]:event.target.value}));requestId.current=null;setMessage('');setError('');}}>
            <option value="">{choices.length?'Select a goalie':'Awaiting Saved Team Goalies'}</option>
            {choices.map(choice=><option key={choice.player_id} value={choice.player_id}>{choice.name}</option>)}
          </select>
        </label>
        {status==='confirmed'?<p className="nhl-statistics-note">{manual?'Confirmed by you':'Rechecked'} {pacificTime(row.confirmed_at!)} PT
          {row.reported_at?` · Report published ${pacificTime(row.reported_at)} PT`:''}
          {row.source_url&&<> · <a href={row.source_url} target="_blank" rel="noreferrer">Confirmation Source ↗</a></>}</p>:
          <p className="nhl-statistics-note">{status!==row.status?`Saved ${row.status} evidence expired. Recheck today’s starters and confirm again.`:row.reason}</p>}
        {!!row.candidates.length&&<details><summary className="nhl-statistics-note">Goalie Workload History</summary><dl className="nhl-stat-rows">{row.candidates.map(candidate=><div key={candidate.player_id}>
          <dt>{candidate.name}<small style={{display:'block'}}>Latest appearance: {candidate.latest_appearance||'Unavailable'}</small></dt>
          <dd>{candidate.season_appearances} season appearances</dd>
        </div>)}</dl></details>}
      </article>;
    })}</div>
    <button className="outline-button" disabled={!canVerify||!selectionValid||saving} onClick={()=>void confirm()}>{saving?'Saving…':'Confirm Selection'}</button>
    <p className="nhl-statistics-note">{canVerify?'By confirming, you identify these two goalies as today’s starters. The app records your confirmation time automatically.':'The game has started. New pregame confirmations are closed.'}</p>
    {message&&<p className="notice" role="status">{message}</p>}{error&&<p className="notice" role="alert">{error}</p>}
    <GoalieSourceReport report={report} clock={clock} home={home} away={away}/><details><summary className="nhl-statistics-note">About Starter Data</summary><p className="nhl-statistics-note">{data.note} Daily Faceoff opens separately for reference; no automatic Daily Faceoff feed is connected. Saving this selection does not refresh odds or start an AI review.</p></details>
  </section>;
}
