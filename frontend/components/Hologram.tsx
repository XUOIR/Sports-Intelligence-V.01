'use client';
import {useEffect,useRef} from 'react';
import * as THREE from 'three';

const COUNT=10000, SEAMS=1800, CYCLE=8;

// Stable point identities let each sport dissolve smoothly into the next.
function cloud(count:number,seam:boolean,shape:number){
  const positions=new Float32Array(count*3);
  for(let i=0;i<count;i++){
    let x:number,y:number,z:number;
    if(seam){
      const t=(i%600)/600*Math.PI*2,band=Math.floor(i/600);
      if(shape===2){x=Math.cos(t);y=Math.sin(t)*Math.cos(2*t)*.75;z=Math.sin(t)*Math.sin(2*t);}
      else if(band===0){x=Math.cos(t);y=Math.sin(t);z=0;}
      else if(band===1){x=0;y=Math.sin(t);z=Math.cos(t);}
      else{x=Math.cos(t);y=Math.sin(t)*.55;z=Math.sin(t)*.83;}
      const norm=Math.hypot(x,y,z);x/=norm;y/=norm;z/=norm;
    }else{
      y=1-2*(i+.5)/count;const radius=Math.sqrt(1-y*y),angle=i*Math.PI*(3-Math.sqrt(5));
      x=Math.cos(angle)*radius;z=Math.sin(angle)*radius;
    }
    if(shape===1){x*=1.42;y*=.70;z*=.70;}
    if(shape===3){
      const angle=Math.atan2(z,x),cap=Math.abs(y)>.45;
      const r=cap?Math.sqrt((1-Math.abs(y))/.55):1;
      x=Math.cos(angle)*r;z=Math.sin(angle)*r;y=cap?Math.sign(y)*.25:y/.45*.25;
    }
    positions.set([x,y,z],i*3);
  }
  return positions;
}

