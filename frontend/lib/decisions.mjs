export const decisionLabels={WATCH:'AWAITING REVIEW',HOLD:'NEEDS VERIFICATION',PASS:'NO QUALIFYING EDGE',RECOMMEND:'VERIFIED PLAY'};
export function decisionLabel(state){return decisionLabels[state]||'NEEDS VERIFICATION';}
export function decisionExplanation(state,reason){
  if(state==='PASS')return 'Validated edge is below the 3 percentage-point minimum.';
  const checks={'price':'current PlayNow odds','personnel':'confirmed starting goalies','form':'recent form',
    'maps veto':'map/veto review','other markets':'spread and total review','opposing case':'opposing-case review',
    'overlap exposure':'exposure approval','probability':'a validated forecast'};
  const parts=String(reason||'').split(';').map(s=>s.trim());
  if(parts.length&&parts.every(s=>checks[s]))return 'Needs '+parts.map(s=>checks[s]).join(', ')+'.';
  return reason||(state==='WATCH'?'Awaiting enough current data for a verified decision.':'Verification is incomplete.');
}
