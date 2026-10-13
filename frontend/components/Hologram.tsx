'use client';
import {useEffect,useRef} from 'react';
import * as THREE from 'three';
export default function Hologram({sleeping}:{sleeping:boolean}) {
  const host=useRef<HTMLDivElement>(null);
  const asleep=useRef(sleeping);useEffect(()=>{asleep.current=sleeping},[sleeping]);
  useEffect(()=>{
    const element=host.current;if(!element)return;
    let renderer:THREE.WebGLRenderer;
    try { renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'}); } catch { return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.5));element.appendChild(renderer.domElement);
    const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(42,1,.1,100);camera.position.z=5.2;
    const geometry=new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.55,2));
    const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
      uniforms:{time:{value:0}},
      vertexShader:'varying vec3 pos; void main(){pos=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader:'uniform float time; varying vec3 pos; void main(){float shimmer=sin(pos.y*2.0+pos.x+time*.35)*.5+.5; vec3 color=mix(vec3(.10,.35,1.),vec3(.50,.80,1.),shimmer); gl_FragColor=vec4(color,.35+shimmer*.40);}',
    });
    const shape=new THREE.LineSegments(geometry,material);scene.add(shape);
    const ringGeometry=new THREE.RingGeometry(1.9,1.905,96),ringMaterial=new THREE.MeshBasicMaterial({color:0x3b82f6,transparent:true,opacity:.15,side:THREE.DoubleSide});
    const ring=new THREE.Mesh(ringGeometry,ringMaterial);ring.rotation.x=1.05;scene.add(ring);
    let targetX=0,targetY=0,frame=0,last=0;
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function pointer(event:PointerEvent){targetX=(event.clientX/window.innerWidth-.5)*.45;targetY=(event.clientY/window.innerHeight-.5)*.35;}
    function resize(){if(!element)return;const {width,height}=element.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/Math.max(1,height);camera.updateProjectionMatrix();}
    const observer=new ResizeObserver(resize);observer.observe(element);window.addEventListener('pointermove',pointer,{passive:true});resize();
    function draw(t:number){frame=requestAnimationFrame(draw);if(document.hidden || asleep.current || t-last<33)return;last=t;
      if(!reduced){shape.rotation.y+=(targetX+t*.00006-shape.rotation.y)*.04;shape.rotation.x+=(targetY+.15-shape.rotation.x)*.04;material.uniforms.time.value=t*.001;camera.fov+=(42+Math.abs(targetX)*8-camera.fov)*.03;camera.updateProjectionMatrix();}
      renderer.render(scene,camera);
    }
    frame=requestAnimationFrame(draw);
    return()=>{cancelAnimationFrame(frame);observer.disconnect();window.removeEventListener('pointermove',pointer);geometry.dispose();material.dispose();ringGeometry.dispose();ringMaterial.dispose();renderer.dispose();renderer.domElement.remove();};
  },[]);
  return <div ref={host} className="hologram" aria-hidden="true"/>;
}
