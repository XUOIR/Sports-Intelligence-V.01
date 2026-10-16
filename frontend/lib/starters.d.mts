import type {NHLStarterPreview,NHLStatistics,GoalieSelection} from './types';
export function starterStatus(row:NHLStarterPreview['sides']['home'],data:NHLStarterPreview,now?:number):'confirmed'|'projected'|'unknown';
export function selectedGoaliePair(statistics:NHLStatistics,selected:Record<string,string>):GoalieSelection|null;
