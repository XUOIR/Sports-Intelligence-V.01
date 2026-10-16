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

// A draft from comparison dropdowns grants no confirmation or verification gate.
export function selectedGoaliePair(statistics,selected){
  const pair={};
  for(const side of ['home','away']){
    const goalie=statistics?.sides?.[side]?.goalies?.find(g=>g.player_id===selected[side]);
    if(!goalie||typeof goalie.name!=='string'||goalie.name.trim().length<2)return null;
    pair[side]=goalie.name.trim();
  }
  return pair.home.toLowerCase()===pair.away.toLowerCase()?null:pair;
}
