import {isStale} from './activity.mjs';
import {moneylinePair} from './market.mjs';
export function verificationExpired(detail,now=Date.now()){
  const data=detail.verification;
  return !data||isStale(data.checked_at,now)||Date.parse(detail.fixture.commence_time)<=now
    ||data.phase==='waiting_for_anchor'&&Date.parse(data.anchor_at)<=now;
}
export function gateStatus(check,detail,now=Date.now()){
  if(check.status!=='passed')return check.status;
  if(verificationExpired(detail,now)||detail.fixture.dirty)return 'blocked';
  if(check.key==='price'){const pair=moneylinePair(detail.fixture,detail.odds,now);if(!pair||pair.stale)return 'blocked';}
  if(['personnel','other_markets','opposing_case'].includes(check.key)){
    const at=Date.parse(detail.fixture.metrics.confirmed_at);
    if(!Number.isFinite(at)||at>now||now-at>1800000)return 'blocked';
  }
  return 'passed';
}
