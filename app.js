const ART=new Set("c001 c007 c009 c013 c015 c020 c024 c026 c030 c033 c041 c047 c050 c054 c056 c062 c068 c069 c074 c076 c078 c086 c092 c095 c101 c102 c115 c117 c129 c131 c133 c137 c142 ".trim().split(" "));
const $=s=>document.querySelector(s),KEY="faithcards-v2",DEBUG=/[?&]debug=1/.test(location.search);
const SYM={common:"●",rare:"◆",special:"★"},RNAME={common:"Common",rare:"Rare",special:"Special Holo"};
let S=JSON.parse(localStorage.getItem(KEY)||"null")||{owned:{},lastOpen:null,streak:0,bonus:0,offset:0,forceSpecial:false,done:false};
const save=()=>localStorage.setItem(KEY,JSON.stringify(S));
const dstr=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const dayN=o=>{const d=new Date();d.setDate(d.getDate()+S.offset+o);return dstr(d)};
const today=()=>dayN(0),yesterday=()=>dayN(-1);
const curStreak=()=>(S.lastOpen==today()||S.lastOpen==yesterday())?S.streak:0;
const ownedCount=()=>Object.keys(S.owned).length;

// ---------- card rendering ----------
function cardHTML(c,cls=""){const[st]=SERIES[c.series];
 const art=ART.has(c.id)?`<img src="art/${c.id}.jpg" alt="" draggable="false">`:cardArt(c);
 return `<div class="tc r-${c.rarity} ${cls}" data-id="${c.id}"><div class="tc-in">
 <div class="tc-head"><span class="nm">${c.name}</span><span class="sym" title="${RNAME[c.rarity]}">${SYM[c.rarity]}</span></div>
 <div class="tc-art">${art}</div>
 <div class="tc-type">${st} · ${RNAME[c.rarity]}</div>
 <div class="tc-text"><p class="fl">${c.flavour}</p><p class="ref">📖 ${c.ref}</p></div>
 <div class="tc-foot"><span>${String(c.no).padStart(3,"0")}/500</span><span>Faith Cards ✝</span></div></div>
 ${c.rarity=="special"?'<div class="holo"></div><div class="sparkle"></div>':""}</div>`}
const back=()=>`<div class="cb"><div class="cb-in"><span>✝</span><b>FAITH<br>CARDS</b></div></div>`;

// ---------- drawing ----------
const pool=r=>CARDS.filter(c=>c.rarity==r);
function pickFrom(list,exclude){const fresh=list.filter(c=>!S.owned[c.id]&&!exclude.has(c.id)),any=list.filter(c=>!exclude.has(c.id));
 const src=fresh.length&&Math.random()<.7?fresh:any;return src[Math.floor(Math.random()*src.length)]}
function makePack(n,guarantee){const ex=new Set(),out=[];
 const special=guarantee||S.forceSpecial||Math.random()<.10;S.forceSpecial=false;
 for(let i=0;i<n-(special?1:0);i++){const c=pickFrom(pool(Math.random()<.25?"rare":"common"),ex);ex.add(c.id);out.push(c)}
 out.sort((a,b)=>(a.rarity=="rare")-(b.rarity=="rare"));
 if(special){const c=pickFrom(pool("special"),ex);out.push(c)}return out}

// ---------- header / streak ----------
function renderTop(){const n=ownedCount();$("#ownedN").textContent=n;$("#ownedBar").style.width=n/5+"%";
 const st=curStreak(),opened=S.lastOpen==today(),inCycle=st%7==0&&st>0&&opened?7:st%7;
 $("#streakN").textContent=st;$("#flameBig").classList.toggle("cold",st==0);
 $("#pips").innerHTML=Array.from({length:7},(_,i)=>`<span class="pip ${i<inCycle?"lit":""} ${i==6?"gift":""}">${i==6?"🎁":i<inCycle?"🔥":"·"}</span>`).join("");
 const left=7-inCycle;
 $("#streakMsg").innerHTML=S.bonus>0?`🎁 <b>Bonus pack ready!</b> Guaranteed Special inside.`:
  st==0&&S.lastOpen?`Streak reset — open today to light the first flame!`:
  opened?(left==0?`7-day streak! Bonus earned 🎉`:`Come back tomorrow · <b>${left}</b> more day${left>1?"s":""} to a Bonus Pack`):
  `Open today's pack to keep the flame alive · <b>${left}</b> day${left>1?"s":""} to Bonus`}

