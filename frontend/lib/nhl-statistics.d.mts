import type {NHLTeamStatistics} from './types';
export type TeamXg={share:number;sample:number;latest:string|null};
export function teamXg(metrics:NHLTeamStatistics|null|undefined):TeamXg|null;
export function xgDifference(home:TeamXg|null,away:TeamXg|null):number|null;
export function nhlLogo(abbreviation:unknown):string|null;
