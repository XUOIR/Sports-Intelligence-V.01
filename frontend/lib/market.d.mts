import type {Fixture,Quote} from './types';
export function moneylinePair(fixture:Fixture,quotes?:Quote[],now?:number,books?:string[]):{book:string;home:Quote;away:Quote;source_at:string;stale:boolean}|null;
export function probabilities(fixture:Fixture):{home:number;away:number}|null;
export function priceComparison(probability:number|null|undefined,price:number):{implied:number;edge:number;fair_odds:number|null}|null;
export function noVig(pair:{home:Quote;away:Quote}|null):{home:number;away:number}|null;
