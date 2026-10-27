"""The shared lab bench: page skeleton, styles and the Step / Back / Play engine every lab runs on.

A lab only supplies ``PRESETS``, ``fill``, ``readInputs`` and ``build(input) -> frames`` (plus its input fields); each frame is
``{k, title, explain, view}`` — one small decision, its explanation, and what to show.
"""

from __future__ import annotations

CSS = r"""
:root{--bg:#f3f5f8;--paper:#fff;--ink:#172131;--muted:#5d6879;--line:#d8dee8;--grid:#e8edf4;--accent:#2457c5;--accent-soft:#dfe8fb;
--ok:#16845b;--ok-soft:#dcf3e8;--no:#c23b2c;--no-soft:#fbe3df;--hl:#fff1c2;--hl-line:#e0a800;
--display:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;--body:"Atkinson Hyperlegible","Segoe UI",system-ui,sans-serif;--mono:"JetBrains Mono",ui-monospace,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f141c;--paper:#161d28;--ink:#e5eaf2;--muted:#9aa5b6;--line:#2a3443;--grid:#1d2633;
--accent:#7ea6f5;--accent-soft:#1d2b47;--ok:#4fd39b;--ok-soft:#173528;--no:#f2867a;--no-soft:#3a1f1c;--hl:#3a3216;--hl-line:#d8a72a;color-scheme:dark}}
*{box-sizing:border-box}body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:16px;line-height:1.55;margin:0}
.wrap{max-width:1160px;margin:0 auto;padding:26px 16px 70px}
h1,h2,h3{font-family:var(--display);line-height:1.15;margin:0}h1{font-size:2.3rem;font-weight:750}h2{font-size:1.4rem;margin-bottom:10px}h3{font-size:1.05rem}
.lead{color:var(--muted);max-width:72ch;margin:8px 0 18px}.lead b{color:var(--ink)}
.cond{display:inline-block;font:700 .95rem var(--mono);background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:6px 12px;margin:0 0 16px}
.presets{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:18px}
.preset{all:unset;cursor:pointer;background:var(--paper);border:1.5px solid var(--line);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:3px}
.preset:hover{border-color:var(--accent)}.preset[aria-pressed="true"]{border-color:var(--accent);box-shadow:inset 0 0 0 1.5px var(--accent)}
.preset .tag{font:700 .7rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}.preset strong{font-family:var(--display)}.preset .d{font-size:.88rem;color:var(--muted)}
.lab{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:18px;align-items:start}@media (max-width:880px){.lab{grid-template-columns:minmax(0,1fr)}}
.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:16px}
.status .k{font:700 .72rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.status h3{margin:4px 0 8px;font-size:1.2rem}.status .ex{min-height:96px}.status .ex p{margin:0 0 8px}
.formula{font:600 .9rem var(--mono);background:var(--grid);border-radius:8px;padding:8px 10px;margin:6px 0;white-space:pre-wrap;overflow-x:auto}
.ctrls{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.btn{all:unset;cursor:pointer;font-weight:700;border-radius:999px;padding:8px 16px;background:var(--accent-soft);color:var(--accent)}.btn.pri{background:var(--accent);color:#fff}
.btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.btn[disabled]{opacity:.45;cursor:default}
.bar{height:6px;border-radius:3px;background:var(--grid);margin-top:12px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .25s}
.count{font:600 .8rem var(--mono);color:var(--muted);margin-top:6px}
table.t{border-collapse:separate;border-spacing:4px;font:500 .9rem var(--mono);margin:0 auto}
table.t th{font:700 .72rem var(--mono);color:var(--muted);padding:2px 6px;text-align:center}
table.t td{background:var(--grid);border:1.5px solid var(--line);border-radius:7px;padding:6px 8px;text-align:center;min-width:52px;transition:background .25s,border-color .25s}
table.t td.empty{background:transparent;border-color:transparent}
table.t td.cur{background:var(--hl);border-color:var(--hl-line);box-shadow:0 0 0 2px var(--hl-line)}
table.t td.src{background:var(--accent-soft);border-color:var(--accent)}
table.t td.ok{background:var(--ok-soft);border-color:var(--ok)}table.t td.no{background:var(--no-soft);border-color:var(--no)}
table.t td.path{background:var(--ok-soft);border-color:var(--ok);font-weight:700}
.small{font-size:.8rem;color:var(--muted)}
.tok{display:inline-block;font:600 .9rem var(--mono);padding:2px 7px;margin:2px;border-radius:6px;background:var(--grid);border:1.5px solid var(--line)}
.tok.cur{background:var(--hl);border-color:var(--hl-line)}.tok.ok{background:var(--ok-soft);border-color:var(--ok)}
.viewtitle{font:700 .72rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:2px 0 10px}
.scroll{overflow-x:auto}
.own{margin-top:18px}.own .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.own label{display:block;font:700 .78rem var(--mono);color:var(--muted);margin-bottom:4px}
.own textarea,.own input[type=text]{width:100%;font:500 .9rem var(--mono);background:var(--bg);color:var(--ink);border:1.5px solid var(--line);border-radius:8px;padding:8px}
.own textarea{min-height:120px}.err{color:var(--no);font-weight:700;margin-top:8px}
.ideas{margin-top:18px}.ideas ul{margin:0;padding-left:20px}.ideas li{margin:4px 0}
.verdict{font-weight:800}.verdict.ok{color:var(--ok)}.verdict.no{color:var(--no)}
"""

