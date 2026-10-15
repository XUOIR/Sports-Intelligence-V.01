'use client';
import type {Performance as Results} from '@/lib/types';
const dollars=(value:string)=>new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD'}).format(Number(value));

export default function Performance({results}:{results?:Results}){
  const curve=results?.curve||[],values=[0,...curve.map(p=>Number(p.profit))];
  const min=Math.min(0,...values),max=Math.max(0,...values),span=max-min||1;
  const points=values.map((value,i)=>`${(i/Math.max(values.length-1,1)*600).toFixed(1)},${(112-(value-min)/span*90).toFixed(1)}`);
  return <section className="performance-card" aria-label="Recorded performance">
    <div className="card-heading"><div><span className="eyebrow">THE TRACK RECORD</span><h2>Performance</h2></div><span className="badge">RECORDED WAGERS</span></div>
    <p className="card-description">Your actual tickets. Your actual returns.</p>
    <div className="performance-stats"><div><span>Record <small>W–L–P</small></span><strong>{results?`${results.wins}–${results.losses}–${results.pushes}`:'—'}</strong></div><div><span>Win rate</span><strong>{results?.win_rate!==null&&results?.win_rate!==undefined?`${results.win_rate}%`:'—'}</strong></div><div><span>ROI</span><strong className="gradient-text">{results?.roi!==null&&results?.roi!==undefined?`${Number(results.roi)>0?'+':''}${results.roi}%`:'—'}</strong></div></div>
    <div className="performance-chart">{curve.length?<figure><svg viewBox="0 0 600 132" role="img" aria-label={`Cumulative settled profit ${dollars(results!.profit)}`} preserveAspectRatio="none"><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity=".24"/><stop offset="100%" stopColor="#3b82f6" stopOpacity="0"/></linearGradient><linearGradient id="chart-line"><stop stopColor="#22d3ee"/><stop offset="100%" stopColor="#8b5cf6"/></linearGradient></defs>{[22,67,112].map(y=><line key={y} x1="0" x2="600" y1={y} y2={y} stroke="#ffffff0d"/>)}<polygon points={`0,132 ${points.join(' ')} 600,132`} fill="url(#chart-fill)"/><polyline points={points.join(' ')} fill="none" stroke="url(#chart-line)" strokeWidth="2.5" vectorEffect="non-scaling-stroke"/></svg><figcaption><span>{curve[0].date}</span><b>{dollars(results!.profit)} cumulative profit</b><span>{curve.at(-1)!.date}</span></figcaption></figure>:<div className="chart-empty"><span className="chart-orbit">↗</span><strong>Your track record starts here.</strong><span>Settle a recorded wager to see your performance curve.</span></div>}</div>
    <div className="performance-notes"><span>{results?.settled||0} settled · {results?.pending||0} open · {results?.voids||0} void</span><span>All-time · CAD</span></div>
    <p className="fine-print">Win rate excludes pushes and voids. ROI uses settled stakes. The curve follows each ticket’s latest settlement update.</p>
    <div className="model-validation"><span>Model accuracy <b>{results?.model.accuracy!=null?`${results.model.accuracy}%`:'—'}</b></span><span>Brier score <b>{results?.model.brier??'—'}</b></span><small>{results?.model.evaluated||0} resolved model forecasts</small></div>
  </section>;
}
