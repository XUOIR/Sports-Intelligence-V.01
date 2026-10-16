'use client';
import type {PaperResults} from '@/lib/types';
import {pacificTime} from '@/lib/time.mjs';
import './PaperResearch.css';

const percent=(value:string|null,digits=1)=>value===null?'—':`${(Number(value)*100).toFixed(digits)}%`;
const edge=(value:string)=>`${Number(value)>=0?'+':''}${(Number(value)*100).toFixed(2)} pp`;
export default function PaperResearch({results}:{results:PaperResults}){
  // Show saved forecasts before future fixtures awaiting their match day.
  const records=[...results.records].sort((a,b)=>Number(Boolean(b.captured_at))-Number(Boolean(a.captured_at))
    || (a.captured_at&&b.captured_at?b.start_at.localeCompare(a.start_at):a.start_at.localeCompare(b.start_at))
    || a.fixture_id.localeCompare(b.fixture_id));
  return <section className="paper-research market-panel" aria-label="NHL Paper Research">
    <div className="market-heading"><h2>NHL Paper Research</h2><span className="badge hold">PAPER ONLY</span></div>
    <p className="fine-print">{results.note} Expected or unknown starters are permitted in this team-only model; no goalie adjustment is applied.</p>
    <div className="metrics-grid">
      <div className="metric-card"><div className="metric-label">FORWARD FORECASTS</div><strong>{results.forecasts}</strong><p>{results.fixtures_seen} fixtures seen · {results.blocked} awaiting eligible inputs</p></div>
      <div className="metric-card"><div className="metric-label">MATCHED PLAYNOW PRICES</div><strong>{results.matched_prices}</strong><p>{results.resolved_pairs} forecast/price pairs resolved</p></div>
      <div className="metric-card"><div className="metric-label">PAPER POSITIONS</div><strong>{results.positions}</strong><p>{results.settled_positions} settled · {results.void_positions} void · one simulated unit each</p></div>
      <div className="metric-card"><div className="metric-label">PAPER RETURN</div><strong>{results.roi_percent===null?'—':`${Number(results.roi_percent).toFixed(2)}%`}</strong><p>{Number(results.profit_units).toFixed(2)} simulated units · separate from Bankroll</p></div>
    </div>
    <p className="fine-print">Model Brier: {results.brier===null?'awaiting results':Number(results.brier).toFixed(4)}. On the same priced games: model {results.paired_model_brier===null?'—':Number(results.paired_model_brier).toFixed(4)}, margin-adjusted market {results.paired_market_brier===null?'—':Number(results.paired_market_brier).toFixed(4)}. Lower is better.</p>
    <p className="fine-print">Forecasts freeze on match day before puck drop. Paper positions require both PlayNow prices to be at most five minutes old and an edge of at least +3 percentage points. The first qualifying observation is saved; there is no daily pick quota. Saved price edges below are historical observations, not current offers.</p>
    {results.history_error&&<p className="notice" role="status">The official history refresh did not complete ({results.history_error}). Incomplete inputs remain blocked; saved forecasts and results are preserved.</p>}
    <div className="table-scroll"><table><thead><tr><th>MATCHUP / PT</th><th>HOME / AWAY PROBABILITY</th><th>SAVED PLAYNOW / EDGE</th><th>PAPER DECISION</th><th>RESULT</th></tr></thead><tbody>{records.map(row=><tr key={row.fixture_id}>
      <td>{row.away} at {row.home}<small>{pacificTime(row.start_at)}</small></td>
      <td>{row.home_probability===null?'Awaiting inputs':`${percent(row.home_probability)} / ${percent(String(1-Number(row.home_probability)))}`}<small>{row.captured_at?`Saved ${pacificTime(row.captured_at)} PT`:row.issue}</small></td>
      <td>{row.prices?<><span>{row.home}: {Number(row.prices.home_odds).toFixed(3)} · {edge(row.prices.home_edge)}</span><small>{row.away}: {Number(row.prices.away_odds).toFixed(3)} · {edge(row.prices.away_edge)}</small><small>Observed {pacificTime(row.prices.source_at)} PT</small></>:'No eligible paired price captured'}</td>
      <td>{row.position?<>{row.position.selection}<small>1 simulated unit at {Number(row.position.odds).toFixed(3)} · {edge(row.position.edge)}</small></>:row.captured_at?'No qualifying paper position':'Awaiting eligible inputs'}</td>
      <td>{row.resolution==='VOID'?'Void / schedule changed':row.resolution==='FINAL'?(row.position?(row.result_home_win===row.position.home?'Paper win':'Paper loss'):(row.result_home_win?row.home:row.away)+' won'):'Awaiting result'}</td>
    </tr>)}</tbody></table></div>
    {!results.records.length&&<div className="table-empty"><h3>Forward Collection Is Ready</h3><p>Upcoming regular-season games will be enrolled automatically. No historical prediction is backfilled into this ledger.</p></div>}
    <p className="fine-print">Candidate {results.model_version} · {results.last_collection_at?`Last collection ${pacificTime(results.last_collection_at)} PT`:'Awaiting the first collection'}. The first workflow review needs 14 days and 100 resolved price pairs. This does not approve real-money use.</p>
  </section>;
}
