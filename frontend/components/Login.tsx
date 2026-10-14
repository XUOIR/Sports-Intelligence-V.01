'use client';
import {useState} from 'react';
export default function Login(){
  const [password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function signIn(event:React.FormEvent){event.preventDefault();setBusy(true);setError('');try{
    const result=await fetch('/api/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});
    const body=await result.json();if(!result.ok)throw new Error(body.detail||'Unable to sign in');
    setPassword('');window.location.replace('/');
  }catch(e){setError((e as Error).message);setBusy(false);}}
  return <main className="login-page"><a className="brand" href="/login"><span className="brand-mark">G<span>$</span></span><span>SPORTS INTELLIGENCE<small>V.01</small></span></a><section className="login-card"><span className="eyebrow">YOUR PRIVATE WORKSPACE</span><h1>Welcome <span className="gradient-text">back.</span></h1><p>Sign in to view your NHL match feed, intelligence, and wager ledger.</p><form onSubmit={signIn}><label htmlFor="dashboard-password">Dashboard password</label><input id="dashboard-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required autoFocus maxLength={256}/><button className="blue-button" disabled={busy}>{busy?'Signing in…':'Open workspace ↗'}</button>{error&&<p className="notice" role="alert">{error}</p>}</form><small>Private access · G$ Sports Intelligence V.01</small></section></main>;
}
