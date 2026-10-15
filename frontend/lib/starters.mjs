export function starterStatus(row,data,now=Date.now()){
  const checked=Date.parse(data.checked_at);
  if(!Number.isFinite(checked)||checked>now)return 'unknown';
  if(row.status==='confirmed'){
    const at=Date.parse(row.confirmed_at);
    return Number.isFinite(at)&&at<=now&&now-at<=1800000?'confirmed':'unknown';
  }
  if(row.status==='projected'){
    const until=Date.parse(data.projection_valid_until);
    return Number.isFinite(until)&&now<=until?'projected':'unknown';
  }
  return 'unknown';
}
