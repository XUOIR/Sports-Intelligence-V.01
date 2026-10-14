'use client';
import {useEffect,useState} from 'react';
import {api} from '@/lib/client-api';
import {shouldPoll} from '@/lib/activity.mjs';
import {shiftDay,matchTime,matchAge,feedExpired,playVisible} from '@/lib/matches.mjs';
import type {MatchFeed as Feed,MatchGame} from '@/lib/types';
export default function MatchFeed({onOpen}:{onOpen:(id:string)=>void}){
  const [day,setDay]=useState(''),[feed,setFeed]=useState<Feed|null>(null),[error,setError]=useState(''),[expanded,setExpanded]=useState(false),[clock,setClock]=useState(Date.now());
  const [bounds,setBounds]=useState({today:'',min:'',max:''});
  useEffect(()=>{
    let disposed=false,pending:AbortController|null=null,timer:ReturnType<typeof setTimeout>|undefined,failures=0,lastActivity=Date.now(),queuedAt=0;
    async function read(){
      if(disposed||pending)return;
      if(!shouldPoll({lastActivity,now:Date.now(),hidden:document.hidden})){timer=setTimeout(()=>void read(),30000);return;}
      const controller=new AbortController();pending=controller;const timeout=setTimeout(()=>controller.abort(),10000);
      try{const result=await api<Feed>(`matches${day?'?date='+day:''}`,{signal:controller.signal});if(disposed)return;
        setFeed(result);setBounds({today:result.today,min:result.min_date,max:result.max_date});setError('');failures=0;
        // Renew selected-day demand sparingly. The durable worker owns deduplication,
        // cooldowns and upstream calls; every GET is database-only.
        if(Date.now()-queuedAt>=600000){await api('matches/sync',{method:'POST',signal:controller.signal,body:JSON.stringify({date:result.date})});queuedAt=Date.now();}
      }catch(e){if(!disposed&&!(controller.signal.aborted&&document.hidden)){setError('Score connection interrupted. Last received scores are retained.');failures++;}}
      finally{clearTimeout(timeout);pending=null;if(!disposed)timer=setTimeout(()=>void read(),Math.min(300000,30000*2**Math.min(failures,4)));}
    }
    function active(){const paused=!shouldPoll({lastActivity,now:Date.now(),hidden:document.hidden});lastActivity=Date.now();if(paused&&!document.hidden){clearTimeout(timer);void read();}}
    function visibility(){if(document.hidden)pending?.abort();else{lastActivity=Date.now();clearTimeout(timer);void read();}}
    const events=['pointerdown','keydown','scroll','touchstart','pointermove'];events.forEach(e=>window.addEventListener(e,active,{passive:true}));document.addEventListener('visibilitychange',visibility);
    void read();const ticker=setInterval(()=>setClock(Date.now()),1000);
    return()=>{disposed=true;pending?.abort();clearTimeout(timer);clearInterval(ticker);events.forEach(e=>window.removeEventListener(e,active));document.removeEventListener('visibilitychange',visibility);};
  },[day]);
  const current=feed&&(!day||feed.date===day)?feed:null,selected=day||feed?.date||'',stale=feedExpired(current,clock)||!!error;
  function change(value:string){if(value!==selected&&value>=bounds.min&&value<=bounds.max){setDay(value);setFeed(null);setError('');}}
  function status(game:MatchGame){return game.schedule_state!=='OK'?game.schedule_state:['FINAL','OFF'].includes(game.game_state)?'Final':['LIVE','CRIT'].includes(game.game_state)?'LIVE':game.game_state==='UNKNOWN'?'Awaiting sync':matchTime(game.commence_time);}
  return <aside className={`match-sidebar ${expanded?'expanded':''}`} aria-label="NHL match feed"><div className="match-sidebar-heading"><h2>{selected&&selected!==bounds.today?'NHL matches':"Today's matches"}</h2><span>PT</span><button className="outline-button" onClick={()=>change(bounds.today)}>Today</button><button className="icon-button feed-collapse" aria-label={expanded?'Collapse matches':'Expand matches'} aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?'−':'+'}</button></div><div className="match-date"><button className="icon-button" aria-label="Previous day" disabled={!selected||selected<=bounds.min} onClick={()=>change(shiftDay(selected,-1))}>‹</button><input type="date" aria-label="Match date" value={selected} min={bounds.min} max={bounds.max} onChange={e=>{if(e.target.value)change(e.target.value)}}/><button className="icon-button" aria-label="Next day" disabled={!selected||selected>=bounds.max} onClick={()=>change(shiftDay(selected,1))}>›</button></div><div className={`match-feed-state ${stale?'stale':''}`} role="status"><span className={`status-dot ${stale?'amber':''}`}/>{error?'CONNECTION INTERRUPTED':current?.paused?'SCORE FEED PAUSED':!current?.observed_at?'LOADING SCORE FEED':stale?'LAST RECEIVED SCORES':'NHL SCORE FEED'}<small>{matchAge(current?.observed_at||null,clock)}</small></div><div className="match-feed-scroll" tabIndex={0} aria-label="Scrollable NHL games">{current?.games.map(game=>{
    const play=playVisible(game,current,clock)&&!error,decision=game.decision==='RECOMMEND'&&!play?'HOLD':game.decision,live=['LIVE','CRIT'].includes(game.game_state);
    return <button className={`match-feed-game ${live&&!stale?'is-live':''}`} key={game.id} onClick={()=>onOpen(game.id)} disabled={!game.detail_available} aria-label={`${game.away} at ${game.home}, ${status(game)}, ${play?'verified play':decision}`} title={game.reason}><div className="match-feed-teams"><span>{game.away}<b>{game.away_score??''}</b></span><span>{game.home}<b>{game.home_score??''}</b></span></div><div className="match-feed-meta"><span className={live&&!stale?'live-tag':''}>{live&&stale?'Last seen live':status(game)}</span><small>NHL</small></div><div className="match-feed-decision"><span className={`badge ${play?'recommend':decision.toLowerCase()}`}>{play?'VERIFIED PLAY':decision}</span>{live&&<small>{game.intermission?'Intermission':game.period_type==='OT'?'OT':game.period_type==='SO'?'SO':game.period?`P${game.period}`:''}{game.clock&&!game.intermission?` · ${game.clock}`:''}{stale?' · delayed':''}</small>}</div></button>;
  })}{current?.observed_at&&!current.games.length&&<div className="match-feed-empty">No NHL games scheduled for this date.</div>}{!current&&<div className="match-feed-empty">Loading this day's matches…</div>}</div><details className="match-coverage"><summary>Score timing & coverage</summary><p>NHL scores use a shared free feed. Live games are checked about every 30 seconds; other dates update less often. Provider delays and outages can occur. Scores do not refresh betting odds.</p><p>PLAY requires current pregame evidence and all eight gates. HOLD means verification is missing or expired. PASS is the engine's decision to skip. WATCH means no verified decision is recorded.</p><p>Clock values are the last received values. Scores never settle your wager ledger automatically.</p><a className="text-button" href="/settings">Odds refresh & provider controls ↗</a></details></aside>;
}
