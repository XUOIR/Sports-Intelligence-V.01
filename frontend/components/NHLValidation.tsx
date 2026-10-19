import type {ForwardValidation,ForwardCohort,StarterGrade} from '@/lib/types';
import {pacificTime} from '@/lib/time.mjs';
import './NHLValidation.css';

const number=(value:number|null,digits=4)=>value==null?'—':value.toFixed(digits);
const percent=(value:number|null)=>value==null?'—':`${(value*100).toFixed(1)}%`;
const signed=(value:number)=>`${value>=0?'+':''}${(value*100).toFixed(2)} pp`;
const starterLabels:Record<string,string>={matched:'Correct starter',mismatched:'Different starter',
  stale:'Observation expired at cutoff',not_observed_before_cutoff:'No pregame observation',
  source_removed:'Report removed before cutoff',unconfirmed_or_unmatched:'Unconfirmed or unmatched'};
const starterGrade=(row:StarterGrade)=>starterLabels[row.status]||'Awaiting verification';

export default function NHLValidation({data}:{data:ForwardValidation}){
  const {baseline,candidate,candidate_info:info,starters}=data;
  const models:[string,ForwardCohort][]=[['Current Baseline',baseline],...(candidate?[['xG Candidate',candidate] as [string,ForwardCohort]]:[])];
  const metrics:{label:string;value:(r:ForwardCohort)=>string|number}[]=[
    {label:'Forecasts Saved',value:r=>r.forecasts},{label:'Resolved Games',value:r=>r.resolved},
    {label:'Winner Accuracy',value:r=>percent(r.scores.accuracy)},
    {label:'Brier Score · Lower Is Better',value:r=>number(r.scores.brier)},
    {label:'Log Loss · Lower Is Better',value:r=>number(r.scores.log_loss)},
    {label:'Resolved PlayNow Pairs',value:r=>r.resolved_price_pairs},
    {label:'Brier On Those Priced Games',value:r=>number(r.paired_model.brier)},
    {label:'Market Brier On The Same Games',value:r=>number(r.paired_market.brier)},
    {label:'Settled Paper Positions',value:r=>r.settled_positions},
    {label:'Paper Return · One Unit Each',value:r=>r.roi_percent==null?'—':`${r.roi_percent.toFixed(2)}%`},
    {label:'Closing Value · Observed Pairs',value:r=>r.mean_closing_value_percent==null?'—':`${r.mean_closing_value_percent.toFixed(2)}% · ${r.closing_pairs} pairs`}
  ];
  return <div className="nhl-validation">
    <section className="market-panel" aria-label="Forward model validation">
      <div className="market-heading"><h2>Forward Model Validation</h2><span className="badge hold">PAPER ONLY</span></div>
      <p className="fine-print">The baseline uses ratings, rest and back-to-backs. The separate candidate also uses prior-game 5v5 xG and team goaltending form. Neither model uses sportsbook prices as prediction inputs. Named starter reports remain context; no individual goalie adjustment is claimed.</p>
      <div className="table-scroll"><table><thead><tr><th>MEASURE</th>{models.map(([label])=><th key={label}>{label.toUpperCase()}</th>)}</tr></thead>
        <tbody>{metrics.map(metric=><tr key={metric.label}><td>{metric.label}</td>{models.map(([label,row])=><td key={label}>{metric.value(row)}</td>)}</tr>)}</tbody></table></div>
      <p className="fine-print">Prices are compared only on the same games with a genuinely saved forecast and a fresh two-sided PlayNow observation. Closing value uses the last eligible saved prices in the final five minutes before scheduled puck drop; missing closing observations stay blank. Paper returns never change Bankroll.</p>
      <div className="validation-checkpoints">{models.map(([label,row])=><p className="fine-print" key={label}><b>{label}:</b> {row.days_collecting.toFixed(1)} / 14 collection days · {row.resolved_price_pairs} / 100 resolved price pairs. {row.operational_review_ready?'Ready for a workflow review.':'Collecting forward evidence.'} These checkpoints do not approve real-money use.</p>)}</div>
      {info&&<details className="validation-research"><summary>Historical Candidate Comparison</summary>
        <p className="fine-print">On {info.research.partitions.test.toLocaleString()} historical comparison games, Brier was {info.research.scores.team_only.brier.toFixed(4)} for the team-only comparator and {info.research.scores.xg_goaltending.brier.toFixed(4)} for the candidate. Log loss was {info.research.scores.team_only.log_loss.toFixed(4)} versus {info.research.scores.xg_goaltending.log_loss.toFixed(4)}.</p>
        <p className="fine-print">The paired Brier improvement was {info.research.paired_improvement.estimate.toFixed(4)}; exploratory 95% week-block interval {info.research.paired_improvement.percentile_95_low.toFixed(4)} to {info.research.paired_improvement.percentile_95_high.toFixed(4)}. Historical source versions were downloaded recently, and these seasons were examined in earlier research. This supports forward testing and does not demonstrate a sportsbook edge.</p>
        <p className="fine-print">Candidate frozen {pacificTime(info.created_at)} PT. {candidate?.version}</p>
      </details>}
      {data.candidate_error&&<p className="notice" role="status">{data.candidate_error}</p>}
    </section>

    <section className="market-panel" aria-label="Probability calibration">
      <div className="market-heading"><h2>Probability Calibration</h2><span className="muted">Saved predictions graded after finals</span></div>
      <p className="fine-print">For example, forecasts around 60% should win about 60% of the time over a large sample. These home-team probability groups show the actual sample size and a 95% interval for the observed win rate. Small samples remain uncertain.</p>
      <div className="table-scroll"><table><thead><tr><th>MODEL / GROUP</th><th>GAMES</th><th>MEAN FORECAST</th><th>HOME WINS</th><th>95% INTERVAL</th></tr></thead><tbody>
        {models.flatMap(([label,row])=>row.calibration.map(bin=><tr key={`${label}:${bin.lower}`}><td>{label}<small>{Math.round(bin.lower*100)}–{Math.round(bin.upper*100)}%</small></td><td>{bin.games}</td><td>{percent(bin.mean_probability)}</td><td>{percent(bin.observed_home_win_rate)}</td><td>{percent(bin.wilson_low)}–{percent(bin.wilson_high)}</td></tr>))}
      </tbody></table></div>
      {!models.some(([,row])=>row.calibration.length)&&<p className="fine-print">Awaiting genuinely resolved forecasts.</p>}
    </section>

    {candidate&&<section className="market-panel" aria-label="xG candidate forecasts">
      <div className="market-heading"><h2>xG Candidate Forecasts</h2><span className="badge watch">SEPARATE COHORT</span></div>
      <p className="fine-print">Every forecast below was saved at its actual pregame collection time. Five prior games are required for each statistics window. The original baseline forecasts remain intact. Saved edges describe the price at observation time, not a current offer.</p>
      <div className="table-scroll validation-candidate-table" tabIndex={0} aria-label="Scrollable candidate forecast history"><table><thead><tr><th>MATCHUP / PT</th><th>HOME / AWAY</th><th>SAVED PLAYNOW / EDGE</th><th>PAPER DECISION</th><th>RESULT</th></tr></thead><tbody>
        {[...candidate.records].sort((a,b)=>Number(Boolean(b.captured_at))-Number(Boolean(a.captured_at))||a.start_at.localeCompare(b.start_at)).map(row=><tr key={row.fixture_id}>
          <td>{row.away} at {row.home}<small>{pacificTime(row.start_at)} PT</small></td>
          <td>{row.home_probability==null?'Awaiting inputs':`${percent(Number(row.home_probability))} / ${percent(1-Number(row.home_probability))}`}<small>{row.captured_at?`Saved ${pacificTime(row.captured_at)} PT`:row.issue}</small></td>
          <td>{row.prices?<>{row.home}: {row.prices.home_odds.toFixed(2)} · {signed(row.prices.home_edge)}<small>{row.away}: {row.prices.away_odds.toFixed(2)} · {signed(row.prices.away_edge)}</small><small>Source {pacificTime(row.prices.source_at)} PT</small></>:'No eligible fresh price pair observed'}</td>
          <td>{row.position?<>{row.position.selection}<small>1 simulated unit at {Number(row.position.odds).toFixed(2)}</small></>:row.captured_at?(row.prices?'No qualifying paper position':'Awaiting fresh prices'):'Awaiting eligible inputs'}</td>
          <td>{row.resolution==='VOID'?'Void / schedule changed':row.resolution==='FINAL'?(row.position?(row.result_home_win===row.position.home?'Paper win':'Paper loss'):`${row.result_home_win?row.home:row.away} won`):'Awaiting result'}</td>
        </tr>)}
      </tbody></table></div>
    </section>}

    <section className="market-panel" aria-label="Goalie feed validation">
      <div className="market-heading"><h2>Goalie Feed Validation</h2><span className="badge watch">SOURCE TEST</span></div>
      <div className="metrics-grid">
        <div className="metric-card"><div className="metric-label">UPCOMING GAMES OBSERVED</div><strong>{starters.upcoming_games_observed}</strong><p>Reports actually collected before puck drop</p></div>
        <div className="metric-card"><div className="metric-label">OFFICIAL FINALS CHECKED</div><strong>{starters.completed_games_checked}</strong><p>{starters.unavailable_checks} unavailable checks · failures are not automatically retried</p></div>
        <div className="metric-card"><div className="metric-label">CONFIRMED REPORT ACCURACY</div><strong>{percent(starters.confirmed.accuracy)}</strong><p>{starters.confirmed.correct} / {starters.confirmed.graded_sides} graded starting goalies</p></div>
        <div className="metric-card"><div className="metric-label">EXPECTED REPORT ACCURACY</div><strong>{percent(starters.expected.accuracy)}</strong><p>{starters.expected.correct} / {starters.expected.graded_sides} graded starting goalies</p></div>
      </div>
      <p className="fine-print">{starters.at_t30.correct} / {starters.at_t30.graded_sides} eligible goalie reports matched at T−30; {starters.at_t30.missing_or_stale} team sides lacked a fresh eligible report at that checkpoint. The last pregame check matched {starters.last_pregame.correct} / {starters.last_pregame.graded_sides}. Late, stale, unconfirmed or unmatched observations do not count as correct predictions.</p>
      <p className="fine-print">For {starters.new_report_age.samples} new reports dated after this pilot started, source age at first observation was median {number(starters.new_report_age.median_minutes,1)} minutes; 95th percentile {number(starters.new_report_age.p95_minutes,1)} minutes. This uses the site's update timestamp and does not measure the original reporter's publication latency.</p>
      <div className="table-scroll"><table><thead><tr><th>GAME / PT</th><th>ACTUAL STARTER</th><th>T−30 REPORT</th><th>LAST PREGAME REPORT</th></tr></thead><tbody>
        {starters.records.flatMap(row=>(['away','home'] as const).map(side=><tr key={`${row.fixture_id}:${side}`}><td>{side==='home'?row.home:row.away}<small>{pacificTime(row.start_at)} PT</small></td><td>{row.sides[side].name}</td><td>{starterGrade(row.at_t30[side])}</td><td>{starterGrade(row.last_pregame[side])}</td></tr>))}
      </tbody></table></div>
      <p className="fine-print">{starters.note} A source-only test does not approve a model or a play.</p>
    </section>
  </div>;
}
