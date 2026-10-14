import test from 'node:test';
import assert from 'node:assert/strict';
import {moneylinePair,probabilities,priceComparison,noVig} from '../lib/market.mjs';
const at=Date.parse('2026-10-14T20:00:00Z'),fixture={home:'Home',away:'Away',selection:'Home',probability:'.6'};
const quote=(selection,bookmaker='playnow',source_at=new Date(at).toISOString())=>({selection,bookmaker,source_at,market:'h2h',line:null,decimal_odds:'2'});
test('prices survive expiry but cannot appear current, future or from another market',()=>{
  assert.equal(moneylinePair(fixture,[quote('Home'),quote('Away')],at+300001).stale,true);
  assert.equal(moneylinePair(fixture,[quote('Home'),quote('Away')],at-1),null);
  assert.equal(moneylinePair(fixture,[quote('Home'),{...quote('Away'),market:'totals',line:'5.5'}],at),null);
});
test('never mixes bookies, incomplete pairs or different quote timestamps',()=>{
  assert.equal(moneylinePair(fixture,[quote('Home'),quote('Away','pinnacle')],at),null);
  assert.equal(moneylinePair(fixture,[quote('Home'),quote('Away','playnow',new Date(at-1000).toISOString())],at),null);
  assert.equal(moneylinePair(fixture,[quote('Home','pinnacle'),quote('Away','pinnacle')],at),null);
  assert.equal(moneylinePair(fixture,[quote('Home','pinnacle'),quote('Away','pinnacle')],at,['pinnacle']).book,'pinnacle');
});
test('both selected-side orientations produce complementary win probabilities',()=>{
  assert.deepEqual(probabilities(fixture),{home:.6,away:.4});
  assert.deepEqual(probabilities({...fixture,selection:'Away'}),{home:.4,away:.6});
  for(const probability of [null,'',NaN,'1.1'])assert.equal(probabilities({...fixture,probability}),null);
  assert.equal(probabilities({...fixture,selection:'Other'}),null);
});
test('edge is signed probability points, and fair odds use the model probability',()=>{
  assert.ok(Math.abs(priceComparison(.6,2).edge-.1)<1e-10);
  assert.ok(Math.abs(priceComparison(.4,2).edge+.1)<1e-10);
  assert.equal(priceComparison(.5,2).fair_odds,2);
  assert.ok(Math.abs(priceComparison(.65,1.8).expected_return-.17)<1e-10);
  assert.ok(Math.abs(priceComparison(.65,1.8).edge-(.65-1/1.8))<1e-10);
  assert.equal(priceComparison(null,2),null);
  assert.equal(priceComparison(.6,0),null);
});
test('market benchmark removes margin without claiming a model forecast',()=>{
  const p=noVig({home:{decimal_odds:'1.8'},away:{decimal_odds:'2'}});
  assert.ok(Math.abs(p.home+p.away-1)<1e-10);
  assert.ok(Math.abs(p.home-(1/1.8)/(1/1.8+1/2))<1e-10);
  assert.equal(noVig(null),null);
  assert.equal(noVig({home:{decimal_odds:'bad'},away:{decimal_odds:'2'}}),null);
});
