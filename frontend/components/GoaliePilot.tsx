'use client';
import {useEffect,useState} from 'react';
import {api} from '@/lib/client-api';
import {pacificTime} from '@/lib/time.mjs';
import type {GoaliePilot as Pilot} from '@/lib/types';

export default function GoaliePilot({status,onUpdated}:{status:Pilot;onUpdated:()=>void}){
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[clock,setClock]=useState(Date.now());
  useEffect(()=>{const timer=setInterval(()=>setClock(Date.now()),1000);return()=>clearInterval(timer);},[]);
  const running=status.status==='running'&&!!status.started_at&&clock-Date.parse(status.started_at)<90000;
  const phase=status.expires_at&&clock>=Date.parse(status.expires_at)&&status.phase==='active'?'expired':status.phase;
  useEffect(()=>{
    if(!running)return;
    const timer=setTimeout(onUpdated,5000);return()=>clearTimeout(timer);
  },[running,status.status,onUpdated]);
  const waiting=!!status.next_at&&clock<Date.parse(status.next_at);
  async function action(value:'start'|'pause'|'resume'|'check'){
    setBusy(true);setError('');
    try{await api('operations/nhl-goalie-pilot',{method:'POST',body:JSON.stringify({action:value})});onUpdated();}
    catch(caught){setError((caught as Error).message);onUpdated();}finally{setBusy(false);}
  }
  const label=({not_started:'NOT STARTED',active:'TEST RUNNING',paused:'PAUSED',halted:'STOPPED AFTER FAILURE',expired:'TEST EXPIRED'})[phase];
  return <section className="operations-card" aria-label="Daily Faceoff goalie pilot">
    <div className="card-heading"><div><span className="eyebrow">NHL STARTER SOURCE · REPORTS ONLY</span><h2>Daily Faceoff Test Feed</h2></div><span className={`badge ${status.phase==='halted'?'hold':'watch'}`}>{label}</span></div>
    <p className="card-description">A private 72-hour test of the public starting-goalies page. Reports appear beside your manual selections. They do not confirm starters, change forecasts or start AI reviews.</p>
    {status.reason&&<p className="notice" role="status">{status.reason} No automatic retry is scheduled.</p>}
    <div className="account-readout"><b>Test Window</b><span>{status.expires_at?`Ends ${pacificTime(status.expires_at)} PT`:'Awaiting the first test'}</span><small>Resume keeps the original deadline. A deployment or another browser cannot restart the allowance.</small></div>
    <div className="account-readout"><b>Source Requests</b><span>{status.requests_reserved_today} / {status.request_cap} reserved today</span><small>One shared page check at most every ten minutes, scheduled within eight hours of today's upcoming games. Includes the cached crawler-policy check; failed reservations stay consumed.</small></div>
    <div className="account-readout"><b>Protected Transfer</b><span>{(status.bytes_reserved_today/1000000).toFixed(2)} / {status.daily_byte_cap/1000000} MB today · {(status.bytes_reserved_month/1000000).toFixed(2)} / {status.monthly_byte_cap/1000000} MB this month</span><small>No Odds API or OpenRouter credits. Unknown transfer after a failure keeps its full reservation.</small></div>
    <div className="account-readout"><b>Last Saved Check</b><span>{status.last_success_at?`${pacificTime(status.last_success_at)} PT · ${status.matched_games??0} matched games`:'No successful collection yet'}</span><small>{status.unmatched_source_games?`${status.unmatched_source_games} source games could not be matched safely. `:''}Player names need an unambiguous saved NHL ID match. A mismatch remains visible for review.</small></div>
    <div className="goalie-pilot-actions">
      {['not_started','expired'].includes(phase)?<button className="blue-button" disabled={busy} onClick={()=>void action('start')}>Start 72-Hour Test</button>:
        phase==='active'?<button className="outline-button" disabled={busy} onClick={()=>void action('pause')}>Pause Test</button>:
        <button className="outline-button" disabled={busy||running||waiting} onClick={()=>void action('resume')}>Resume Test</button>}
      <button className="outline-button" disabled={busy||running||waiting||phase!=='active'} onClick={()=>void action('check')}>{running?'Checking Source…':waiting?'Ten-Minute Cooldown':'Check Now'}</button>
      <button className="text-button" disabled={busy} onClick={onUpdated}>Reload Test Status ↗</button>
    </div>
    {error&&<p className="notice" role="alert">{error}</p>}
    <p className="fine-print">Stops on an access error, changed format or crawler restriction. Source update times and our observation times are saved separately. Public HTML extraction is under evaluation; no supported API or reuse licence is claimed.</p>
  </section>;
}
