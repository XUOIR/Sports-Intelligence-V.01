import {test} from 'node:test';
import assert from 'node:assert/strict';
import {shiftDay,matchTime,matchAge,feedExpired,playVisible} from '../lib/matches.mjs';
test('date navigation crosses month and year boundaries',()=>{assert.equal(shiftDay('2026-12-31',1),'2027-01-01');assert.equal(shiftDay('2026-03-01',-1),'2026-02-28');});
test('score ages use observation time and do not advance the game clock',()=>{assert.equal(matchAge('2026-10-13T20:00:00Z',Date.parse('2026-10-13T20:00:27Z')),'Updated 27s ago');assert.equal(matchTime('2026-10-13T19:30:00-07:00'),'7:30 p.m.');});
test('play badge disappears when freshness expires or a game starts',()=>{
  const at=Date.parse('2026-10-13T20:00:00Z'),feed={stale:false,valid_until:new Date(at+90000).toISOString()},game={verified_play:true,decision:'RECOMMEND',game_state:'FUT',schedule_state:'OK',commence_time:new Date(at+60000).toISOString()};
  assert.equal(playVisible(game,feed,at),true);assert.equal(playVisible(game,feed,at+60000),false);
  assert.equal(playVisible({...game,game_state:'LIVE'},feed,at),false);assert.equal(playVisible({...game,schedule_state:'PPD'},feed,at),false);
  assert.equal(playVisible(game,{...feed,stale:true},at),false);assert.equal(feedExpired(feed,at+90001),true);
});