ENGINE = r"""
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=v=>{if(v===0)return '0';if(Math.abs(v)>=0.001)return (+v.toPrecision(4)).toString();return v.toExponential(2)};
function gcd(a,b){return b?gcd(b,a%b):a}
const frac=(a,b)=>{if(b===0)return '—';const g=gcd(a,b)||1;return b/g===1?String(a/g):`${a/g}/${b/g}`};
const LAB={frames:[],i:0,timer:null};
function show(){const f=LAB.frames[LAB.i];if(!f)return;$('#view').innerHTML=f.view||'';$('#k').textContent=f.k||'Step';$('#st').textContent=f.title||'';
$('#ex').innerHTML=f.explain||'';const n=LAB.frames.length;$('#count').textContent=`Step ${LAB.i+1} of ${n}`;$('.bar i').style.width=(100*(LAB.i+1)/n)+'%';
$('#back').disabled=LAB.i===0;$('#step').disabled=LAB.i>=n-1}
function go(d){LAB.i=Math.max(0,Math.min(LAB.frames.length-1,LAB.i+d));show()}
function stop(){if(LAB.timer){clearInterval(LAB.timer);LAB.timer=null;$('#play').textContent='▶ Play'}}
function play(){if(LAB.timer){stop();return}$('#play').textContent='❚❚ Pause';LAB.timer=setInterval(()=>{if(LAB.i>=LAB.frames.length-1){stop();return}go(1)},+$('#speed').value)}
function run(input){stop();$('#err').textContent='';try{LAB.frames=build(input);LAB.i=0;show()}catch(e){$('#err').textContent=e.message||String(e)}}
function usePreset(k){document.querySelectorAll('.preset').forEach((b,j)=>b.setAttribute('aria-pressed',j===k?'true':'false'));fill(PRESETS[k].input);run(PRESETS[k].input)}
document.addEventListener('DOMContentLoaded',()=>{
 $('#presets').innerHTML=PRESETS.map((p,k)=>`<button class="preset" aria-pressed="false" data-k="${k}"><span class="tag">${esc(p.tag)}</span><strong>${esc(p.name)}</strong><span class="d">${esc(p.desc)}</span></button>`).join('');
 document.querySelectorAll('.preset').forEach(b=>b.onclick=()=>usePreset(+b.dataset.k));
 $('#step').onclick=()=>{stop();go(1)};$('#back').onclick=()=>{stop();go(-1)};$('#play').onclick=play;$('#reset').onclick=()=>{stop();LAB.i=0;show()};
 $('#end').onclick=()=>{stop();LAB.i=LAB.frames.length-1;show()};$('#runown').onclick=()=>{document.querySelectorAll('.preset').forEach(b=>b.setAttribute('aria-pressed','false'));run(readInputs())};
 document.addEventListener('keydown',e=>{if(e.target.closest('textarea,input'))return;if(e.key==='ArrowRight'||e.key===' '){e.preventDefault();stop();go(1)}else if(e.key==='ArrowLeft'){stop();go(-1)}});
 usePreset(0)});
"""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="learnova-topics" content="__TOPICS__">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,750&family=Atkinson+Hyperlegible:wght@400;700&family=JetBrains+Mono:wght@500;700&display=swap">
<style>__CSS__</style>
</head>
<body>
<main class="wrap">
<h1>__H1__</h1>
<p class="lead">__LEAD__</p>
<div class="cond">__COND__</div>
<p class="small">Choose an example, then press <b>Step</b> to watch one decision at a time, or <b>Play</b> to animate. Arrow keys work too. Use your own numbers in <b>Try your own input</b> below.</p>
<div class="presets" id="presets"></div>
<section class="lab">
 <div class="card"><div class="viewtitle">__VIEWTITLE__</div><div id="view" class="scroll"></div></div>
 <div class="card status" aria-live="polite">
  <div class="k" id="k">Step</div><h3 id="st"></h3><div class="ex" id="ex"></div>
  <div class="ctrls"><button class="btn" id="back">← Back</button><button class="btn pri" id="step">Step →</button><button class="btn" id="play">▶ Play</button>
  <button class="btn" id="end">Run to end</button><button class="btn" id="reset">Reset</button></div>
  <label class="small" style="display:block;margin-top:10px">Speed <input id="speed" type="range" min="300" max="2200" step="100" value="1100" style="vertical-align:middle;direction:rtl"></label>
  <div class="bar"><i></i></div><div class="count" id="count"></div>
 </div>
</section>
<section class="card own"><h2>Try your own input</h2>__INPUTS__<div class="ctrls"><button class="btn pri" id="runown">Run with my input</button></div><div class="err" id="err"></div></section>
<section class="card ideas"><h2>Key ideas</h2><ul>__IDEAS__</ul></section>
</main>
<script>
__ENGINE__
__JS__
</script>
</body>
</html>
"""



def page(*, title: str, h1: str, topics: str, lead: str, cond: str, view: str, inputs: str, ideas: list, js: str) -> str:
    def li(t: str) -> str:
        return "<li>" + t.replace("<", "&lt;").replace(">", "&gt;") + "</li>"

    return (PAGE.replace("__CSS__", CSS).replace("__ENGINE__", ENGINE).replace("__JS__", js).replace("__TOPICS__", topics)
            .replace("__TITLE__", title).replace("__H1__", h1).replace("__LEAD__", lead).replace("__COND__", cond)
            .replace("__VIEWTITLE__", view).replace("__INPUTS__", inputs).replace("__IDEAS__", "".join(li(i) for i in ideas)))
