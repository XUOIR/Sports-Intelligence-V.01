import test from 'node:test';
import assert from 'node:assert/strict';
import {starterStatus} from '../lib/starters.mjs';
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
