'use client';
import type {NHLStarterPreview} from '@/lib/types';
import {starterStatus} from '@/lib/starters.mjs';
import {pacificTime} from '@/lib/time.mjs';

export default function NHLStarters({data,home,away,clock}:{clock:number;data?:NHLStarterPreview|null;home:string;away:string}){
  if(!data)return null;
  return <section className="nhl-statistics" aria-label="Starting Goalies">
    <h3>Starting Goalies</h3>
    <div className="nhl-team-comparison">{(['away','home'] as const).map(side=>{
      const row=data.sides[side],status=starterStatus(row,data,clock);
      return <article key={side}><h4>{side==='home'?home:away}</h4>
        <span className={`badge ${status==='confirmed'?'recommend':status==='projected'?'watch':'hold'}`}>
          {status==='confirmed'?'CONFIRMED STARTER':status==='projected'?'PROJECTED STARTER':'STARTER UNKNOWN'}
        </span>
        <p><strong>{status==='confirmed'?row.confirmed_name:status==='projected'?row.projected_name:'Awaiting Confirmation'}</strong></p>
        {status==='confirmed'?<p className="nhl-statistics-note">Rechecked {pacificTime(row.confirmed_at!)} PT
          {row.reported_at?` · Report published ${pacificTime(row.reported_at)} PT`:''}
          {row.source_url&&<> · <a href={row.source_url} target="_blank" rel="noreferrer">Confirmation Source ↗</a></>}</p>:
          <p className="nhl-statistics-note">{status!==row.status?`Saved ${row.status} evidence expired. Refresh saved evidence and recheck the source.`:row.reason}</p>}
        {!!row.candidates.length&&<dl className="nhl-stat-rows">{row.candidates.map(candidate=><div key={candidate.player_id}>
          <dt>{candidate.name}<small style={{display:'block'}}>Latest appearance: {candidate.latest_appearance||'Unavailable'}</small></dt>
          <dd>{candidate.season_appearances} season appearances</dd>
        </div>)}</dl>}
      </article>;
    })}</div>
    <p className="nhl-statistics-note">{data.note}</p>
  </section>;
}
