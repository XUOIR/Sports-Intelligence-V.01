'use client';
import {useState,useEffect} from 'react';
export default function WorkspaceNav({children,section='dashboard'}:{children?:React.ReactNode;section?:string}){
  useEffect(()=>{function restore(event:PageTransitionEvent){if(event.persisted)window.location.reload();}window.addEventListener('pageshow',restore);return()=>window.removeEventListener('pageshow',restore);},[]);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function logout(){setBusy(true);try{const result=await fetch('/api/session',{method:'DELETE'});if(!result.ok)throw new Error('Sign out failed. Please try again.');window.location.replace('/login');}catch(e){setError((e as Error).message);setBusy(false);}}
  return <><header className="topbar"><a className="brand" href="/" aria-label="G dollar Sports Intelligence home"><span className="brand-mark">G<span>$</span></span><span>SPORTS INTELLIGENCE<small>V.01</small></span></a><nav aria-label="Workspace"><a className={`nav-item ${section==='dashboard'?'selected':''}`} href="/">Overview</a><a className={`nav-item ${section==='performance'?'selected':''}`} href="/model-performance">Model Performance</a><a className={`nav-item ${section==='bankroll'?'selected':''}`} href="/bankroll">Bankroll</a>{children}<a className={`nav-item ${section==='settings'?'selected':''}`} href="/settings">Settings</a><button className="nav-item signout" disabled={busy} onClick={()=>void logout()}>{busy?'Signing out…':'Sign out'}</button></nav></header>{error&&<p className="notice" role="alert">{error}</p>}</>;
}
