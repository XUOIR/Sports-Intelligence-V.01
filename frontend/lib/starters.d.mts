import type {NHLStarterPreview} from './types';
export function starterStatus(row:NHLStarterPreview['sides']['home'],data:NHLStarterPreview,now?:number):'confirmed'|'projected'|'unknown';
