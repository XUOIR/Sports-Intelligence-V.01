import test from 'node:test';
import assert from 'node:assert/strict';
import {shouldPoll,isStale,IDLE_MS} from '../lib/activity.mjs';
import {pacificTime} from '../lib/time.mjs';
test('no polling when hidden or after exactly fifteen inactive minutes',()=>{
  assert.equal(shouldPoll({lastActivity:0,now:IDLE_MS-1,hidden:false}),true);
  assert.equal(shouldPoll({lastActivity:0,now:IDLE_MS,hidden:false}),false);
  assert.equal(shouldPoll({lastActivity:IDLE_MS,now:IDLE_MS,hidden:true}),false);
});
test('frontend preserves server Vancouver time after November 2026 transition',()=>{
  assert.match(pacificTime('2026-11-01T19:00:00-07:00'),/7:00/);
  assert.equal(pacificTime('2026-11-01T19:00:00'),'Time unavailable');
});
test('missing, invalid, future, or older than five-minute source shows stale',()=>{
  const now=Date.parse('2026-10-13T10:00:00-07:00');
  assert.equal(isStale(null,now),true);assert.equal(isStale('invalid',now),true);
  assert.equal(isStale('2026-10-13T10:01:00-07:00',now),true);
  assert.equal(isStale('2026-10-13T09:54:59-07:00',now),true);
  assert.equal(isStale('2026-10-13T09:55:00-07:00',now),false);
});
