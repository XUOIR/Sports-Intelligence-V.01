import { NextResponse } from 'next/server';
import { COOKIE, createSession, safeEqual, sameOrigin } from '@/lib/auth';
import {readLimited} from '@/lib/bounded-body';
const attempts = new Map<string,{count:number; until:number}>();
export async function POST(request: Request) {
  if (!sameOrigin(request)) return NextResponse.json({detail:'Origin rejected'},{status:403});
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password || password.length<12 || (process.env.ADMIN_API_TOKEN?.length||0)<32) return NextResponse.json({detail:'Dashboard access has not been configured'},{status:503});
  const key = request.headers.get('x-forwarded-for')?.split(',')[0] || 'local';
  for (const [ip, attempt] of attempts) if(attempt.until<Date.now()) attempts.delete(ip);
  if(attempts.size>1000 && !attempts.has(key)) return NextResponse.json({detail:'Try again later'},{status:429});
  const attempt = attempts.get(key) || {count:0,until:Date.now()+600000};
  if(attempt.count>=5) return NextResponse.json({detail:'Too many attempts. Try again in 10 minutes.'},{status:429});
  attempts.set(key,{...attempt,count:attempt.count+1});
  let text:string;try{text=await readLimited(request.body,1024);}catch{return NextResponse.json({detail:'Request too large'},{status:413});}
  let supplied=''; try { supplied=JSON.parse(text).password; } catch { return NextResponse.json({detail:'Invalid request'},{status:400}); }
  if(typeof supplied!=='string' || !safeEqual(supplied,password)) return NextResponse.json({detail:'Incorrect dashboard password'},{status:401});
  const response=NextResponse.json({ok:true});
  response.cookies.set(COOKIE,createSession(),{httpOnly:true,secure:process.env.NODE_ENV==='production',sameSite:'strict',maxAge:8*60*60,path:'/'});
  attempts.delete(key);
  return response;
}
export async function DELETE(request: Request) { if(!sameOrigin(request))return NextResponse.json({detail:'Origin rejected'},{status:403}); const response=NextResponse.json({ok:true}); response.cookies.delete(COOKIE); return response; }
