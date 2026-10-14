import type {MatchFeed,MatchGame} from './types';
export function shiftDay(day:string,amount:number):string;
export function matchTime(value:string):string;
export function matchAge(value:string|null,now?:number):string;
export function feedExpired(feed:MatchFeed|null,now?:number):boolean;
export function playVisible(game:MatchGame,feed:MatchFeed|null,now?:number):boolean;