// ---------- stage ----------
let phase="idle",pulled=[],idx=0;
function renderStage(){const st=$("#stage"),msg=$("#stageMsg");$("#toBinder").hidden=true;$("#pulled").innerHTML="";
 const daily=S.lastOpen!=today(),bonus=S.bonus>0;
 if(daily||bonus){const kind=daily?"daily":"bonus";
  st.innerHTML=packHTML(kind);msg.innerHTML=`<span class="swipe-hint">👆 Swipe across the top to tear it open</span>`;bindPack(kind)}
 else{st.innerHTML=packHTML("locked");msg.innerHTML=`Today's pack is opened! Next blessing in <b id="cd"></b>`;tick()}}
function packHTML(kind){const t={daily:["Daily Blessing","5 cards · 10% Special"],bonus:["Streak Bonus","3 cards · Special guaranteed!"],locked:["Come back tomorrow","New pack at midnight"]}[kind];
 return `<div class="pack-wrap"><div class="pack p-${kind}" id="pack">
 <div class="pk-top"><div class="crimp"></div><div class="tear" id="tear"><i id="tearLine"></i></div></div>
 <div class="pk-body"><div class="pk-foil"></div><div class="pk-glare"></div>
  <div class="pk-logo">✝ FAITH CARDS</div>
  <div class="pk-art"><img src="art/${kind=="bonus"?"c142":"c013"}.jpg" alt=""></div>
  <div class="pk-title">${t[0]}</div><div class="pk-sub">${t[1]}</div>${kind=="locked"?'<div class="lock">🔒</div>':""}
 </div><div class="crimp bottom"></div></div><div class="pack-shadow"></div></div>`}
function bindPack(kind){const pk=$("#pack"),tear=$("#tear"),line=$("#tearLine");
 const tilt=e=>{const r=pk.getBoundingClientRect(),x=(e.clientX-r.left)/r.width,y=(e.clientY-r.top)/r.height;
  pk.style.setProperty("--rx",((.5-y)*22)+"deg");pk.style.setProperty("--ry",((x-.5)*26)+"deg");pk.style.setProperty("--mx",x*100+"%");pk.style.setProperty("--my",y*100+"%")};
 pk.addEventListener("pointermove",tilt);pk.addEventListener("pointerleave",()=>{pk.style.setProperty("--rx","0deg");pk.style.setProperty("--ry","0deg")});
 let sx=null;tear.addEventListener("pointerdown",e=>{sx=e.clientX;tear.setPointerCapture(e.pointerId);e.stopPropagation()});
 tear.addEventListener("pointermove",e=>{if(sx==null)return;const w=tear.offsetWidth,p=Math.min(1,Math.abs(e.clientX-sx)/(w*.7));line.style.width=p*100+"%";if(p>=1){sx=null;openPack(kind)}});
 tear.addEventListener("pointerup",()=>{if(sx!=null){sx=null;line.style.width="0"}});
 pk.addEventListener("click",e=>{if(e.target.closest("#tear"))return;pk.classList.remove("nudge");void pk.offsetWidth;pk.classList.add("nudge")});
 pk.addEventListener("dblclick",()=>openPack(kind))}
function openPack(kind){if(phase!="idle")return;phase="opening";
 if(kind=="daily"){S.streak=S.lastOpen==yesterday()?S.streak+1:1;S.lastOpen=today();if(S.streak%7==0)S.bonus++;pulled=makePack(5,false)}
 else{S.bonus--;pulled=makePack(3,true)}
 pulled=pulled.map(c=>({c,isNew:!S.owned[c.id]}));pulled.forEach(({c})=>S.owned[c.id]=(S.owned[c.id]||0)+1);save();renderTop();
 const pk=$("#pack");$("#stageMsg").innerHTML="";pk.classList.add("torn");flash(.6);
 setTimeout(()=>{$("#stage").innerHTML=`<div class="stack" id="stack">${pulled.map((p,i)=>`<div class="sc" style="--i:${i}">${back()}</div>`).join("")}</div>`;
  $("#stageMsg").innerHTML=`<span class="swipe-hint">Tap the card to reveal · ${pulled.length} cards</span>`;idx=0;phase="reveal";bindStack()},900)}
function bindStack(){const stack=$("#stack");stack.onclick=reveal;
 let sx=null;stack.onpointerdown=e=>sx=e.clientX;stack.onpointerup=e=>{if(sx!=null&&Math.abs(e.clientX-sx)>40){reveal()}sx=null}}
