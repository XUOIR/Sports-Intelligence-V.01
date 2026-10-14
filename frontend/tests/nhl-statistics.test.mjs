import test from 'node:test';
import assert from 'node:assert/strict';
import {teamXg,xgDifference,nhlLogo} from '../lib/nhl-statistics.mjs';
const metrics={status:'available',sample_games:6,latest_game_date:'2026-10-13',xg_share:'.549'};
test('real xG shares retain their samples and are separate from betting probabilities',()=>{
  const away=teamXg(metrics),home=teamXg({...metrics,xg_share:'.506'});
  assert.deepEqual(away,{share:.549,sample:6,latest:'2026-10-13'});
  assert.ok(Math.abs(xgDifference(home,away)-4.3)<1e-10);
  assert.ok(Math.abs(xgDifference(away,home)+4.3)<1e-10);
  assert.notEqual(home.share+away.share,1);
  assert.equal(xgDifference(home,null),null);
});
test('no invented values for missing, invalid, small sample or postgame statistics',()=>{
  for(const xg_share of [null,undefined,'',' ',false,NaN,'Infinity','1.01','-.01'])assert.equal(teamXg({...metrics,xg_share}),null);
  for(const sample_games of [0,2,3.5,'6'])assert.equal(teamXg({...metrics,sample_games}),null);
  for(const status of ['insufficient_sample','not_pre_game','pending'])assert.equal(teamXg({...metrics,status}),null);
  assert.equal(teamXg(null),null);
  assert.equal(teamXg({...metrics,xg_share:'0'}).share,0);
});
test('logos use only official NHL assets and reject unknown or injected paths',()=>{
  assert.equal(nhlLogo('MTL'),'https://assets.nhle.com/logos/nhl/svg/MTL_dark.svg');
  assert.equal(nhlLogo('WSH'),'https://assets.nhle.com/logos/nhl/svg/WSH_dark.svg');
  for(const code of [null,undefined,'QA','mtl','../../MTL','https://attacker.test','MTL?key=private'])assert.equal(nhlLogo(code),null);
});
