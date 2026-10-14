import { NextRequest, NextResponse } from 'next/server';
import { authenticated, sameOrigin } from '@/lib/auth';
import {readLimited} from '@/lib/bounded-body';
export const dynamic = 'force-dynamic';
async function proxy(request: NextRequest,{params}:{params:Promise<{path:string[]}>}) {
  if(!await authenticated())return NextResponse.json({detail:'Sign in to view your workspace'},{status:401});
  if(request.method!=='GET' && !sameOrigin(request)) return NextResponse.json({detail:'Origin rejected'},{status:403});
  const {path}=await params;
  const allowed = path.length===1 && ['dashboard','bets','operations','matches'].includes(path[0])
    || path.length===2 && path[0]==='matches' && path[1]==='sync'
    || path.length===2 && ['fixtures','bets'].includes(path[0])
    || path.length===2 && path[0]==='operations' && ['pause','resume','allowances','odds-refresh','nhl-statistics-refresh'].includes(path[1])
    || path.length===3 && path[0]==='operations' && path[1]==='odds-refresh'
    || path.length===3 && path[0]==='fixtures' && path[2]==='evidence';
  if(!allowed || path.some(p=>!/^[-a-zA-Z0-9_:]+$/.test(p)))return NextResponse.json({detail:'Unknown endpoint'},{status:404});
  const base=process.env.BACKEND_URL || (process.env.BACKEND_HOST?`http://${process.env.BACKEND_HOST}:${process.env.BACKEND_PORT||'10000'}`:undefined);
  if(!base)return NextResponse.json({detail:'Backend connection is not configured'},{status:503});
  let body:string|undefined;
  try{body=request.method==='GET'?undefined:await readLimited(request.body,16384);}catch{return NextResponse.json({detail:'Request too large'},{status:413});}
  const query=new URLSearchParams();
  if(path[0]==='matches'){const date=request.nextUrl.searchParams.get('date');if(date){if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return NextResponse.json({detail:'Invalid match date'},{status:422});query.set('date',date);}}
  for(const name of ['limit','offset']){ const value=request.nextUrl.searchParams.get(name); if(value)query.set(name,value); }
  try {
    const result=await fetch(`${base.replace(/\/$/,'')}/${path.map(encodeURIComponent).join('/')}?${query}`,{
      method:request.method,body,cache:'no-store',signal:AbortSignal.timeout(path[0]==='operations'&&path[1]==='odds-refresh'&&request.method==='POST'?50000:path[0]==='operations'&&path[1]==='allowances'?25000:10000),
      headers:{Authorization:`Bearer ${process.env.ADMIN_API_TOKEN}`,'Content-Type':'application/json'},redirect:'error',
    });
    const payload=await readLimited(result.body,1000000);
    return new NextResponse(payload,{status:result.status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
  }catch{return NextResponse.json({detail:'Backend temporarily unavailable'},{status:503});}
}
export {proxy as GET,proxy as POST,proxy as PATCH};
