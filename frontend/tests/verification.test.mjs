import test from 'node:test';
import assert from 'node:assert/strict';
import {gateStatus,verificationExpired,verificationNotice} from '../lib/verification.mjs';
const now=Date.parse('2026-10-14T21:00:00Z');
const detail={fixture:{home:'Home',away:'Away',commence_time:new Date(now+3600000).toISOString(),dirty:false,metrics:{confirmed_at:new Date(now-10000).toISOString()}},verification:{phase:'frozen',checked_at:new Date(now).toISOString(),anchor_at:new Date(now-10000).toISOString()},odds:['Home','Away'].map(selection=>({selection,bookmaker:'playnow',market:'h2h',line:null,decimal_odds:'2',source_at:new Date(now-290000).toISOString()}))};
test('an open panel removes passed price badges when its quote expires',()=>{
  const check={key:'price',status:'passed'};
  assert.equal(gateStatus(check,detail,now),'passed');
  assert.equal(gateStatus(check,detail,now+11000),'blocked');
});
test('an old panel, dirty fixture or expired confirmation cannot retain passed badges',()=>{
  assert.equal(gateStatus({key:'form',status:'passed'},detail,now+300001),'blocked');
  assert.equal(gateStatus({key:'form',status:'passed'},{...detail,fixture:{...detail.fixture,dirty:true}},now),'blocked');
  const d={...detail,fixture:{...detail.fixture,metrics:{confirmed_at:new Date(now-1800001).toISOString()}}};
  assert.equal(gateStatus({key:'personnel',status:'passed'},d,now),'blocked');
  assert.equal(gateStatus({key:'probability',status:'pending'},detail,now),'pending');
});
test('passing the anchor or game start invalidates pregame verification',()=>{
  assert.equal(verificationExpired({...detail,verification:{...detail.verification,phase:'waiting_for_anchor'}},now),true);
  assert.equal(verificationExpired(detail,now+3600000),true);
  assert.equal(gateStatus({key:'maps_veto',status:'not_applicable'},detail,now+3600000),'not_applicable');
});
test('a fresh read cannot reopen a started game or invite an endless refresh',()=>{
  const started={...detail,fixture:{...detail.fixture,commence_time:new Date(now).toISOString()}};
  assert.equal(verificationExpired(started,now),true);
  assert.equal(gateStatus({key:'form',status:'passed'},started,now),'blocked');
  assert.equal(verificationNotice(started,now),'Pregame verification is closed for this game. Refreshing saved evidence cannot reopen it.');
  assert.equal(verificationNotice(detail,now),null);
  assert.match(verificationNotice(detail,now+300001),/newer database read/);
  assert.match(verificationNotice({...detail,verification:{...detail.verification,phase:'waiting_for_anchor'}},now),/T−30 checkpoint has arrived/);
});
