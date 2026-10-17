'use client';
import {useEffect,useRef,useState} from 'react';
import {api} from '@/lib/client-api';
import {pacificTime} from '@/lib/time.mjs';
import type {NHLSourceTransport,Operations} from '@/lib/types';

function TransportDetails({details}:{details?:NHLSourceTransport|null}){
  if(!details||(!details.response_kind&&!details.server_family&&!details.redirect))return null;
  const redirect=details.redirect;
  return <>
    <small>Response: {details.response_kind?.replaceAll('_',' ')||'unclassified'}
      {details.server_family&&details.server_family!=='not_reported'?` · server family: ${details.server_family}`:''}
      {details.challenge_reported?' · source reported a browser challenge':''}</small>
    {redirect&&<small>Redirect: {redirect.origin?`${redirect.origin}${redirect.path||' (path withheld)'}`:'unrecognized destination withheld'}
      {redirect.details_withheld?' · private or unrecognized details withheld':''}. Redirects are not followed.</small>}
    {details.edge_reference&&<small>Source request reference: {details.edge_reference}</small>}
    {details.retry_after_seconds!==undefined&&<small>Source requested a {details.retry_after_seconds}-second wait. No retry is scheduled.</small>}
  </>;
}

export default function NHLStatisticsRefresh({status,onUpdated}:{status:NonNullable<Operations['nhl_statistics']>;onUpdated:()=>void}){
  const [busy,setBusy]=useState(false),[probing,setProbing]=useState(false),[message,setMessage]=useState('');
  const started=useRef(0),running=['queued','running'].includes(status.status);
  const probe=status.source_probe,probeRunning=['queued','running'].includes(probe?.last?.status||'');
  const automation=status.automation;
  const method=status.cache_acquisition==='operator_public_download'?'Manual Recovery':
    status.cache_acquisition==='manual_render_download'?'Manual Import':
    status.cache_acquisition==='scheduled_public_download'?'Scheduled Import':'Saved Import';
  const label=running?'IMPORT RUNNING':status.status==='failed'?'LAST CACHE RETAINED':
    status.status==='succeeded'?`${method.toUpperCase()} SAVED`:'AWAITING IMPORT';
  useEffect(()=>{
    if(!running&&!probeRunning){started.current=0;return;}
    if(!started.current)started.current=Date.now();
    if(Date.now()-started.current>240000)return;
    const timer=setTimeout(onUpdated,10000);return()=>clearTimeout(timer);
  },[running,probeRunning,status.status,probe?.last?.status,onUpdated]);
  async function diagnose(){
    setProbing(true);setMessage('');
    try{await api('operations/nhl-statistics-probe',{method:'POST'});setMessage('Source diagnostic admitted; its saved result is shown above. No statistics or prices are refreshed.');onUpdated();}
    catch(e){setMessage((e as Error).message);}finally{setProbing(false);}
  }
  async function request(){
    setBusy(true);setMessage('');
    try{await api('operations/nhl-statistics-refresh',{method:'POST'});setMessage('Import admitted. The last valid statistics stay available.');onUpdated();}
    catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
  }
  return <section className="operations-card" aria-label="NHL statistics updates">
    <div className="card-heading"><div><span className="eyebrow">NHL DATA CONNECTION</span><h2>Advanced Statistics</h2></div>
      <span className={`badge ${status.status==='failed'?'hold':'watch'}`}>{label}</span></div>
    <p className="card-description">MoneyPuck team 5v5 expected goals and goalie GSAx. Completed-game data updates separately from the live score feed.</p>
    {status.status==='failed'&&<div className="notice" role="status">
      <p>Last import failed{status.failure_stage?` during ${status.failure_stage.replaceAll('_',' ')}`:''}. {status.failure_reason||'This earlier attempt did not record a detailed reason.'} The previous cache keeps its original date. The consumed attempt will not be retried automatically.</p>
      <TransportDetails details={status.failure_transport}/>
    </div>}
    <div className="account-readout"><b>Automatic Daily Updates</b>
      <span>{automation?`${automation.consecutive_success_days} / ${automation.verification_target_days} consecutive successful days`:'Awaiting a Verified Scheduled Import'}</span>
      <small>Counts scheduled daily imports only. The three-day check measures download reliability; model validation is tracked separately.</small>
      {automation&&<small>Last scheduled attempt: {automation.last_attempt_date} · {automation.last_status}
        {automation.last_success_date?` · last success: ${automation.last_success_date}`:''}</small>}
      {automation?.last_status==='failed'&&<><small>{automation.last_failure?.reason}</small><TransportDetails details={automation.last_failure?.transport}/></>}
    </div>
    <div className="account-readout"><b>Shared Daily Limit</b><span>{status.daily_imports_used} / {status.daily_imports_cap} import attempts today</span>
      <small>A failed or interrupted attempt remains consumed. Other tabs and restarts cannot repeat it.</small></div>
    <div className="account-readout"><b>Protected Data Transfer</b><span>{(status.bytes_monthly_used/1000000).toFixed(1)} / {(status.bytes_monthly_cap/1000000).toFixed(0)} MB reserved this month</span>
      <small>This is our hosting-bandwidth safeguard, not a MoneyPuck credit allowance.</small></div>
    <div className="account-readout"><b>Statistics Date</b><span>{status.as_of_date||'Awaiting the first validated import'}</span>
      {status.observed_at&&<small>{method} · received {pacificTime(status.observed_at)} PT{status.verified_through?` · game results through ${status.verified_through}`:''}</small>}
      <small>Scheduled at 9:00 AM Pacific. Source failures keep the last cache and its original age.</small></div>
    <button className="blue-button" disabled={busy||running||probing||probeRunning||status.daily_imports_used>=status.daily_imports_cap} onClick={()=>void request()}>
      {busy?'Queuing…':running?'Import running…':status.daily_imports_used>=status.daily_imports_cap?'Daily attempt used':'Import NHL statistics'}</button>
    <div className="account-readout"><b>Source Connection Diagnostic</b>
      <small>Checks two small source samples from Render once per day. Reserves 2 MB of the existing transfer budget. Does not import statistics, reset the daily import attempt, or use odds/AI credits.</small>
      <button className="outline-button" disabled={running||probing||probeRunning||(probe?.daily_used||0)>=(probe?.daily_limit||1)} onClick={()=>void diagnose()}>
        {probing||probeRunning?'Checking Source Connection…':(probe?.daily_used||0)>=(probe?.daily_limit||1)?'Daily Diagnostic Used':'Check Source Connection'}</button>
      {probe?.last&&<><small>Checked {pacificTime(probe.last.checked_at)} PT · {probe.last.status==='complete'?'Small samples received; full-file validation still required.':probe.last.reason||probe.last.status}</small>
        {probe.last.sources.map(row=><div key={row.source}><small>{row.source==='team'?'Team Data':'Goalie Data'}: HTTP {row.http_status??'unavailable'} · {row.status==='sample_available'?'small transport sample received':row.reason||row.status}</small>
          <TransportDetails details={row}/></div>)}</>}
    </div>
    {message&&<p className="fine-print" role="status">{message}</p>}
    <p className="fine-print">Free noncommercial data from MoneyPuck.com. No odds or AI refresh. Importing statistics does not confirm starters or approve a prediction.</p>
  </section>;
}