export default function Hologram({sleeping}:{sleeping:boolean}){
  const host=useRef<HTMLDivElement>(null),asleep=useRef(sleeping),wake=useRef(()=>{});
  useEffect(()=>{asleep.current=sleeping;wake.current();},[sleeping]);
  useEffect(()=>{
    const element=host.current;if(!element)return;
    let renderer:THREE.WebGLRenderer;
    try{renderer=new THREE.WebGLRenderer({alpha:true,antialias:false,powerPreference:'low-power'});}
    catch{element.dataset.fallback='true';return;}
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.5));element.appendChild(renderer.domElement);
    const scene=new THREE.Scene(),group=new THREE.Group(),camera=new THREE.PerspectiveCamera(38,1,.1,20);
    scene.add(group);camera.position.z=3.9;
    const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
    const uniforms={time:{value:0},morph:{value:0},scatter:{value:0},hover:{value:0},pointer:{value:new THREE.Vector2(10,10)}};
    const geometries:THREE.BufferGeometry[]=[],materials:THREE.ShaderMaterial[]=[],shapes:Float32Array[][]=[];
    for(const seam of [false,true]){
      const count=seam?SEAMS:COUNT,variants=[0,1,2,3].map(shape=>cloud(count,seam,shape));shapes.push(variants);
      const geometry=new THREE.BufferGeometry();
      geometry.setAttribute('position',new THREE.BufferAttribute(variants[0].slice(),3));
      geometry.setAttribute('nextPosition',new THREE.BufferAttribute(variants[1].slice(),3));
      geometry.setAttribute('sparkle',new THREE.BufferAttribute(Float32Array.from({length:count},(_,i)=>(Math.sin(i*127.1)*43758.5453)%1),1));
      const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
        uniforms:{...uniforms,size:{value:seam?3.0:1.65},seam:{value:seam?1:0}},
        vertexShader:`attribute vec3 nextPosition; attribute float sparkle;
          uniform float time,morph,scatter,hover,size; uniform vec2 pointer;
          varying vec3 tint; varying float glow;
          void main(){vec3 p=mix(position,nextPosition,morph);p+=normalize(p)*scatter*(.7+abs(sparkle));
            vec4 mv=modelViewMatrix*vec4(p,1.);vec2 delta=mv.xy-pointer;
            float force=hover*exp(-dot(delta,delta)*4.);mv.xy+=normalize(delta+vec2(.001))*force*.24;
            tint=mix(vec3(.52,.20,1.),vec3(.08,.55,1.),smoothstep(-1.,.4,p.y));
            tint=mix(tint,vec3(.30,.96,1.),smoothstep(.25,1.,p.y));
            glow=.55+.45*sin(time*.7+sparkle*12.);gl_Position=projectionMatrix*mv;
            gl_PointSize=size*min(2.,3.9/-mv.z);}`,
        fragmentShader:`uniform float seam; varying vec3 tint; varying float glow;
          void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;
            float a=pow(1.-d*2.,1.2)*mix(.65,1.,seam);gl_FragColor=vec4(tint*(1.+seam*.7),a*glow);}`});
      geometries.push(geometry);materials.push(material);group.add(new THREE.Points(geometry,material));
    }
    let frame=0,last=0,elapsed=0,phase=-1,visible=true,targetHover=0,targetX=0,targetY=0,disposed=false;
    function updatePhase(next:number){if(phase===next)return;phase=next;geometries.forEach((geometry,i)=>{
      for(const [name,variant] of [['position',next],['nextPosition',(next+1)%4]] as const){
        const attribute=geometry.getAttribute(name) as THREE.BufferAttribute;
        (attribute.array as Float32Array).set(shapes[i][variant]);attribute.needsUpdate=true;
      }
    });}
    function schedule(){if(!disposed&&!frame&&visible&&!document.hidden&&!asleep.current)frame=requestAnimationFrame(draw);}
    wake.current=schedule;
    function draw(t:number){
      frame=0;if(disposed||!visible||document.hidden||asleep.current){last=0;return;}
      const reduced=motion.matches;
      if(!reduced&&last&&t-last<33){schedule();return;}
      const dt=last?Math.min((t-last)/1000,.1):0;last=t;if(!reduced)elapsed+=dt;
      const cycle=elapsed/CYCLE;updatePhase(reduced?0:Math.floor(cycle)%4);
      const blend=Math.max(0,((cycle%1)-.72)/.28);uniforms.morph.value=reduced?0:blend*blend*(3-2*blend);
      uniforms.time.value=elapsed;uniforms.scatter.value=reduced?0:Math.max(0,uniforms.scatter.value-dt*2.5);
      uniforms.hover.value=reduced?0:uniforms.hover.value+(targetHover-uniforms.hover.value)*.12;
      group.rotation.y=reduced ? .35 : elapsed*.18+targetX*.16;group.rotation.x=reduced ? .12 : .12+targetY*.10;
      renderer.render(scene,camera);if(!reduced)schedule();
    }
    function resize(){const {width,height}=element!.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/Math.max(height,1);camera.updateProjectionMatrix();schedule();}
    function pointer(event:PointerEvent){const box=element!.getBoundingClientRect();targetX=(event.clientX-box.left)/box.width*2-1;targetY=1-(event.clientY-box.top)/box.height*2;
      const h=Math.tan(THREE.MathUtils.degToRad(19))*camera.position.z;
      uniforms.pointer.value.set(targetX*h*camera.aspect,targetY*h);targetHover=1;schedule();}
    function leave(){targetHover=0;targetX=targetY=0;}
    function burst(){if(!motion.matches){uniforms.scatter.value=1;schedule();}}
    function visibility(){last=0;schedule();}
    const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(element);
    const intersection=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;last=0;schedule();},{threshold:.05});intersection.observe(element);
    element.addEventListener('pointermove',pointer,{passive:true});element.addEventListener('pointerleave',leave);element.addEventListener('pointerdown',burst);
    document.addEventListener('visibilitychange',visibility);motion.addEventListener('change',visibility);resize();schedule();
    return()=>{disposed=true;wake.current=()=>{};cancelAnimationFrame(frame);resizeObserver.disconnect();intersection.disconnect();
      element.removeEventListener('pointermove',pointer);element.removeEventListener('pointerleave',leave);element.removeEventListener('pointerdown',burst);
      document.removeEventListener('visibilitychange',visibility);motion.removeEventListener('change',visibility);
      geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());renderer.dispose();renderer.domElement.remove();};
  },[]);
  return <div ref={host} className="hologram" aria-hidden="true"><div className="orb-fallback"/></div>;
}