let busy=false;
function reveal(){if(busy||phase!="reveal")return;const cards=[...document.querySelectorAll(".sc")],top=cards[cards.length-1];if(!top)return;

 busy=true;
 if(top.classList.contains("flipped")){ // send away
  top.classList.add("away");addPulled(top.__p);idx++;
  setTimeout(()=>{top.remove();busy=false;if(idx>=pulled.length)finishReveal();else $("#stageMsg").innerHTML=`<span class="swipe-hint">Tap to reveal · ${pulled.length-idx} left${pulled.length-idx==1&&pulled[pulled.length-1].c.rarity=="special"?" … something is glowing ✨":""}</span>`},450);return}
 const pp=pulled[idx];top.__p=pp;
 const doFlip=()=>{top.innerHTML=`<div class="flipper"><div class="f-back">${back()}</div><div class="f-front">${cardHTML(pp.c)}${pp.isNew?'<span class="newb">NEW!</span>':'<span class="dupb">×'+S.owned[pp.c.id]+'</span>'}</div></div>`;
  requestAnimationFrame(()=>requestAnimationFrame(()=>top.classList.add("flipped")));
  holoTilt(top);setTimeout(()=>busy=false,650)};
 if(pp.c.rarity=="special"){top.classList.add("charging");$("#stage").classList.add("glow");
  setTimeout(()=>{flash(1);burst();top.classList.remove("charging");doFlip();confetti(40)},1300)}
 else{if(pp.c.rarity=="rare")top.classList.add("rare-pop");doFlip()}}
function addPulled(p){const d=document.createElement("div");d.className="mini";d.innerHTML=cardHTML(p.c)+(p.isNew?'<span class="newb">NEW</span>':"");d.onclick=()=>zoom(p.c);$("#pulled").appendChild(d)}
function finishReveal(){phase="done";$("#stage").classList.remove("glow");$("#stage").innerHTML="";$("#stageMsg").innerHTML=`<b>${pulled.filter(p=>p.isNew).length}</b> new card(s) for your binder!`;$("#toBinder").hidden=false}
$("#toBinder").onclick=()=>{const t=$("#binderTab").getBoundingClientRect();$("#toBinder").hidden=true;
 [...document.querySelectorAll("#pulled .mini")].forEach((m,i)=>{const r=m.getBoundingClientRect();m.style.transition=`transform .7s cubic-bezier(.5,-0.3,.7,1) ${i*.12}s, opacity .7s ${i*.12}s`;
  m.style.transform=`translate(${t.left+t.width/2-r.left-r.width/2}px,${t.top-r.top-r.height/2}px) scale(.1) rotate(${200+i*30}deg)`;m.style.opacity=".2"});
 setTimeout(()=>{$("#binderTab").classList.add("bump");setTimeout(()=>$("#binderTab").classList.remove("bump"),500);phase="idle";renderStage();renderBinder();$("#newDot").hidden=false;
  if(ownedCount()>=500&&!S.done){S.done=true;save();$("#complete").hidden=false;confetti(120)}else{const lp=pulled.find(p=>p.c.rarity=="special");}
 },900+pulled.length*120)};

// ---------- effects ----------
function flash(o){const f=$("#flash");f.style.opacity=o;setTimeout(()=>f.style.opacity=0,120)}
function burst(){const b=document.createElement("div");b.className="burst";$("#stage").appendChild(b);setTimeout(()=>b.remove(),2600)}
function confetti(n){for(let i=0;i<n;i++){const s=document.createElement("i");s.className="conf";s.textContent=["✨","⭐","🕊️","💛","🌟"][i%5];
 s.style.left=Math.random()*100+"vw";s.style.animationDuration=1.8+Math.random()*2.5+"s";s.style.animationDelay=Math.random()*.5+"s";document.body.appendChild(s);setTimeout(()=>s.remove(),5000)}}
function holoTilt(el){el.addEventListener("pointermove",e=>{const tc=el.querySelector(".tc");if(!tc)return;const r=tc.getBoundingClientRect(),x=(e.clientX-r.left)/r.width,y=(e.clientY-r.top)/r.height;
 tc.style.setProperty("--mx",x*100+"%");tc.style.setProperty("--my",y*100+"%");tc.style.transform=`rotateX(${(.5-y)*16}deg) rotateY(${(x-.5)*18}deg)`});
 el.addEventListener("pointerleave",()=>{const tc=el.querySelector(".tc");if(tc)tc.style.transform=""})}
