'use client';
import type {Fixture,Quote} from '@/lib/types';
import {moneylinePair,probabilities,priceComparison,noVig} from '@/lib/market.mjs';
import {pacificTime} from '@/lib/time.mjs';
const percent=(p:number|undefined)=>p===undefined?'—':`${(p*100).toFixed(1)}%`;
const odds=(p:number|null|undefined)=>p==null?'—':p.toFixed(3);
export default function DailyMatchups({fixtures,quotes,clock,onOpen}:{fixtures:Fixture[];quotes:Record<string,Quote[]>;clock:number;onOpen:(f:Fixture)=>void}){
  return <div className="daily-matchups">{fixtures.map(f=>{
    const pair=moneylinePair(f,quotes[f.id],clock),reference=moneylinePair(f,quotes[f.id],clock,['pinnacle']),benchmark=noVig(reference);
    const p=probabilities(f),state=f.dirty&&f.state==='RECOMMEND'?'HOLD':f.state;
    return <article className="daily-match-card" key={f.id} aria-label={`${f.away} at ${f.home} market comparison`}>
      <div className="card-heading"><span className="eyebrow">NHL · {pacificTime(f.commence_time)} PT</span><span className={`badge ${state.toLowerCase()}`}>{state==='RECOMMEND'?'VERIFIED PLAY':state}</span></div>
      <button className="match-title" onClick={()=>onOpen(f)}><h3>{f.away}<span>at {f.home} ↗</span></h3></button>
      <div className="daily-prices"><span className="eyebrow">PLAYNOW · MONEYLINE</span><span className={`badge ${!pair||pair.stale?'hold':'watch'}`}>{!pair?'UNAVAILABLE':pair.stale?'LAST RECEIVED':'CURRENT PRICE'}</span></div>
      <div className="price-pair">{(['away','home'] as const).map(side=><div key={side}><span>{f[side]}</span><strong>{pair?Number(pair[side].decimal_odds).toFixed(3):'—'}</strong><small>{pair?`${percent(1/Number(pair[side].decimal_odds))} break-even`:'No saved PlayNow price'}</small></div>)}</div>
      {pair&&<p className="fine-print">Observed {pacificTime(pair.source_at)} PT · {pair.stale?'Older than five minutes; execution locked.':'Freshness alone does not verify a play.'}</p>}
      {reference&&benchmark&&<div className="market-benchmark"><b>Pinnacle market benchmark</b><div className="probability-labels"><span>{f.away}<strong>{percent(benchmark.away)}</strong></span><span>{f.home}<strong>{percent(benchmark.home)}</strong></span></div><p className="fine-print">Bookmaker margin removed from the saved two-way prices. This is a market estimate, separate from our model. Observed {pacificTime(reference.source_at)} PT{reference.stale?' · older than five minutes':''}.</p></div>}
      <div className="match-probability"><div><b>Model win probability</b><span>{p?'SAVED ESTIMATE':'AWAITING VALIDATED FORECAST'}</span></div><div className="probability-labels"><span>{f.away}<strong>{percent(p?.away)}</strong></span><span>{f.home}<strong>{percent(p?.home)}</strong></span></div><input type="range" min="0" max="100" step="0.1" value={p?p.home*100:50} disabled aria-label={`${f.home} model win probability${p?'':' unavailable'}`} className={p?'':'unknown-range'}/><small>{p?'Two-way moneyline; probabilities total 100%.':'Team xG share is descriptive and is not a win probability.'}</small></div>
      <div className="edge-comparisons">{(['away','home'] as const).map(side=>{
        const comparison=pair&&p?priceComparison(p[side],Number(pair[side].decimal_odds)):null;
        return <div className="edge-row" key={side}><div><span>{f[side]} edge</span><b className={comparison&&comparison.edge>=0?'positive':'negative'}>{comparison?`${comparison.edge>=0?'+':''}${(comparison.edge*100).toFixed(1)} pp`:'—'}</b></div><input type="range" min="-100" max="100" step="0.1" value={comparison?comparison.edge*100:0} disabled aria-label={`${f[side]} probability edge${comparison?'':' unavailable'}`} className={comparison?'':'unknown-range'}/><small>Model fair odds {odds(comparison?.fair_odds)} · {comparison?'Model probability minus price break-even probability.':'Requires both a forecast and a saved PlayNow price.'}</small>{comparison&&<small>Estimated return {comparison.expected_return>=0?'+':''}{(comparison.expected_return*100).toFixed(1)}% per unit staked · depends on the model estimate{pair?.stale?' and an expired price':''}.</small>}</div>;
      })}</div>
      <div className="daily-card-footer"><span>{f.reason}</span><button className="outline-button" onClick={()=>onOpen(f)}>Stats & market detail ↗</button></div>
    </article>;
  })}{!fixtures.length&&<div className="table-empty"><h3>No matches on this date</h3><p>Choose another date or clear the watchlist filters. The shared NHL feed supplies scheduled games.</p></div>}</div>;
}
