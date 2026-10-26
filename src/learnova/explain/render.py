"""
HTML for a step-by-step explainer.

* ``explainer_html``  — a self-contained, interactive page (Next / Back / Play, keyboard, progress, big readable maths,
  highlighted changes, tables for chart-style problems). Opens on its own or inside the deck in an overlay.
* ``stepper_cards_html`` — the same steps as stacked cards for a slide, revealed one per click like every other slide.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Dict, Optional

from learnova.explain.model import Explainer


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _math_html(line: str) -> str:
    """[[changed]] becomes a highlighted span; everything else is escaped."""
    parts = re.split(r"(\[\[.*?\]\])", str(line))
    return "".join(f'<mark>{_esc(p[2:-2])}</mark>' if p.startswith("[[") and p.endswith("]]") else _esc(p) for p in parts)


def _colors(theme: Optional[Any]) -> Dict[str, str]:
    g = (lambda k, d: getattr(theme, k, d)) if theme is not None else (lambda k, d: d)
    return {"primary": g("primary_hex", "#C2502A"), "accent": g("accent_hex", "#F4B63E"), "bg": g("bg_hex", "#FFFAF5"), "card": g("card_bg_hex", "#FFFFFF"),
            "text": g("text_hex", "#402B25"), "sub": g("subtext_hex", "#715A4E")}


_CSS = """
*{box-sizing:border-box}body{margin:0;font-family:'Manrope',system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
.ex{max-width:980px;margin:0 auto;padding:22px 20px 30px}
.kind{display:inline-block;background:var(--primary);color:var(--on);font-weight:800;font-size:12px;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:4px 12px}
h1{font-family:'Bricolage Grotesque',Georgia,serif;font-size:26px;margin:10px 0 4px;line-height:1.15}
.problem{background:var(--card);border:2px solid var(--primary);border-left-width:8px;border-radius:14px;padding:14px 18px;font-size:19px;line-height:1.45;margin:12px 0 18px}
.stage{background:var(--card);border:1px solid color-mix(in srgb,var(--primary) 25%,transparent);border-radius:20px;padding:22px 24px;min-height:330px;box-shadow:0 14px 40px color-mix(in srgb,var(--primary) 14%,transparent)}
.badge{display:inline-flex;align-items:center;gap:10px;font-weight:800;color:var(--primary);font-size:14px;letter-spacing:.04em}
.badge b{background:var(--primary);color:var(--on);border-radius:50%;width:30px;height:30px;display:grid;place-items:center;font-size:15px}
.stitle{font-family:'Bricolage Grotesque',Georgia,serif;font-size:26px;font-weight:700;margin:12px 0 12px}
.math{font-family:'Cambria Math','STIX Two Math',Georgia,serif;font-size:27px;line-height:1.5;background:color-mix(in srgb,var(--primary) 7%,var(--card));border-radius:12px;padding:12px 18px;margin:0 0 14px}
.math div{white-space:pre-wrap;animation:rise .35s both}.math div:nth-child(2){animation-delay:.12s}.math div:nth-child(3){animation-delay:.24s}.math div:nth-child(4){animation-delay:.36s}
mark{background:var(--accent);color:#1f1710;border-radius:6px;padding:0 6px;animation:pop .5s both}
.explain{font-size:19px;line-height:1.6}.tip{margin-top:14px;display:inline-block;background:color-mix(in srgb,var(--accent) 30%,var(--card));border-radius:10px;padding:8px 14px;font-weight:700;font-size:15px}
table.grid{border-collapse:collapse;margin:0 0 14px;font-size:15px}table.grid td{border:1px solid color-mix(in srgb,var(--primary) 35%,transparent);padding:7px 11px;min-width:64px;text-align:center;font-family:Georgia,serif}
table.grid td.f{background:var(--accent);font-weight:800}
.bar{display:flex;align-items:center;gap:12px;margin-top:16px;flex-wrap:wrap}
button{font:inherit;cursor:pointer;border:0;border-radius:999px;padding:11px 22px;font-weight:800;font-size:16px}
.go{background:var(--primary);color:var(--on)}.go:disabled{opacity:.4;cursor:default}.alt{background:color-mix(in srgb,var(--primary) 12%,var(--card));color:var(--primary)}
button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.dots{display:flex;gap:7px;margin-left:auto;flex-wrap:wrap}.dots i{width:12px;height:12px;border-radius:50%;background:color-mix(in srgb,var(--primary) 22%,var(--card));cursor:pointer;display:block}.dots i.on{background:var(--primary);transform:scale(1.25)}.dots i.done{background:var(--accent)}
.answer{margin-top:18px;background:var(--primary);color:var(--on);border-radius:16px;padding:16px 22px;font-size:24px;font-weight:800;display:none}
.answer small{display:block;font-size:14px;font-weight:600;opacity:.85;margin-top:8px}.recap{margin:10px 0 0;padding-left:20px;font-size:15px;font-weight:600}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}@keyframes pop{from{transform:scale(.8);opacity:.2}to{transform:none;opacity:1}}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}
@media(max-width:640px){.math{font-size:21px}.stitle{font-size:21px}.explain{font-size:17px}.stage{padding:16px}}
"""


def _on_color(hex_: str) -> str:
    h = hex_.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#111111" if (0.2126 * r + 0.7152 * g + 0.0722 * b) > 150 else "#ffffff"


def explainer_html(ex: Explainer, theme: Optional[Any] = None, title: str = "") -> str:
    """A complete page; safe to save as a file, open in a browser, or load in an iframe (``srcdoc``)."""
    c = _colors(theme)
    data = json.dumps(ex.to_dict(), ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title or ex.kind.title())} — step by step</title>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Manrope:wght@500;700;800&display=swap" rel="stylesheet">
<style>:root{{--primary:{c['primary']};--accent:{c['accent']};--bg:{c['bg']};--card:{c['card']};--text:{c['text']};--sub:{c['sub']};--on:{_on_color(c['primary'])}}}{_CSS}</style></head>
<body><main class="ex"><span class="kind" id="kind"></span><h1 id="h1"></h1><div class="problem" id="problem"></div>
<section class="stage" id="stage" aria-live="polite"></section>
<div class="answer" id="answer"></div>
<div class="bar"><button class="alt" id="prev">← Back</button><button class="go" id="next">Next step →</button><button class="alt" id="play">▶ Play</button><button class="alt" id="all">Show all</button><div class="dots" id="dots"></div></div>
</main>
<script>
const EX={data};
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[m]));
const mh=l=>String(l).split(/(\\[\\[.*?\\]\\])/).map(p=>p.startsWith('[[')&&p.endsWith(']]')?'<mark>'+esc(p.slice(2,-2))+'</mark>':esc(p)).join('');
let i=0,timer=null,showAll=false;
$('kind').textContent=EX.kind;$('h1').textContent=EX.kind.charAt(0).toUpperCase()+EX.kind.slice(1)+', step by step';$('problem').textContent=EX.problem;
$('dots').innerHTML=EX.steps.map((s,k)=>'<i data-k="'+k+'" title="'+esc(s.title)+'"></i>').join('');
function stepHtml(s,k){{
  let g='';
  if(s.grid){{g='<table class="grid">'+s.grid.map((r,a)=>'<tr>'+r.map((c,b)=>'<td'+((s.focus||[]).some(f=>f[0]===a&&f[1]===b)?' class="f"':'')+'>'+esc(c)+'</td>').join('')+'</tr>').join('')+'</table>';}}
  return '<div class="badge"><b>'+(k+1)+'</b> STEP '+(k+1)+' OF '+EX.steps.length+'</div><div class="stitle">'+esc(s.title)+'</div>'+g+
   (s.math&&s.math.length?'<div class="math">'+s.math.map(m=>'<div>'+mh(m)+'</div>').join('')+'</div>':'')+
   (s.explain?'<div class="explain">'+esc(s.explain)+'</div>':'')+(s.tip?'<div class="tip">💡 '+esc(s.tip)+'</div>':'');
}}
function render(){{
  const n=EX.steps.length;
  $('stage').innerHTML=showAll?EX.steps.map((s,k)=>'<div style="margin-bottom:26px;padding-bottom:18px;border-bottom:1px dashed #0002">'+stepHtml(s,k)+'</div>').join(''):stepHtml(EX.steps[i],i);
  document.querySelectorAll('#dots i').forEach((d,k)=>{{d.className=k===i&&!showAll?'on':(k<i||showAll?'done':'')}});
  $('prev').disabled=i===0&&!showAll;$('next').disabled=i===n-1&&!showAll;
  const last=showAll||i===n-1;const a=$('answer');
  a.style.display=last?'block':'none';
  a.innerHTML='Answer: '+esc(EX.answer)+(EX.recap&&EX.recap.length?'<small>Remember:</small><ul class="recap">'+EX.recap.map(r=>'<li>'+esc(r)+'</li>').join('')+'</ul>':'');
}}
function go(d){{showAll=false;i=Math.max(0,Math.min(EX.steps.length-1,i+d));render();}}
$('next').onclick=()=>go(1);$('prev').onclick=()=>go(-1);
$('all').onclick=()=>{{showAll=!showAll;$('all').textContent=showAll?'Step by step':'Show all';render();}};
$('play').onclick=()=>{{if(timer){{clearInterval(timer);timer=null;$('play').textContent='▶ Play';return;}}$('play').textContent='❚❚ Pause';if(i===EX.steps.length-1)i=-1;timer=setInterval(()=>{{if(i>=EX.steps.length-1){{clearInterval(timer);timer=null;$('play').textContent='▶ Play';return;}}go(1);}},4200);}};
$('dots').onclick=e=>{{const k=e.target.dataset&&e.target.dataset.k;if(k!==undefined){{showAll=false;i=+k;render();}}}};
document.addEventListener('keydown',e=>{{if(e.key==='ArrowRight'||e.key===' '){{e.preventDefault();go(1);}}else if(e.key==='ArrowLeft'){{go(-1);}}}});
render();
</script></body></html>"""


