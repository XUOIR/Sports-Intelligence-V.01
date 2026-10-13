import type {Fixture} from './types';
export type WatchFilters={confidence:number;edge:number;coverage:number};
export const verificationGates:string[];
export const defaultFilters:Readonly<WatchFilters>;
export function normalizeFilters(value:unknown):WatchFilters;
export function coverage(fixture:Fixture):number;
export function matchesFilters(fixture:Fixture,filters:WatchFilters):boolean;
