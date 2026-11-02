// Procedural layered SVG art, seeded per card
let _gid=0;
function rng(seed){let s=seed*9301+49297;return()=>{s=(s*16807)%2147483647;return(s%10000)/10000}}
function ridge(r,y,amp,n){let d=`M0 140 L0 ${y}`;for(let i=0;i<=n;i++){const x=i*200/n;d+=` L${x.toFixed(1)} ${(y-r()*amp).toFixed(1)}`}return d+" L200 140Z"}
function hills(r,y,amp){let d=`M0 140 L0 ${y}`,x=0;while(x<200){const w=40+r()*50;d+=` Q${x+w/2} ${y-amp*(0.4+r())} ${x+w} ${y+(r()-.5)*8}`;x+=w}return d+" L200 140Z"}
function cardArt(c){
 const[,p,scene]=SERIES[c.series],r=rng(c.no*7+3),g="g"+(++_gid);
 const night=/night|dusk/.test(scene),sx=40+r()*120,sy=night?28+r()*20:30+r()*25;
 let s=`<svg viewBox="0 0 200 140" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg"><defs>
 <linearGradient id="${g}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p[0]}"/><stop offset="1" stop-color="${p[1]}"/></linearGradient>
 <radialGradient id="${g}u"><stop offset="0" stop-color="#fff" stop-opacity=".95"/><stop offset=".35" stop-color="#fff6c8" stop-opacity=".6"/><stop offset="1" stop-color="#fff6c8" stop-opacity="0"/></radialGradient>
 <radialGradient id="${g}h"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
 <linearGradient id="${g}f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p[2]}"/><stop offset="1" stop-color="${p[3]}"/></linearGradient></defs>
 <rect width="200" height="140" fill="url(#${g}s)"/>`;
 if(night||scene=="heaven")for(let i=0;i<40;i++)s+=`<circle cx="${r()*200}" cy="${r()*70}" r="${(r()*.9+.2).toFixed(2)}" fill="#fff" opacity="${(.4+r()*.6).toFixed(2)}"/>`;
 // light rays
 s+=`<g opacity=".22">`;for(let i=0;i<9;i++){const a=(i/9)*Math.PI*2+r(),b=a+.12;s+=`<path d="M${sx} ${sy} L${sx+Math.cos(a)*260} ${sy+Math.sin(a)*260} L${sx+Math.cos(b)*260} ${sy+Math.sin(b)*260}Z" fill="#fff"/>`}s+=`</g>`;
 s+=`<circle cx="${sx}" cy="${sy}" r="34" fill="url(#${g}u)"/><circle cx="${sx}" cy="${sy}" r="${night?7:10}" fill="${night?"#f4f1de":"#fff3b0"}"/>`;
 for(let i=0;i<3;i++){const cx=r()*200,cy=15+r()*40,w=14+r()*18;s+=`<g fill="#fff" opacity="${night?.15:.7}"><ellipse cx="${cx}" cy="${cy}" rx="${w}" ry="${w*.3}"/><ellipse cx="${cx+w*.4}" cy="${cy-w*.2}" rx="${w*.5}" ry="${w*.35}"/></g>`}
 s+=`<path d="${ridge(r,78,22,8)}" fill="${p[3]}" opacity=".35"/>`;
 if(scene=="sea"){for(let i=0;i<4;i++){const y=88+i*13;s+=`<path d="${hills(r,y,4)}" fill="${i%2?p[2]:p[3]}" opacity="${.75+i*.08}"/>`}}
 else{s+=`<path d="${hills(r,92,14)}" fill="${p[2]}" opacity=".85"/><path d="${hills(r,112,10)}" fill="url(#${g}f)"/>`}
 if(scene=="city")for(let i=0;i<9;i++){const x=r()*190,w=8+r()*12,h=12+r()*26;s+=`<rect x="${x}" y="${96-h}" width="${w}" height="${h}" fill="${p[3]}" opacity=".7"/>${r()>.6?`<path d="M${x} ${96-h} Q${x+w/2} ${86-h-6} ${x+w} ${96-h}Z" fill="${p[3]}" opacity=".7"/>`:""}`}
 if(scene=="library")for(let i=0;i<22;i++){const x=4+i*9;s+=`<rect x="${x}" y="${104+r()*6}" width="7" height="${20+r()*8}" rx="1" fill="${["#8c3b2e","#2e5d8c","#3f7d4f","#c9a227","#6b3f8c"][i%5]}" opacity=".9"/>`}
 if(scene=="garden"||scene=="fields")for(let i=0;i<26;i++){const x=r()*200,y=112+r()*26;s+=scene=="garden"?`<circle cx="${x}" cy="${y}" r="${1.5+r()*2}" fill="${["#ff8fab","#ffd166","#cdb4db","#fff"][i%4]}"/>`:`<path d="M${x} ${y} q2 -10 ${r()*4-2} -16" stroke="#e9c46a" stroke-width="1.4" fill="none"/>`}
 if(scene=="desert"||scene=="desert-night")for(let i=0;i<3;i++){const x=r()*180;s+=`<path d="M${x} 104 l6 -10 l6 10Z" fill="${p[3]}" opacity=".6"/>`}
 if(scene=="hills")for(let i=0;i<5;i++){const x=r()*190,y=100+r()*10;s+=`<circle cx="${x}" cy="${y}" r="${5+r()*4}" fill="${p[3]}" opacity=".8"/><rect x="${x-.8}" y="${y}" width="1.6" height="8" fill="#5b3a29"/>`}
 // motif with halo
 s+=`<circle cx="100" cy="74" r="40" fill="url(#${g}h)"/><text x="100" y="${74+15}" font-size="44" text-anchor="middle" style="filter:drop-shadow(0 3px 2px rgba(0,0,0,.35))">${c.motif}</text>`;
 s+=`<rect width="200" height="140" fill="none" stroke="rgba(0,0,0,.25)" stroke-width="3"/></svg>`;return s}
