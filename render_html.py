"""採譜結果(JSON) → ドレミ付きかんたん楽譜ページ(HTML1枚)
使い方: python3 render_html.py out.json -o score.html --title "曲名"
"""
import argparse, json

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — ドレミ楽譜</title>
<style>
:root{--bg:#fffaf3;--ink:#2b2b2b;--sub:#8a8173;--acc:#e8673a;--line:#cfc6b8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Hiragino Maru Gothic ProN","Rounded Mplus 1c",system-ui,sans-serif}
header{padding:18px 16px 6px}h1{font-size:20px;margin:0}.meta{color:var(--sub);font-size:13px;margin-top:4px}
.ctrl{display:flex;gap:8px;align-items:center;padding:8px 16px;flex-wrap:wrap;position:sticky;top:0;background:var(--bg);z-index:2;border-bottom:1px solid #eee3d3}
button{border:0;border-radius:999px;padding:10px 18px;font-size:15px;background:var(--acc);color:#fff;font-weight:700}
button.sec{background:#efe6d8;color:var(--ink)}label{font-size:13px;color:var(--sub)}input[type=range]{width:110px;accent-color:var(--acc)}
#score{padding:8px 4px 12px;overflow-x:hidden}svg{display:block;width:100%;height:auto}
.kb{position:relative;height:90px;margin:6px 12px 24px;max-width:520px}
.w,.b{position:absolute;border:1px solid #9a9184;border-radius:0 0 6px 6px}
.w{background:#fff;height:90px;display:flex;align-items:flex-end;justify-content:center;font-size:11px;color:var(--sub);padding-bottom:4px}
.b{background:#333;height:56px;z-index:1}.on{background:var(--acc)!important;color:#fff!important}
.note{transition:fill .1s}.now .head{fill:var(--acc)}.now text{fill:var(--acc);font-weight:700}
footer{color:var(--sub);font-size:12px;padding:0 16px 30px}
</style></head><body>
<header><h1>__TITLE__</h1><div class="meta" id="meta"></div></header>
<div class="ctrl"><button id="play">▶ 再生</button><button class="sec" id="stop">■</button>
<label>はやさ <input type="range" id="spd" min="0.5" max="1.5" step="0.1" value="1"> <span id="spdv">100%</span></label></div>
<div id="score"></div>
<div class="kb" id="kb"></div>
<footer>自動採譜の結果です。音がずれている場合があります。個人の練習用にご利用ください。</footer>
<script>
const DATA = __DATA__;
const notes = DATA.notes;
document.getElementById('meta').textContent =
  `テンポ ${DATA.bpm} ・ ${notes.length}音` + (DATA.original_key ? ` ・ 元のキー「${DATA.original_key}」→ ハ長調に直しました` : '');

// ---- 五線譜（1段4小節、音符の下にドレミ） ----
const STEP = 6;                       // 五線の半間隔(px)
const DIA = {0:0,1:0,2:1,3:1,4:2,5:3,6:3,7:4,8:4,9:5,10:5,11:6};
function pos(m){ return (Math.floor(m/12)-5)*7 + DIA[m%12]; }  // C4=0
const sharp = m => [1,3,6,8,10].includes(m%12);
const W = 360, PER_ROW = 8;           // 1段=8拍（2小節）
let rows = [], beat = 0, row = [];
notes.forEach((n,i)=>{ if(beat>=PER_ROW){rows.push(row);row=[];beat=0;} row.push({...n,i,at:beat}); beat+=n.beats; });
if(row.length) rows.push(row);
const svgNS='http://www.w3.org/2000/svg';
const el=(t,a,p)=>{const e=document.createElementNS(svgNS,t);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e;};
const score=document.getElementById('score'); const noteEls=[];
rows.forEach(r=>{
  const H=160, top=46, svg=el('svg',{viewBox:`0 0 ${W} ${H}`});
  const yOf=p=> top+8*STEP - (p-2)*STEP;  // ミ(E4)が一番下の線
  for(let k=0;k<5;k++){ const y=top+k*2*STEP; el('line',{x1:8,x2:W-6,y1:y,y2:y,stroke:'#cfc6b8','stroke-width':1},svg); }
  el('text',{x:10,y:top+7*STEP,'font-size':46,fill:'#b9ae9c'},svg).textContent='𝄞';
  // 短い音にも最低限の幅を確保する配置（8分=0.8, 4分=1, 2分=1.5 …）
  const wt=b=> b<1 ? 0.8 : 1+(b-1)*0.5;
  const total=Math.max(r.reduce((s,n)=>s+wt(n.beats),0), PER_ROW*0.9);
  const x0=44, unit=(W-x0-10)/total; let cx=x0, cb=0;
  const xs=r.map(n=>{const x=cx+unit*0.45; cx+=wt(n.beats)*unit; return x;});
  r.forEach((n,k)=>{ cb+=n.beats; if(k<r.length-1 && Math.abs(cb%4)<1e-6){ const bx=(xs[k]+xs[k+1])/2+4;
    el('line',{x1:bx,x2:bx,y1:top,y2:top+8*STEP,stroke:'#cfc6b8'},svg);} });
  r.forEach((n,k)=>{
    const g=el('g',{class:'note'},svg), x=xs[k], p=pos(n.midi), y=yOf(p);
    for(let q=0; q>=p; q-=2) if(q<=0) el('line',{x1:x-9,x2:x+9,y1:yOf(q),y2:yOf(q),stroke:'#8a8173'},g); // 加線(下)
    for(let q=12; q<=p; q+=2) el('line',{x1:x-9,x2:x+9,y1:yOf(q),y2:yOf(q),stroke:'#8a8173'},g);       // 加線(上)
    const open=n.beats>=2;
    el('ellipse',{class:'head',cx:x,cy:y,rx:6.5,ry:4.8,transform:`rotate(-20 ${x} ${y})`,fill:open?'#fffaf3':'#2b2b2b',stroke:'#2b2b2b','stroke-width':1.6},g);
    const up=p<6, sx=up?x+6:x-6, sy=up?y-30:y+30;
    if(n.beats<4) el('line',{x1:sx,x2:sx,y1:y,y2:sy,stroke:'#2b2b2b','stroke-width':1.4},g);
    if(n.beats===0.5) el('path',{d:up?`M${sx} ${sy} q10 8 6 20`:`M${sx} ${sy} q10 -8 6 -20`,fill:'none',stroke:'#2b2b2b','stroke-width':1.6},g);
    if(n.beats===1.5||n.beats===3) el('circle',{cx:x+11,cy:y,r:1.8,fill:'#2b2b2b'},g);
    if(sharp(n.midi)) el('text',{x:x-17,y:y+4,'font-size':13},g).textContent='♯';
    el('text',{x:x,y:H-12,'text-anchor':'middle','font-size':n.doremi.length>2?12:15,fill:'#2b2b2b'},g).textContent=n.doremi;
    noteEls[n.i]=g;
  });
  score.appendChild(svg);
});

// ---- 鍵盤（C4〜C6） ----
const kb=document.getElementById('kb'), keyEls={}, LO=60, HI=84;
const whites=[]; for(let m=LO;m<=HI;m++) if(!sharp(m)) whites.push(m);
const ww=100/whites.length;
whites.forEach((m,i)=>{const d=document.createElement('div');d.className='w';d.style.left=(i*ww)+'%';d.style.width=ww+'%';
  d.textContent=['ド','','レ','','ミ','ファ','','ソ','','ラ','','シ'][m%12];kb.appendChild(d);keyEls[m]=d;});
for(let m=LO;m<=HI;m++) if(sharp(m)){const i=whites.indexOf(m-1);const d=document.createElement('div');d.className='b';
  d.style.left=((i+1)*ww-ww*0.3)+'%';d.style.width=(ww*0.6)+'%';kb.appendChild(d);keyEls[m]=d;}

// ---- 再生（WebAudio） ----
let ctx, timers=[];
function hl(i){ noteEls.forEach(g=>g&&g.classList.remove('now')); Object.values(keyEls).forEach(k=>k.classList.remove('on'));
  if(i<0) return; noteEls[i]&&noteEls[i].classList.add('now'); const k=keyEls[notes[i].midi]; k&&k.classList.add('on');
  noteEls[i]&&noteEls[i].scrollIntoView({block:'nearest',behavior:'smooth'}); }
function stop(){ timers.forEach(clearTimeout); timers=[]; if(ctx){ctx.close();ctx=null;} hl(-1); }
document.getElementById('stop').onclick=stop;
const spd=document.getElementById('spd'); spd.oninput=()=>document.getElementById('spdv').textContent=Math.round(spd.value*100)+'%';
document.getElementById('play').onclick=()=>{
  stop(); ctx=new (window.AudioContext||window.webkitAudioContext)();
  const sec=60/DATA.bpm/parseFloat(spd.value); let t=ctx.currentTime+0.15, acc=0;
  notes.forEach((n,i)=>{
    const o=ctx.createOscillator(), g=ctx.createGain(); o.type='triangle';
    o.frequency.value=440*Math.pow(2,(n.midi-69)/12); const d=n.beats*sec;
    g.gain.setValueAtTime(0,t); g.gain.linearRampToValueAtTime(0.35,t+0.02); g.gain.exponentialRampToValueAtTime(0.001,t+d*0.95);
    o.connect(g).connect(ctx.destination); o.start(t); o.stop(t+d);
    timers.push(setTimeout(()=>hl(i),(acc+0.15)*1000)); t+=d; acc+=d;
  });
  timers.push(setTimeout(()=>hl(-1),(acc+0.3)*1000));
};
</script></body></html>"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("-o", "--out", default="score.html"); ap.add_argument("--title", default="かんたん楽譜")
    a = ap.parse_args()
    data = json.load(open(a.json))
    html = TEMPLATE.replace("__TITLE__", a.title).replace("__DATA__", json.dumps(data, ensure_ascii=False))
    open(a.out, "w").write(html)
    print("→", a.out)
