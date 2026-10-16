import type {Fixture,PaperResults} from './types';
export function matchupForecast(fixture:Fixture,paper?:PaperResults,now?:number):{
  home:number;away:number;source:'model'|'paper';captured_at:string|null;model_version:string|null;
}|null;
