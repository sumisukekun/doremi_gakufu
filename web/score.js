// ドレミ楽譜の描画と再生（Web版・アプリ版・単体HTMLで共通）
(function (global) {
  const STEP = 6, W = 360, PER_ROW = 8;
  const DIA = {0:0,1:0,2:1,3:1,4:2,5:3,6:3,7:4,8:4,9:5,10:5,11:6};
  const pos = m => (Math.floor(m/12)-5)*7 + DIA[m%12];   // C4=0
  const sharp = m => [1,3,6,8,10].includes(m%12);
  const NS = 'http://www.w3.org/2000/svg';
  const el = (t,a,p) => { const e=document.createElementNS(NS,t); for(const k in a) e.setAttribute(k,a[k]); p&&p.appendChild(e); return e; };
  const wt = b => b<1 ? 0.8 : 1+(b-1)*0.5;

  function render(data, scoreBox, kbBox) {
    const notes = data.notes, noteEls = [], keyEls = {};
    scoreBox.innerHTML = ''; kbBox.innerHTML = '';
    let rows=[], beat=0, row=[];
    notes.forEach((n,i)=>{ if(beat>=PER_ROW){rows.push(row);row=[];beat=0;} row.push({...n,i}); beat+=n.beats; });
    if(row.length) rows.push(row);

    rows.forEach(r=>{
      const H=160, top=46, svg=el('svg',{viewBox:`0 0 ${W} ${H}`});
      const yOf = p => top+8*STEP-(p-2)*STEP;   // ミ(E4)が一番下の線
      for(let k=0;k<5;k++){ const y=top+k*2*STEP; el('line',{x1:8,x2:W-6,y1:y,y2:y,stroke:'#cfc6b8'},svg); }
      el('text',{x:10,y:top+7*STEP,'font-size':46,fill:'#b9ae9c'},svg).textContent='𝄞';
      const total=Math.max(r.reduce((s,n)=>s+wt(n.beats),0), PER_ROW*0.9);
      const x0=44, unit=(W-x0-10)/total; let cx=x0, cb=0;
      const xs=r.map(n=>{const x=cx+unit*0.45; cx+=wt(n.beats)*unit; return x;});
      r.forEach((n,k)=>{ cb+=n.beats; if(k<r.length-1 && Math.abs(cb%4)<1e-6){ const bx=(xs[k]+xs[k+1])/2+4;
        el('line',{x1:bx,x2:bx,y1:top,y2:top+8*STEP,stroke:'#cfc6b8'},svg);} });
      r.forEach((n,k)=>{
        const g=el('g',{class:'note'},svg), x=xs[k], p=pos(n.midi), y=yOf(p);
        for(let q=0;q>=p;q-=2) el('line',{x1:x-9,x2:x+9,y1:yOf(q),y2:yOf(q),stroke:'#8a8173'},g);
        for(let q=12;q<=p;q+=2) el('line',{x1:x-9,x2:x+9,y1:yOf(q),y2:yOf(q),stroke:'#8a8173'},g);
        el('ellipse',{class:'head',cx:x,cy:y,rx:6.5,ry:4.8,transform:`rotate(-20 ${x} ${y})`,
          fill:n.beats>=2?'#fffaf3':'#2b2b2b',stroke:'#2b2b2b','stroke-width':1.6},g);
        const up=p<6, sx=up?x+6:x-6, sy=up?y-30:y+30;
        if(n.beats<4) el('line',{x1:sx,x2:sx,y1:y,y2:sy,stroke:'#2b2b2b','stroke-width':1.4},g);
        if(n.beats===0.5) el('path',{d:up?`M${sx} ${sy} q10 8 6 20`:`M${sx} ${sy} q10 -8 6 -20`,fill:'none',stroke:'#2b2b2b','stroke-width':1.6},g);
        if(n.beats===1.5||n.beats===3) el('circle',{cx:x+11,cy:y,r:1.8,fill:'#2b2b2b'},g);
        if(sharp(n.midi)) el('text',{x:x-17,y:y+4,'font-size':13},g).textContent='♯';
        el('text',{x:x,y:H-12,'text-anchor':'middle','font-size':n.doremi.length>2?12:15,fill:'#2b2b2b'},g).textContent=n.doremi;
        noteEls[n.i]=g;
      });
      scoreBox.appendChild(svg);
    });

    // 鍵盤（使われている音域に合わせて C〜C を表示）
    const lo=Math.min(60, 12*Math.floor(Math.min(...notes.map(n=>n.midi))/12));
    const hi=Math.max(lo+24, 12*Math.ceil(Math.max(...notes.map(n=>n.midi))/12));
    const whites=[]; for(let m=lo;m<=hi;m++) if(!sharp(m)) whites.push(m);
    const ww=100/whites.length, name=['ド','','レ','','ミ','ファ','','ソ','','ラ','','シ'];
    whites.forEach((m,i)=>{const d=document.createElement('div');d.className='w';d.style.left=(i*ww)+'%';d.style.width=ww+'%';
      d.textContent=name[m%12];kbBox.appendChild(d);keyEls[m]=d;});
    for(let m=lo;m<=hi;m++) if(sharp(m)){const i=whites.indexOf(m-1);const d=document.createElement('div');d.className='b';
      d.style.left=((i+1)*ww-ww*0.3)+'%';d.style.width=(ww*0.6)+'%';kbBox.appendChild(d);keyEls[m]=d;}

    let ctx=null, timers=[];
    function hl(i){
      noteEls.forEach(g=>g&&g.classList.remove('now')); Object.values(keyEls).forEach(k=>k.classList.remove('on'));
      if(i<0) return; noteEls[i]&&noteEls[i].classList.add('now'); keyEls[notes[i].midi]&&keyEls[notes[i].midi].classList.add('on');
      noteEls[i]&&noteEls[i].scrollIntoView({block:'nearest',behavior:'smooth'});
    }
    function stop(){ timers.forEach(clearTimeout); timers=[]; if(ctx){ctx.close();ctx=null;} hl(-1); }
    function play(speed){
      stop(); ctx=new (window.AudioContext||window.webkitAudioContext)();
      const sec=60/data.bpm/speed; let t=ctx.currentTime+0.15, acc=0;
      notes.forEach((n,i)=>{
        const o=ctx.createOscillator(), g=ctx.createGain(); o.type='triangle';
        o.frequency.value=440*Math.pow(2,(n.midi-69)/12); const d=n.beats*sec;
        g.gain.setValueAtTime(0,t); g.gain.linearRampToValueAtTime(0.35,t+0.02); g.gain.exponentialRampToValueAtTime(0.001,t+d*0.95);
        o.connect(g).connect(ctx.destination); o.start(t); o.stop(t+d);
        timers.push(setTimeout(()=>hl(i),(acc+0.15)*1000)); t+=d; acc+=d;
      });
      timers.push(setTimeout(()=>hl(-1),(acc+0.3)*1000));
    }
    return { play, stop };
  }
  global.DoremiScore = { render };
})(window);
