'use client';
import {useCallback,useEffect,useState} from 'react';
import Operations from './Operations';
import Readiness from './Readiness';
import WorkspaceNav from './WorkspaceNav';
import {api} from '@/lib/client-api';
import type {Operations as Status,Allowance,OddsRefreshResult} from '@/lib/types';
export default function Settings({development=false}:{development?:boolean}){
  const [status,setStatus]=useState<Status|null>(null),[error,setError]=useState('');
  const refresh=useCallback(async()=>{try{setStatus(await api<Status>('operations'));setError('');}catch(e){setError((e as Error).message);}},[]);
  useEffect(()=>{void refresh();},[refresh]);
  return <main><WorkspaceNav section="settings"/><div className="page-content settings-content"><div className="page-heading"><span className="eyebrow">{development?'TEMPORARY DEVELOPMENT CHECKLIST':'PRIVATE WORKSPACE SETTINGS'}</span><h1>{development?'NHL build progress':'Connections & credits'}<span className="title-dot">.</span></h1><p>{development?'This checklist tracks the work required before NHL picks can become verified plays. It will leave the product when the build is complete.':'Manage provider allowances, spending protection, and your manual odds refresh.'}</p></div>{error&&<p className="notice" role="alert">{error}</p>}{!status&&!error&&<p className="muted">Loading private settings…</p>}{status&&(development?<Readiness status={status}/>:<Operations status={status} onPause={async paused=>{await api('operations/pause',{method:'PATCH',body:JSON.stringify({paused})});await refresh();}} onResume={async provider=>{await api('operations/resume',{method:'POST',body:JSON.stringify({provider})});await refresh();}} onCheck={async()=>{const result=await api<{providers:Allowance[]}>('operations/allowances',{method:'POST'});return result.providers;}} onRequestOdds={async id=>api<OddsRefreshResult>('operations/odds-refresh',{method:'POST',body:JSON.stringify({request_id:id})})} onCheckOdds={async id=>api<OddsRefreshResult>(`operations/odds-refresh/${id}`)} onUpdated={()=>void refresh()}/>)}<div className="settings-links"><a className="text-button" href={development?'/settings':'/development'}>{development?'Back to connections & credits':'View temporary build checklist'} ↗</a><a className="text-button" href="/">Back to NHL intelligence ↗</a></div></div></main>;
}
