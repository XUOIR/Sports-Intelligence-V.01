import type {Detail,Verification} from './types';
export function verificationExpired(detail:Detail,now?:number):boolean;
export function verificationNotice(detail:Detail,now?:number):string|null;
export function gateStatus(check:Verification['checks'][number],detail:Detail,now?:number):Verification['checks'][number]['status'];
