'use client';
import {useState} from 'react';
import {nhlLogo} from '@/lib/nhl-statistics.mjs';
export default function TeamLogo({abbreviation}:{abbreviation:unknown}){
  const [failed,setFailed]=useState<string|null>(null);
  const url=nhlLogo(abbreviation);
  return <span className="team-logo" aria-hidden="true">{url&&failed!==url?<img src={url} width={40} height={40} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={()=>setFailed(url)}/>:<span>{url?String(abbreviation):'NHL'}</span>}</span>;
}
