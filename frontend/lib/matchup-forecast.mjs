import {probabilities} from './market.mjs';

// Display saved research without promoting it into the verified recommendation.
// Never infer a win probability from xG share or a bookmaker's prices.
export function matchupForecast(fixture,paper,now=Date.now()){
  const existing=probabilities(fixture);
  if(existing)return {...existing,source:'model',captured_at:null,model_version:null};
  if(fixture.sport!=='NHL'||paper?.mode!=='paper_only'||paper.approved_for_wagers!==false)return null;
  const row=paper.records?.find(row=>row.fixture_id===fixture.id);
  if(!row||row.home!==fixture.home||row.away!==fixture.away||row.resolution==='VOID')return null;
  const start=Date.parse(row.start_at),captured=Date.parse(row.captured_at);
  const home=Number(row.home_probability);
  if(!Number.isFinite(now)||!Number.isFinite(start)||start!==Date.parse(fixture.commence_time)
    ||!Number.isFinite(captured)||captured>=start||captured>now
    ||row.home_probability===null||row.home_probability===undefined||row.home_probability===''
    ||!Number.isFinite(home)||home<0||home>1)return null;
  return {home,away:1-home,source:'paper',captured_at:row.captured_at,model_version:paper.model_version};
}
