import test from 'node:test';
import assert from 'node:assert/strict';
import {starterStatus,selectedGoaliePair} from '../lib/starters.mjs';
test('confirmation and projections lose their badges when the saved evidence expires',()=>{
  const now=Date.parse('2026-10-14T19:00:00Z');
  const data={checked_at:new Date(now).toISOString(),projection_valid_until:new Date(now+7200000).toISOString()};
  const row={status:'confirmed',confirmed_at:new Date(now).toISOString()};
  assert.equal(starterStatus(row,data,now),'confirmed');
  assert.equal(starterStatus(row,data,now+1800001),'unknown');
  assert.equal(starterStatus({...row,status:'projected'},data,now),'projected');
  assert.equal(starterStatus({...row,status:'projected'},data,now+7200001),'unknown');
  assert.equal(starterStatus(row,data,now-1),'unknown');
});

test('comparison selections only prepare named drafts; both sides must match their own candidate lists',()=>{
  const data={sides:{home:{goalies:[{player_id:'1',name:'Home Goalie'}]},away:{goalies:[{player_id:'2',name:'Away Goalie'}]}}};
  const before=structuredClone(data);
  assert.equal(selectedGoaliePair(data,{}),null);
  assert.equal(selectedGoaliePair(data,{home:'1'}),null);
  assert.equal(selectedGoaliePair(data,{home:'2',away:'1'}),null);
  assert.deepEqual(selectedGoaliePair(data,{home:'1',away:'2'}),{home:'Home Goalie',away:'Away Goalie'});
  assert.deepEqual(data,before);
  assert.equal(selectedGoaliePair({...data,sides:{...data.sides,away:{goalies:[{player_id:'2',name:'HOME GOALIE'}]}}},{home:'1',away:'2'}),null);
});
