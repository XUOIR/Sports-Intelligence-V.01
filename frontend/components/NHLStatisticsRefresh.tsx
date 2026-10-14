'use client';
import {useEffect,useRef,useState} from 'react';
import {api} from '@/lib/client-api';
import type {Operations} from '@/lib/types';

export default function NHLStatisticsRefresh({status,onUpdated}:{status:NonNullable<Operations['nhl_statistics']>;onUpdated:()=>void}){
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const started=useRef(0),running=['queued','running'].includes(status.status);
  useEffect(()=>{
    if(!running){started.current=0;return;}
    if(!started.current)started.current=Date.now();
    if(Date.now()-started.current>240000)return;
    const timer=setTimeout(onUpdated,10000);return()=>clearTimeout(timer);
  },[running,status.status,onUpdated]);
  async function request(){setBusy(true);setMessage('');try{await api('operations/nhl-statistics-refresh',{method:'POST'});setMessage('Import queued. The last valid statistics stay available while it runs.');onUpdated();}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}
  return <section className="operations-card" aria-label="NHL statistics updates"><div className="card-heading"><div><span className="eyebrow">NHL DATA CONNECTION</span><h2>Advanced statistics</h2></div><span className={`badge ${status.status==='failed'?'hold':'watch'}`}>{running?'IMPORT RUNNING':status.status==='failed'?'LAST CACHE RETAINED':'DAILY IMPORT'}</span></div><p className="card-description">MoneyPuck team 5v5 expected goals and goalie GSAx. Completed-game data updates separately from the live score feed.</p><div className="account-readout"><b>Shared daily limit</b><span>{status.daily_imports_used} / {status.daily_imports_cap} import attempts today</span><small>A failed or interrupted attempt remains consumed. Other tabs and restarts cannot repeat it.</small></div><div className="account-readout"><b>Protected data transfer</b><span>{(status.bytes_monthly_used/1000000).toFixed(1)} / {(status.bytes_monthly_cap/1000000).toFixed(0)} MB reserved this month</span><small>This is our hosting-bandwidth safeguard, not a MoneyPuck credit allowance.</small></div><div className="account-readout"><b>Statistics date</b><span>{status.as_of_date||'Awaiting the first validated import'}</span><small>Scheduled at 9:00 AM Pacific. Source failures keep the last cache and its original age.</small></div><button className="blue-button" disabled={busy||running||status.daily_imports_used>=status.daily_imports_cap} onClick={()=>void request()}>{busy?'Queuing…':running?'Import running…':status.daily_imports_used>=status.daily_imports_cap?'Daily attempt used':'Import NHL statistics'}</button>{message&&<p className="fine-print" role="status">{message}</p>}<p className="fine-print">Free noncommercial data from MoneyPuck.com. No odds or AI refresh. Importing statistics does not confirm starters or approve a prediction.</p></section>;
}
