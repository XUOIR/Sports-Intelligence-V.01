// Stable point identities, with a separate seam layer for each sporting object.
export function sportCloud(count,seam,shape){
  const positions=new Float32Array(count*3),colors=new Float32Array(count*3);
  const sphere=(t)=>{const y=.58*Math.sin(2*t),r=Math.sqrt(1-y*y);return [r*Math.cos(t),y,r*Math.sin(t)];};
  const football=(x,angle)=>{const r=.7*Math.pow(Math.max(0,1-x*x),.68);return [x*1.48,r*Math.cos(angle),r*Math.sin(angle)];};
  for(let i=0;i<count;i++){
    let p,color=[.42,.58,1];
    const u=(i+.5)/count,t=u*Math.PI*2;
    if(!seam){
      const y=1-2*u,r=Math.sqrt(1-y*y),a=i*Math.PI*(3-Math.sqrt(5));p=[Math.cos(a)*r,y,Math.sin(a)*r];
      if(shape===1)p=football(p[0],Math.atan2(p[2],p[1]));
      if(shape===3){
        // Uniform disks stay flat; knurling belongs only on the cylinder wall.
        const side=u>=.7,local=side?(u-.7)/.3:(u% .35)/.35;
        const radius=side?1:Math.sqrt(local);
        p=[radius*Math.cos(a),side?(local*2-1)*.24:u<.35?.24:-.24,radius*Math.sin(a)];
      }
    }else if(shape===0){
      const band=Math.floor(u*4),a=(u*4%1)*Math.PI*2;
      if(band===0)p=[Math.cos(a),0,Math.sin(a)];
      else if(band===1)p=[Math.cos(a),Math.sin(a),0];
      else{const x=band===2?.55:-.55,r=Math.sqrt(1-x*x);p=[x,r*Math.cos(a),r*Math.sin(a)];}
      p=p.map(v=>v*1.006);color=[.72,.64,1];
    }else if(shape===1){
      if(u<.6){const part=u/.6*4,band=Math.floor(part);p=football((part%1)*2-1,band*Math.PI/2);color=[.57,.57,.91];}
      else if(u<.7){const x=(u-.6)/.1*.9-.45;p=football(x,1.30);color=[.91,.91,1];}
      else{const part=(u-.7)/.3*9,stitch=Math.min(8,Math.floor(part)),a=1.30+(part%1-.5)*.34;p=football(-.4+stitch*.1,a);color=[.91,.91,1];}
      p=p.map(v=>v*1.006);
    }else if(shape===2){
      // Red, paired diagonal stitches follow one continuous spherical seam.
      const stitches=100,part=u*stitches,a=Math.floor(part)/stitches*Math.PI*2,offset=part%1-.5;
      const center=sphere(a),next=sphere(a+.001),tangent=next.map((v,j)=>v-center[j]);
      const length=Math.hypot(...tangent);tangent.forEach((v,j)=>tangent[j]=v/length);
      const normal=[center[1]*tangent[2]-center[2]*tangent[1],center[2]*tangent[0]-center[0]*tangent[2],center[0]*tangent[1]-center[1]*tangent[0]];
      p=center.map((v,j)=>v+normal[j]*offset*.11+tangent[j]*Math.abs(offset)*.045);
      const radius=Math.hypot(...p);p=p.map(v=>v/radius*1.008);color=[1,.12,.22];
    }else{
      if(u<.45)p=[Math.cos(t/.45),.242,Math.sin(t/.45)];
      else if(u<.9){const a=(u-.45)/.45*Math.PI*2;p=[Math.cos(a),-.242,Math.sin(a)];}
      else{const part=(u-.9)/.1*100,a=Math.floor(part)/100*Math.PI*2;p=[Math.cos(a)*1.003,(part%1*2-1)*.22,Math.sin(a)*1.003];}
      color=[.37,.54,.86];
    }
    positions.set(p,i*3);colors.set(color,i*3);
  }
  return {positions,colors};
}
