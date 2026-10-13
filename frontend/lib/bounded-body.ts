export async function readLimited(stream:ReadableStream<Uint8Array>|null,limit:number):Promise<string> {
  if(!stream)return '';
  const reader=stream.getReader(),chunks:Uint8Array[]=[];let total=0;
  try{for(;;){const {value,done}=await reader.read();if(done)break;total+=value.byteLength;if(total>limit){await reader.cancel();throw new Error('Payload limit exceeded');}chunks.push(value);}}
  finally{reader.releaseLock();}
  const joined=new Uint8Array(total);let offset=0;for(const chunk of chunks){joined.set(chunk,offset);offset+=chunk.byteLength;}
  return new TextDecoder('utf-8',{fatal:true}).decode(joined);
}
