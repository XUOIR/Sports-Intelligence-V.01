import { createHmac, timingSafeEqual } from 'node:crypto';
import { cookies } from 'next/headers';
export const COOKIE = 'si_session';
function signature(value: string) { const key = process.env.ADMIN_API_TOKEN; if (!key || key.length < 32) throw new Error('Server authentication is not configured'); return createHmac('sha256', key).update(value).digest('hex'); }
export function safeEqual(a: string,b: string) { const left = Buffer.from(a),right = Buffer.from(b); return left.length === right.length && timingSafeEqual(left,right); }
export function createSession() { const expires = String(Date.now()+8*60*60*1000); return `${expires}.${signature(expires)}`; }
export async function authenticated() { const value = (await cookies()).get(COOKIE)?.value; if (!value || !process.env.ADMIN_API_TOKEN || process.env.ADMIN_API_TOKEN.length<32 || !/^\d{13}\.[a-f0-9]{64}$/.test(value)) return false; const [expires, sig] = value.split('.'); return Number(expires)>Date.now() && Number(expires)<Date.now()+8*60*60*1000+1000 && safeEqual(sig, signature(expires)); }
export function sameOrigin(request: Request) { try { return new URL(request.headers.get('origin') || '').host === request.headers.get('host'); } catch { return false; } }
