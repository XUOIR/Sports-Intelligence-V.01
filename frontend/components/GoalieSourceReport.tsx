import type {GoalieSourceReport as Report} from '@/lib/types';
import {pacificTime} from '@/lib/time.mjs';

const comparison={matches_manual:'Matches your manual confirmation',conflicts_manual:'Differs from your manual confirmation — review required',manual_expired:'Your manual confirmation expired',no_manual_confirmation:'No current manual confirmation',source_unconfirmed:'No current confirmed source report'};

export default function GoalieSourceReport({report,clock,home,away}:{report?:Report|null;clock:number;home:string;away:string}){
  if(!report||report.status==='missing')return <p className="nhl-statistics-note">Daily Faceoff Test Feed: no matched report saved yet. Start or inspect the test in Settings.</p>;
  const fresh=report.status==='fresh'&&!!report.observed_at&&!!report.valid_until&&Date.parse(report.observed_at)<=clock&&clock<=Date.parse(report.valid_until);
  return <aside className="goalie-source-report" aria-label="Daily Faceoff test reports">
    <div className="nhl-statistics-heading"><h4>Daily Faceoff Test Feed</h4><span className="badge watch">{fresh?'SOURCE REPORTS':'LAST SAVED REPORTS'}</span></div>
    {(['away','home'] as const).map(side=>{
      const row=report.sides[side];if(!row)return null;
      return <div key={side} className="account-readout"><b>{side==='home'?home:away}: {row.name||'No named starter'}</b>
        <span>{row.reported_status==='confirmed'?'Reported Confirmed':row.reported_status==='expected'?'Reported Expected':'Unconfirmed'}</span>
        <small>{row.reported_at?`Source updated ${pacificTime(row.reported_at)} PT. `:''}{row.player_id?'Matched to a saved NHL player ID.':'NHL player ID needs a match.'}</small>
        <small>{fresh?comparison[row.comparison]:'Source observation expired or report removed; recheck required.'}</small>
        {row.reporter_url&&<a className="text-button" href={row.reporter_url} target="_blank" rel="noreferrer">Reporter Reference ↗</a>}
      </div>;
    })}
    <p className="nhl-statistics-note">{report.observed_at?`Checked ${pacificTime(report.observed_at)} PT. `:''}{report.pregame===false?'Observed after the game started; review only. ':''}Test reports leave your selections and verification gates unchanged.</p>
    {report.source_url&&<a className="text-button" href={report.source_url} target="_blank" rel="noreferrer">Daily Faceoff Source ↗</a>}
  </aside>;
}
