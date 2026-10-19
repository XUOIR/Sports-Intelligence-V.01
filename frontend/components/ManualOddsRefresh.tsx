'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import type {OddsRefreshWindow,OddsRefreshResult} from '@/lib/types';
import {pacificTime} from '@/lib/time.mjs';

const storage='si-pending-odds-refresh';
type Saved={id:string;started:number};
export default function ManualOddsRefresh({window,disabled,onRequest,onCheck,onUpdated}:{window:OddsRefreshWindow;disabled:boolean;onRequest:(id:string)=>Promise<OddsRefreshResult>;onCheck:(id:string)=>Promise<OddsRefreshResult>;onUpdated:()=>void}){
  const [pending,setPending]=useState<Saved|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const requestRef=useRef(onRequest),checkRef=useRef(onCheck),updateRef=useRef(onUpdated);
  const sending=useRef(false);
  requestRef.current=onRequest;checkRef.current=onCheck;updateRef.current=onUpdated;
  useEffect(()=>{
    const reset=Date.parse(window.reset_at||'');
    if(!Number.isFinite(reset))return;
    const server=Date.parse(window.as_of||'');
    const due=Date.now()+Math.max(0,reset-(Number.isFinite(server)?server:Date.now()))+1000;
    // Refresh saved data using the server's interval, never a provider request.
    const reload=()=>updateRef.current();
    const timer=setTimeout(reload,Math.max(250,due-Date.now()));
    const visible=()=>{if(!document.hidden&&Date.now()>=due)reload();};
    document.addEventListener('visibilitychange',visible);
    return()=>{clearTimeout(timer);document.removeEventListener('visibilitychange',visible);};
  },[window.reset_at,window.as_of]);
  useEffect(()=>{try{const saved=JSON.parse(localStorage.getItem(storage)||'null');if(saved&&/^[0-9a-f-]{36}$/i.test(saved.id)&&Number.isFinite(saved.started))setPending(saved);}catch{}},[]);
  const accept=useCallback((result:OddsRefreshResult,saved:Saved)=>{
    if(result.status==='in_progress'||result.status==='not_sent'&&Date.now()-saved.started<60000){setMessage('Checking the saved refresh. No second request will be sent.');return;}
    setPending(null);try{localStorage.removeItem(storage);}catch{}
    setMessage(result.status==='succeeded'?result.message||'NHL odds refresh completed.':result.status==='skipped'?result.message||'No upcoming games; no credits used.':result.status==='not_sent'?'The request did not reach Odds API. No refresh slot was used.':result.status==='unknown'?'The previous attempt is unconfirmed and will not be repeated. Its refresh slot stays used.':'The refresh failed. Its slot stays used if the request reached Odds API.');
    updateRef.current();
  },[]);
  useEffect(()=>{if(!pending)return;let stopped=false,timer:ReturnType<typeof setTimeout>;
    async function check(){if(!document.hidden){try{const result=await checkRef.current(pending!.id);if(!stopped)accept(result,pending!);}catch{if(!stopped)setMessage('The refresh is saved. Check its status before starting another.');}}
      if(!stopped)timer=setTimeout(()=>void check(),Date.now()-pending!.started<60000?2000:10000);}
    timer=setTimeout(()=>void check(),2000);return()=>{stopped=true;clearTimeout(timer);};
  },[pending,accept]);
  async function action(){if(sending.current)return;sending.current=true;setBusy(true);setMessage('');
    const saved=pending||{id:crypto.randomUUID(),started:Date.now()};
    if(!pending){try{localStorage.setItem(storage,JSON.stringify(saved));}catch{setMessage('Browser storage is unavailable. The refresh was not sent.');sending.current=false;setBusy(false);return;}setPending(saved);}
    try{
      accept(await (pending?checkRef.current(saved.id):requestRef.current(saved.id)),saved);
    }catch{setMessage('The request is saved. Only its status will be checked; it will not be resent.');updateRef.current();}
    finally{sending.current=false;setBusy(false);}
  }
  return <div className="manual-odds"><div className="manual-odds-heading"><b>Manual NHL Odds Refresh</b><span>{window.used} of {window.limit} used today · {window.remaining} remaining</span></div>
    <p>One refresh checks all upcoming NHL games and reserves {window.credit_cost} credits. Up to {window.limit} attempts per Pacific calendar day.</p>
    <button className="blue-button" disabled={busy||!pending&&(disabled||!window.remaining||window.in_progress||window.needs_resume)} onClick={()=>void action()}>{busy?'Checking…':pending?'Check saved refresh':'Refresh NHL odds'}</button>
    {window.reset_at&&<small>Daily allowance resets at 12:00 a.m. Pacific · next reset {pacificTime(window.reset_at)} PT. Monthly credits do not reset daily.</small>}
    {window.needs_resume&&<small>An interrupted refresh needs an explicit provider resume. Midnight does not retry it or clear the provider pause; the earlier attempt remains recorded.</small>}
    {message&&<p role="status">{message}</p>}
    <small>Automatic odds refreshes are off. Reloading the dashboard uses stored data and does not spend odds credits.</small>
  </div>;
}