function zoom(c){const z=$("#zoom");z.innerHTML=`<div class="zc">${cardHTML(c)}</div>`;z.hidden=false;holoTilt(z.firstChild);z.onclick=()=>z.hidden=true}

// ---------- binder ----------
const SKEYS=Object.keys(SERIES),PER=18;let cur="creation",page=0;
function renderBinder(){const n=k=>CARDS.filter(c=>c.series==k),have=k=>n(k).filter(c=>S.owned[c.id]).length;
 $("#seriesChips").innerHTML=SKEYS.map(k=>{const t=n(k).length,h=have(k);return `<button class="chip ${k==cur?"on":""} ${h==t?"full":""}" data-k="${k}">${SERIES[k][0]} <small>${h}/${t}</small><i style="width:${h/t*100}%"></i></button>`}).join("");
 const list=n(cur),pages=Math.ceil(list.length/PER);page=Math.min(page,pages-1);
 $("#seriesTitle").textContent=SERIES[cur][0];$("#seriesCount").textContent=`${have(cur)}/${list.length} collected${have(cur)==list.length?" · ✅ Complete!":""}`;
 $("#binderGrid").innerHTML=list.slice(page*PER,page*PER+PER).map(c=>S.owned[c.id]?`<div class="slot has" data-id="${c.id}">${cardHTML(c)}${S.owned[c.id]>1?`<span class="cnt">×${S.owned[c.id]}</span>`:""}</div>`:
  `<div class="slot miss r-${c.rarity}"><span class="sil">${c.motif}</span><b>${String(c.no).padStart(3,"0")}</b><small>${SYM[c.rarity]} ???</small></div>`).join("");
 $("#pgInfo").textContent=`Page ${page+1} / ${pages}`;$("#prevPg").disabled=page==0;$("#nextPg").disabled=page>=pages-1}
$("#seriesChips").onclick=e=>{const b=e.target.closest(".chip");if(b){cur=b.dataset.k;page=0;renderBinder()}};
$("#binderGrid").onclick=e=>{const s=e.target.closest(".slot.has");if(s)zoom(CARDS.find(c=>c.id==s.dataset.id))};
$("#prevPg").onclick=()=>{page--;renderBinder()};$("#nextPg").onclick=()=>{page++;renderBinder()};
document.querySelectorAll(".tab").forEach(t=>t.onclick=()=>{document.querySelectorAll(".tab,.view").forEach(x=>x.classList.remove("on"));t.classList.add("on");
 $(t.dataset.v=="open"?"#vOpen":"#vBinder").classList.add("on");if(t.dataset.v=="binder"){$("#newDot").hidden=true;renderBinder()}});

// ---------- countdown / day rollover ----------
let lastDay=today();
function tick(){const n=new Date(),m=new Date(n);m.setHours(24,0,0,0);const s=Math.floor((m-n)/1000);
 const cd=$("#cd");if(cd)cd.textContent=[s/3600,s%3600/60,s%60].map(x=>String(Math.floor(x)).padStart(2,"0")).join(":");
 if(today()!=lastDay){lastDay=today();renderTop();if(phase=="idle")renderStage()}}
setInterval(tick,1000);

// ---------- debug ----------
if(DEBUG){const d=$("#debug");d.hidden=false;const draw=()=>{d.innerHTML=`<b>🛠 Debug</b> <span>Sim date: ${today()}</span>
 <button data-a="day">⏭ Next day</button><button data-a="skip2">⏩ Skip 2 days (breaks streak)</button><button data-a="special">★ Force special</button>
 <button data-a="give">+100 cards</button><button data-a="all">Fill to 499</button><button data-a="reset">♻ Reset</button>`};draw();
 d.onclick=e=>{const a=e.target.dataset.a;if(!a)return;
  if(a=="day")S.offset++;if(a=="skip2")S.offset+=2;if(a=="special")S.forceSpecial=true;
  if(a=="give")CARDS.filter(c=>!S.owned[c.id]).sort(()=>Math.random()-.5).slice(0,100).forEach(c=>S.owned[c.id]=1);
  if(a=="all")CARDS.slice(0,499).forEach(c=>S.owned[c.id]=S.owned[c.id]||1);
  if(a=="reset"){localStorage.removeItem(KEY);location.reload();return}
  save();lastDay=today();phase="idle";draw();renderTop();renderStage();renderBinder()}}
renderTop();renderStage();renderBinder();tick();
