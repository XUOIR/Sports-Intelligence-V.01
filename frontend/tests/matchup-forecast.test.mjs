import test from 'node:test';
import assert from 'node:assert/strict';
import {matchupForecast} from '../lib/matchup-forecast.mjs';
import {moneylinePair,priceComparison} from '../lib/market.mjs';

const at=Date.parse('2026-10-16T22:00:00Z');
const fixture={id:'nhl:2026020119',sport:'NHL',home:'Colorado Avalanche',away:'Pittsburgh Penguins',
  commence_time:'2026-10-17T01:00:00Z',probability:null,selection:null,state:'HOLD',suggested_stake:'0'};
const record={fixture_id:fixture.id,home:fixture.home,away:fixture.away,start_at:fixture.commence_time,
  captured_at:'2026-10-16T10:00:28Z',home_probability:'0.5811841720',resolution:null,
  position:{selection:fixture.away,odds:'2.75'}};
const paper={mode:'paper_only',approved_for_wagers:false,model_version:'nhl-team-paper-v2-test',records:[record]};

test('saved research favors Colorado independently of a Pittsburgh paper value position',()=>{
  const before=structuredClone({fixture,paper});
  const p=matchupForecast(fixture,paper,at);
  assert.equal(p.source,'paper');
  assert.equal(p.home,.581184172);
  assert.equal(p.home+p.away,1);
  assert.ok(p.home>p.away);
  assert.equal(p.captured_at,record.captured_at);
  assert.deepEqual({fixture,paper},before); // Never promotes research into wager fields.
});

test('saved PlayNow comparisons show the opposite price-value side and remain expired',()=>{
  const quotes=[['Colorado Avalanche','1.47'],['Pittsburgh Penguins','2.75']].map(([selection,decimal_odds])=>({
    selection,decimal_odds,bookmaker:'playnow',market:'h2h',line:null,source_at:'2026-10-16T21:58:16Z'}));
  const p=matchupForecast(fixture,paper,at),pair=moneylinePair(fixture,quotes,at+600000);
  assert.equal(pair.stale,true);
  assert.ok(Math.abs(priceComparison(p.home,Number(pair.home.decimal_odds)).edge-(-.0990879368435374))<1e-10);
  assert.ok(Math.abs(priceComparison(p.away,Number(pair.away.decimal_odds)).edge-.0551794643636364)<1e-10);
  const moved=quotes.map(q=>({...q,decimal_odds:'1.5'}));
  assert.ok(priceComparison(p.away,Number(moneylinePair(fixture,moved,at).away.decimal_odds)).edge<0);
  assert.deepEqual(matchupForecast(fixture,paper,at),p); // Prices cannot move the forecast.
});

test('research cannot cross fixture, team, schedule or sport boundaries',()=>{
  for(const patch of [{id:'another'},{home:fixture.away,away:fixture.home},
    {commence_time:'2026-10-17T01:10:00Z'},{sport:'CS2'}]){
    assert.equal(matchupForecast({...fixture,...patch},paper,at),null);
  }
  assert.equal(matchupForecast(fixture,{...paper,records:[{...record,resolution:'VOID'}]},at),null);
});

test('missing, invalid, future or post-start forecasts never populate the bars',()=>{
  assert.equal(matchupForecast(fixture,undefined,at),null);
  for(const home_probability of [null,undefined,'','NaN','Infinity','1.01','-.01']){
    assert.equal(matchupForecast(fixture,{...paper,records:[{...record,home_probability}]},at),null);
  }
  for(const captured_at of [null,'bad','2026-10-16T22:01:00Z',record.start_at,'2026-10-17T02:00:00Z']){
    assert.equal(matchupForecast(fixture,{...paper,records:[{...record,captured_at}]},at),null);
  }
  for(const patch of [{mode:'live'},{approved_for_wagers:true},{records:[]}]){
    assert.equal(matchupForecast(fixture,{...paper,...patch},at),null);
  }
});

test('an existing saved model forecast retains precedence and correct orientation',()=>{
  const p=matchupForecast({...fixture,selection:fixture.away,probability:'.4'},paper,at);
  assert.equal(p.source,'model');
  assert.deepEqual([p.home,p.away],[.6,.4]);
  assert.equal(p.model_version,null);
});