def stepper_cards_html(data: Dict[str, Any], theme: Any, uid: str) -> str:
    """Slide version: the problem, then each step as a card that appears on its own click, plus a button that opens the full explainer."""
    ex = Explainer.from_dict(data)
    c = _colors(theme)
    steps = ex.steps
    if len(steps) > 8:                         # long solutions: keep the first seven and the last on the slide; the overlay has them all
        steps = steps[:7] + steps[-1:]
    cards = ""
    for k, s in enumerate(steps):
        math = "".join(f'<div style="font-family:Cambria Math,Georgia,serif;font-size:1.15rem;line-height:1.45;">{_math_html(m)}</div>' for m in s.math[:3])
        cards += (f'<div data-el="el.{k + 1}" data-build="{k + 1}" style="background:{c["card"]};border:1px solid {c["primary"]}33;border-left:6px solid {c["primary"]};border-radius:12px;padding:10px 14px;display:flex;gap:12px;align-items:flex-start;">'
                  f'<b style="flex:none;width:28px;height:28px;border-radius:50%;background:{c["primary"]};color:{_on_color(c["primary"])};display:grid;place-items:center;font-size:.9rem;">{k + 1}</b>'
                  f'<div style="min-width:0"><div style="font-weight:800;color:{c["primary"]};font-size:1rem;">{_esc(s.title)}</div>{math}'
                  f'<div style="font-size:.86rem;line-height:1.4;color:{c["text"]};margin-top:3px;">{_esc(s.explain[:190])}</div></div></div>')
    srcdoc = _esc(explainer_html(ex, theme))
    cols = "1fr 1fr" if len(steps) > 4 else "1fr"
    return (f'<div id="{uid}" style="margin-top:6px;">'
            f'<div data-el="el.0" data-build="0" style="display:flex;gap:12px;align-items:center;margin-bottom:10px;"><div style="flex:1;background:{c["primary"]}12;border:2px solid {c["primary"]};border-radius:12px;padding:8px 14px;font-size:1.1rem;font-weight:700;">{_esc(ex.problem)}</div>'
            f'<button onclick="lvExplain(\'{uid}\')" style="all:unset;cursor:pointer;background:{c["primary"]};color:{_on_color(c["primary"])};font-weight:800;border-radius:999px;padding:8px 18px;font-size:.9rem;white-space:nowrap;">Explain it step by step ▶</button></div>'
            f'<div style="display:grid;grid-template-columns:{cols};gap:9px;">{cards}</div>'
            f'<div data-el="el.{len(steps) + 1}" data-build="{len(steps) + 1}" style="margin-top:10px;background:{c["primary"]};color:{_on_color(c["primary"])};border-radius:12px;padding:9px 16px;font-weight:800;font-size:1.15rem;">Answer: {_esc(ex.answer)}</div>'
            f'<template id="{uid}-doc">{srcdoc}</template></div>')
