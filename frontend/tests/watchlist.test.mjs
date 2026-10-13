import {test} from 'node:test';
import assert from 'node:assert/strict';
import {matchesFilters,coverage,normalizeFilters,verificationGates} from '../lib/watchlist.mjs';

test('unknown metrics remain visible at zero, but cannot satisfy positive thresholds',()=>{
  const fixture={probability:null,edge:null,gates:{}};
  assert.equal(matchesFilters(fixture,{confidence:0,edge:0,coverage:0}),true);
  for(const key of ['confidence','edge','coverage'])assert.equal(matchesFilters(fixture,{[key]:1}),false);
  assert.equal(matchesFilters({...fixture,probability:'not a number'},{confidence:1}),false);
});
test('filters use percentage points and all eight gates, with inclusive boundaries',()=>{
  const fixture={probability:'0.75',edge:'0.05',gates:Object.fromEntries(verificationGates.slice(0,4).map(g=>[g,true]))};
  assert.equal(coverage(fixture),50);
  assert.equal(matchesFilters(fixture,{confidence:75,edge:5,coverage:50}),true);
  for(const filters of [{confidence:76},{edge:6},{coverage:51}])assert.equal(matchesFilters(fixture,filters),false);
  assert.equal(coverage({...fixture,gates:{...fixture.gates,unknown:true,probability:'true'}}),50);
  assert.equal(matchesFilters({...fixture,edge:'-0.03'},{edge:0}),true);
});
test('persisted preferences are bounded and malformed values fail safely',()=>{
  assert.deepEqual(normalizeFilters({confidence:150,edge:-4,coverage:'no'}),{confidence:100,edge:0,coverage:0});
  assert.deepEqual(normalizeFilters(null),{confidence:0,edge:0,coverage:0});
  assert.deepEqual(normalizeFilters({confidence:55.4,coverage:Infinity}),{confidence:55,edge:0,coverage:0});
});
