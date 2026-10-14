import type {Operations as Status} from '@/lib/types';
import {pacificTime} from '@/lib/time.mjs';
const dollars=(value:string|null|undefined,unknown='Not checked')=>value==null?unknown:`US$${new Intl.NumberFormat('en-CA',{minimumFractionDigits:2,maximumFractionDigits:6}).format(Number(value))}`;
export default function AISpending({status}:{status:Status}){
  const actual=status.ai_actual_usage;
  const unknown=actual?.checked_at?'Unavailable':'Not checked';
  return <div className="ai-spending" aria-label="AI spending and limits"><div><b>OpenRouter spending · this key</b><span>{dollars(actual?.daily_usd,unknown)} <small>current UTC day</small></span><span>{dollars(actual?.monthly_usd,unknown)} <small>current UTC month</small></span><p>{actual?.checked_at?`Checked ${pacificTime(actual.checked_at)} PT${actual.status==='stale'?' · needs a new check':''}`:'Use “Check provider allowances” for actual usage.'}</p></div><div><b>App budget reserved</b><span>{dollars(status.ai_daily_reserved_usd)} <small>today · Pacific time</small></span><span>{dollars(status.ai_monthly_reserved_usd)} <small>this month · Pacific time</small></span><p>Reservations protect against pending, failed or uncertain calls. They are not a bill.</p></div><div><b>Hard spending limits</b><span>{dollars(status.ai_daily_cap_usd)} <small>maximum per day</small></span><span>{dollars(status.ai_monthly_cap_usd)} <small>maximum per month</small></span><p>The monthly ceiling applies across all days. Limits are not spending targets.</p></div></div>;
}
