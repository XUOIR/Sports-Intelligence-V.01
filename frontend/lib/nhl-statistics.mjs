export function teamXg(metrics){
  if(!metrics||metrics.status!=='available'||!Number.isInteger(metrics.sample_games)||metrics.sample_games<3)return null;
  if(typeof metrics.xg_share!=='string'&&typeof metrics.xg_share!=='number')return null;
  if(typeof metrics.xg_share==='string'&&!metrics.xg_share.trim())return null;
  const share=Number(metrics.xg_share);
  if(!Number.isFinite(share)||share<0||share>1)return null;
  return {share,sample:metrics.sample_games,latest:metrics.latest_game_date};
}
export function xgDifference(home,away){
  return home&&away?(away.share-home.share)*100:null;
}
export function nhlLogo(abbreviation){
  const clubs=['ANA','BOS','BUF','CAR','CBJ','CGY','CHI','COL','DAL','DET','EDM','FLA','LAK','MIN','MTL','NJD','NSH','NYI','NYR','OTT','PHI','PIT','SEA','SJS','STL','TBL','TOR','UTA','VAN','VGK','WPG','WSH'];
  return clubs.includes(abbreviation)?`https://assets.nhle.com/logos/nhl/svg/${abbreviation}_dark.svg`:null;
}
