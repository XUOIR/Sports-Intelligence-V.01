export const IDLE_MS = 15 * 60 * 1000;
export function shouldPoll({lastActivity, now, hidden}) { return !hidden && now-lastActivity<IDLE_MS; }
export function isStale(source, now=Date.now()) { if(!source)return true; const timestamp=Date.parse(source); return !Number.isFinite(timestamp) || timestamp>now || now-timestamp>5*60*1000; }
