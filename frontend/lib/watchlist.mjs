export const verificationGates = ['price','personnel','form','maps_veto','other_markets','opposing_case','overlap_exposure','probability'];
export const defaultFilters = Object.freeze({confidence:0,edge:0,coverage:0});
export function normalizeFilters(value) {
  return Object.fromEntries(Object.keys(defaultFilters).map(key=>{
    const number=Number(value?.[key]);
    return [key,Number.isFinite(number)?Math.min(100,Math.max(0,Math.round(number))):0];
  }));
}
export function coverage(fixture) {
  return verificationGates.filter(gate=>fixture.gates?.[gate]===true).length/verificationGates.length*100;
}
export function matchesFilters(fixture,filters) {
  const thresholds=normalizeFilters(filters);
  const meets=(value,minimum)=>minimum===0 || (value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value))&&Number(value)*100>=minimum);
  return meets(fixture.probability,thresholds.confidence)&&meets(fixture.edge,thresholds.edge)&&coverage(fixture)>=thresholds.coverage;
}
