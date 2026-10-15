// Stored two-outcome moneyline comparisons only. No provider requests or writes.
export function moneylinePair(fixture,quotes=[],now=Date.now(),books=['playnow','bclc']){
  for(const book of books){
    const latest=new Map();
    for(const q of quotes){
      const at=Date.parse(q.source_at);
      if(q.bookmaker!==book||q.market!=='h2h'||q.line!==null||!Number.isFinite(at)||![fixture.home,fixture.away].includes(q.selection))continue;
      if(!latest.has(q.selection)||at>Date.parse(latest.get(q.selection).source_at))latest.set(q.selection,q);
    }
    const home=latest.get(fixture.home),away=latest.get(fixture.away);
    if(!home||!away||Date.parse(home.source_at)!==Date.parse(away.source_at))continue;
    const at=Date.parse(home.source_at);
    if(at>now||![home,away].every(q=>Number.isFinite(Number(q.decimal_odds))&&Number(q.decimal_odds)>1.0001))continue;
    return {book,home,away,source_at:home.source_at,stale:now-at>300000};
  }
  return null;
}
export function probabilities(fixture){
  const raw=fixture.probability,p=Number(raw);
  if(raw===null||raw===undefined||raw===''||!Number.isFinite(p)||p<0||p>1||![fixture.home,fixture.away].includes(fixture.selection))return null;
  const home=fixture.selection===fixture.home?p:1-p;return {home,away:1-home};
}
export function priceComparison(probability,price){
  if(probability===null||probability===undefined||!Number.isFinite(probability)||probability<0||probability>1||!Number.isFinite(price)||price<=1.0001)return null;
  return {implied:1/price,edge:probability-1/price,fair_odds:probability>0?1/probability:null,expected_return:probability*price-1};
}
export function noVig(pair){
  if(!pair)return null;
  const h=Number(pair.home.decimal_odds),a=Number(pair.away.decimal_odds);
  if(!Number.isFinite(h)||!Number.isFinite(a)||h<=1.0001||a<=1.0001)return null;
  const total=1/h+1/a;return {home:(1/h)/total,away:(1/a)/total};
}
