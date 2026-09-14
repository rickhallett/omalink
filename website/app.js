const canvas=document.querySelector('#links'),ctx=canvas.getContext('2d');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let width=0,height=0,visible=true,last=0,phase=0;
const points=[];
for(let ring=0;ring<2;ring++)for(let i=0;i<160;i++)for(let j=0;j<14;j++){
 const u=i/160*Math.PI*2,v=j/14*Math.PI*2,r=1+.105*Math.cos(v);
 points.push(ring===0?[r*Math.cos(u)-.5,r*Math.sin(u),.105*Math.sin(v),j]:[r*Math.cos(u)+.5,.105*Math.sin(v),r*Math.sin(u),j]);
}
function size(){const r=canvas.getBoundingClientRect();width=r.width;height=r.height;const d=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(width*d);canvas.height=Math.round(height*d);ctx.setTransform(d,0,0,d,0,0);paint(phase)}
function paint(t){
 if(!width||!height)return;ctx.clearRect(0,0,width,height);
 const scale=Math.min(width*.255,height*.32),cx=width*.51,cy=height*.49;
 const ay=.45+Math.sin(t*.14)*.22,ax=.63+Math.cos(t*.11)*.10,az=-.36;
 const sy=Math.sin(ay),co=Math.cos(ay),sx=Math.sin(ax),cxr=Math.cos(ax),sz=Math.sin(az),cz=Math.cos(az);
 const projected=points.map(([x,y,z,j])=>{let a=x*co+z*sy,b=-x*sy+z*co,c=y*cxr-b*sx,d=y*sx+b*cxr;return{x:(a*cz-c*sz)*scale+cx,y:(a*sz+c*cz)*scale+cy,z:d,j}}).sort((a,b)=>a.z-b.z);
 const shadow=ctx.createRadialGradient(cx,cy+scale*1.27,5,cx,cy+scale*1.27,scale*1.5);shadow.addColorStop(0,'rgba(41,55,90,.065)');shadow.addColorStop(1,'rgba(41,55,90,0)');ctx.save();ctx.translate(0,(cy+scale*1.27)*.8);ctx.scale(1,.2);ctx.fillStyle=shadow;ctx.fillRect(0,0,width,height*5);ctx.restore();
 for(const p of projected){const opacity=.19+(p.z+1.4)/2.8*.65;ctx.fillStyle=`rgba(27,65,191,${Math.max(.16,Math.min(.92,opacity))})`;ctx.beginPath();ctx.arc(p.x,p.y,(p.j%3===0?1.05:.72)*Math.max(.6,scale/245),0,Math.PI*2);ctx.fill()}
 ctx.strokeStyle='rgba(35,72,204,.12)';ctx.lineWidth=.7;ctx.setLineDash([2,6]);ctx.beginPath();ctx.moveTo(cx-scale*1.55,cy);ctx.lineTo(cx+scale*1.65,cy);ctx.stroke();ctx.setLineDash([]);
}
function animate(now){if(visible&&!reduced.matches&&now-last>45){phase+=.045;paint(phase);last=now}requestAnimationFrame(animate)}
new ResizeObserver(size).observe(canvas);new IntersectionObserver(entries=>{visible=entries[0].isIntersecting}).observe(canvas);document.addEventListener('visibilitychange',()=>{visible=!document.hidden});reduced.addEventListener('change',()=>paint(phase));requestAnimationFrame(animate);
const dialog=document.querySelector('#picker'),list=document.querySelector('#link-list'),options=[...document.querySelectorAll('.option')],openLink=document.querySelector('#open-link');
const urls=['https://en.wikipedia.org/wiki/Hyperlink','https://omarchy.org','https://github.com/rickhallett/omalink'];let selected=0,lastTrigger=null;
function select(index){selected=(index+urls.length)%urls.length;options.forEach((o,i)=>o.setAttribute('aria-selected',String(i===selected)));list.setAttribute('aria-activedescendant','link-'+selected);openLink.href=urls[selected]}
function show(trigger){lastTrigger=trigger;select(0);dialog.showModal();list.focus()}
document.querySelectorAll('[data-demo]').forEach(b=>b.addEventListener('click',()=>show(b)));
document.querySelector('#close-picker').addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>lastTrigger?.focus());dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()}});
options.forEach((o,i)=>o.addEventListener('click',()=>{select(i);list.focus()}));
document.addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey)return;const key=e.key.length===1?e.key.toLowerCase():e.key;if(!dialog.open&&key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();show(document.activeElement)}else if(dialog.open){if(['j','ArrowDown','k','ArrowUp'].includes(key)){e.preventDefault();select(selected+(['j','ArrowDown'].includes(key)?1:-1))}else if(key==='Enter'&&document.activeElement===list){e.preventDefault();openLink.click()}}});
const copy=document.querySelector('#copy');copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(document.querySelector('.install-command code').textContent);copy.textContent='Copied ✓';setTimeout(()=>copy.textContent='Copy ↗',2000)}catch{document.querySelector('#copy-status').textContent='Select and copy the command above. Clipboard access is unavailable in this browser.'}});
