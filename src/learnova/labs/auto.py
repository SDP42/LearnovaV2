"""
Labs made on the spot for topics no built-in lab covers.

Two ways, tried in order:

1. **AI-written** (only with a provider key): the model writes the lab's own logic — presets, inputs and a
   ``build(input) -> frames`` function — for exactly this topic. The JavaScript is syntax-checked with Node before use;
   anything that fails falls through to (2).
2. **Built from the slide** (always available, offline): the slide's structure becomes a step-through —
   a process is walked step by step with each step's explanation, a comparison is explored row by row, a timeline
   event by event, and concepts are revealed one at a time with a check-yourself prompt. The student can edit the
   points and replay.

Generated pages are cached in ``.data/labs/auto`` and served like any other lab (``/api/labs/{id}``).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from learnova.config import DATA_DIR
from learnova.labs.engine import page
from learnova.logging_config import logger

AUTO_DIR = DATA_DIR / "labs" / "auto"

_KIND = {
    "PROCESS_LINEAR": "process", "PROCESS_CYCLIC": "process", "CAUSE_EFFECT": "process", "WORKED_EXAMPLE": "process",
    "TIMELINE": "timeline", "COMPARE_TABLE": "compare", "COMPARE_VISUAL": "compare",
    "LIST_STRUCTURED": "concepts", "KEY_POINTS": "concepts", "OUTLINE": "concepts", "DEFINITION": "concepts", "LAYERS": "process",
    "FUNNEL": "process",
}

# Client-side builder for structure labs: input = {title, kind, items:[{head, body}], cols?}
_GENERIC_JS = r"""
const SLIDE = __SLIDE__;
const PRESETS=[{tag:'From this slide',name:SLIDE.title,desc:SLIDE.blurb,input:SLIDE}];
function fill(i){$('#items').value=i.items.map(x=>x.body?`${x.head}: ${x.body}`:x.head).join('\n');$('#kind').value=i.kind}
function readInputs(){return {...SLIDE,kind:$('#kind').value,items:$('#items').value.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{const k=l.indexOf(':');return k>0&&k<60?{head:l.slice(0,k).trim(),body:l.slice(k+1).trim()}:{head:l,body:''}})}}
function build(inp){
 const it=inp.items;if(it.length<2)throw new Error('Give at least two points, one per line (heading: explanation).');
 const F=[];const n=it.length;
 if(inp.kind==='compare'&&inp.cols){
  const C=inp.cols;const rows=it.map(x=>x.cells||[x.head,x.body]);
  const view=r=>'<table class="t"><tr>'+C.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr>'+rows.map((row,k)=>'<tr>'+row.map((c,j)=>`<td class="${k===r?(j===0?'cur':'src'):k<r?'ok':''}" style="text-align:left">${k<=r||j===0?esc(c):'·'}</td>`).join('')+'</tr>').join('')+'</table>';
  F.push({k:'Set up',title:inp.title,view:view(-1),explain:`<p>Compare <b>${esc(C.slice(1).join(' and '))}</b> one criterion at a time. Before each step, guess the answer, then check.</p>`});
  rows.forEach((row,k)=>F.push({k:`Row ${k+1} of ${rows.length}`,title:row[0],view:view(k),explain:'<p>'+C.slice(1).map((c,j)=>`<b>${esc(c)}:</b> ${esc(row[j+1]||'—')}`).join('<br>')+'</p><p class="small">What is the key difference here, in your own words?</p>'}));
  F.push({k:'Recap',title:'All criteria side by side',view:view(rows.length),explain:'<p>Look down each column: which option wins on most criteria, and when would you pick the other one?</p>'});
  return F}
 if(inp.kind==='process'||inp.kind==='timeline'){
  const tl=inp.kind==='timeline';
  const view=cur=>'<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:stretch">'+it.map((x,k)=>`<div style="flex:1 1 150px;min-width:140px;border-radius:12px;padding:10px 12px;border:1.5px solid ${k===cur?'var(--hl-line)':'var(--line)'};background:${k===cur?'var(--hl)':k<cur?'var(--ok-soft)':'var(--grid)'};opacity:${k>cur&&cur>=0?.55:1}"><div class="small" style="font-weight:700">${tl?'':'STEP '}${tl?esc(x.head):k+1}</div><div style="font-weight:700;margin:2px 0">${tl?'':esc(x.head)}</div><div class="small">${k<=cur&&x.body?esc(x.body):''}</div></div>${k<n-1?'<div style="align-self:center;font-weight:800;color:var(--accent)">→</div>':''}`).join('')+'</div>';
  F.push({k:'Set up',title:inp.title,view:view(-1),explain:`<p>This ${tl?'timeline has':'process has'} <b>${n}</b> ${tl?'events':'steps'}. Step through them; before each one, try to say what comes next and why.</p>`});
  it.forEach((x,k)=>F.push({k:`${tl?'Event':'Step'} ${k+1} of ${n}`,title:x.head,view:view(k),explain:`${x.body?`<p>${esc(x.body)}</p>`:''}${k>0?`<p class="small">It follows “${esc(it[k-1].head)}”${k<n-1?` and leads to “${esc(it[k+1].head)}”.`:' and completes the sequence.'}</p>`:''}`}));
  F.push({k:'Recap',title:'The whole sequence',view:view(n),explain:'<div class="formula">'+it.map((x,k)=>(tl?'':(k+1)+'. ')+x.head).join('\n')+'</div><p>Cover the screen and try to list the steps in order.</p>'});
  return F}
 const view=(cur,reveal)=>'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">'+it.map((x,k)=>`<div style="border-radius:12px;padding:12px;border:1.5px solid ${k===cur?'var(--hl-line)':'var(--line)'};background:${k===cur?'var(--hl)':k<cur||(k===cur&&reveal)?'var(--ok-soft)':'var(--grid)'}"><div style="font-weight:700">${esc(x.head)}</div><div class="small">${(k<cur||(k===cur&&reveal))&&x.body?esc(x.body):(x.body?'<i>tap Step to reveal</i>':'')}</div></div>`).join('')+'</div>';
 F.push({k:'Set up',title:inp.title,view:view(-1,false),explain:`<p><b>${n}</b> ideas on this slide. For each one, first try to explain it yourself, then reveal the slide's explanation.</p>`});
 it.forEach((x,k)=>{if(x.body)F.push({k:`Idea ${k+1} · think`,title:x.head,view:view(k,false),explain:`<p>What does <b>${esc(x.head)}</b> mean? Say it in one sentence before you continue.</p>`});
  F.push({k:`Idea ${k+1} · check`,title:x.head,view:view(k,true),explain:x.body?`<p>${esc(x.body)}</p>`:'<p>Connect this point to the one before it.</p>'})});
 F.push({k:'Recap',title:'All ideas',view:view(n,true),explain:'<p>Which two ideas are most closely connected? Explain the link.</p>'});
 return F}
"""

_GENERIC_INPUTS = ('<div class="row"><div><label for="items">Points (one per line, “heading: explanation”)</label><textarea id="items"></textarea></div>'
                   '<div><label for="kind">Walk through as</label><select id="kind" style="font:500 .9rem var(--mono);padding:8px;border-radius:8px">'
                   '<option value="process">Steps in order</option><option value="timeline">Timeline</option><option value="concepts">Ideas to check</option>'
                   '<option value="compare">Comparison</option></select></div></div>')


def _items_from(family: str, data: Dict[str, Any], bullets: List[str]) -> Tuple[str, List[Dict[str, Any]], Optional[List[str]]]:
    kind = _KIND.get(family, "concepts")
    d = data or {}
    items: List[Dict[str, Any]] = []
    cols = None
    if kind == "compare" and d.get("headers") and d.get("rows"):
        cols = [str(h) or "Criterion" for h in d["headers"]][:4]
        for r in d["rows"][:8]:
            cells = [str(c) for c in r][:len(cols)]
            items.append({"head": cells[0], "body": " · ".join(cells[1:]), "cells": cells})
    elif kind == "compare" and d.get("pros") and d.get("cons"):
        kind = "concepts"
        items = [{"head": "Advantage", "body": str(p)} for p in d["pros"][:4]] + [{"head": "Drawback", "body": str(c)} for c in d["cons"][:4]]
    elif kind in {"process", "timeline"}:
        for st in (d.get("stages") or d.get("steps") or d.get("nodes") or d.get("events") or d.get("levels") or d.get("rows") or [])[:8]:
            if isinstance(st, dict):
                head = st.get("label") or st.get("title") or st.get("step") or st.get("date") or ""
                body = st.get("detail") or st.get("reason") or st.get("description") or (st.get("title") if st.get("date") else "") or ""
                items.append({"head": str(head)[:80], "body": str(body)[:240]})
            else:
                items.append({"head": str(st)[:80], "body": ""})
    else:
        for c in (d.get("cards") or d.get("items") or d.get("groups") or [])[:8]:
            if isinstance(c, dict):
                head = c.get("heading") or c.get("term") or c.get("title") or c.get("label") or ""
                body = c.get("body") or c.get("definition") or c.get("detail") or " · ".join(map(str, c.get("items") or []))
                items.append({"head": str(head)[:80], "body": str(body)[:240]})
        if not items and d.get("term"):
            items = [{"head": str(d["term"]), "body": str(d.get("definition", ""))}] + [{"head": "Note", "body": str(x)} for x in (d.get("notes") or [])[:3]]
    if len(items) < 2:                                   # fall back to the slide's own points
        items = []
        for b in bullets[:8]:
            b = str(b).strip()
            m = re.match(r"^(.{3,60}?)\s*[:—–-]\s+(.{8,})$", b)
            items.append({"head": m.group(1), "body": m.group(2)[:240]} if m else {"head": b[:80], "body": ""})
        kind = kind if kind != "compare" else "concepts"
    items = [x for x in items if x["head"].strip()]
    return kind, items, cols


def _node_ok(js: str) -> bool:
    node = shutil.which("node")
    if not node:
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(js)
        path = fh.name
    try:
        return subprocess.run([node, "--check", path], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False
    finally:
        Path(path).unlink(missing_ok=True)


_LLM_SYSTEM = (
    "You write the logic for ONE interactive teaching lab, in plain browser JavaScript (no libraries, no network). A shared engine "
    "already provides: $(selector), esc(text), fmt(number), frac(a,b), and runs your code. You must define:\n"
    "  const PRESETS=[{tag,name,desc,input}, ...]  // 2 or 3 worked examples with concrete numbers or words\n"
    "  function fill(input)      // put input into the form fields you declare\n"
    "  function readInputs()     // read the form fields back into an input object\n"
    "  function build(input)     // return frames: [{k:'short label', title:'what this step decides', explain:'HTML: why, with the arithmetic', view:'HTML: the current state, e.g. a <table class=\"t\"> with <td class=\"cur\"> for the cell being decided, class=\"ok\"/\"src\"/\"path\" for others'}]\n"
    "Each frame is ONE small decision a beginner can follow. Compute every number in code; never hard-code results. "
    "The first frame sets up the problem; the LAST frame must have k:'Answer' and state the final result in plain words. "
    "Reply ONLY with JSON: {\"title\":\"... Lab\",\"lead\":\"one-sentence HTML intro\",\"cond\":\"the key formula or rule\",\"inputs\":\"HTML form fields with ids your fill/readInputs use (textarea/input type=text inside <div class=row><div><label>..</label>...</div></div>)\",\"ideas\":[\"3-4 key ideas\"],\"js\":\"the JavaScript\"}"
)


def _llm_lab(topic: str, text: str) -> Optional[Dict[str, Any]]:
    try:
        from learnova.ai import assist
        if not assist.llm_available():
            return None
        from learnova.providers.router import TASK_VISUAL_DATA, get_router

        raw = get_router().generate(f"Topic: {topic}\nWhat the slide says:\n{text[:1500]}", system_prompt=_LLM_SYSTEM,
                                    task=TASK_VISUAL_DATA, temperature=0.2, max_tokens=3500, timeout=60.0)
        obj = assist._json_block(raw)                                   # noqa: SLF001
    except Exception as exc:
        logger.info("labs.auto: AI lab failed: %s", exc)
        return None
    if not isinstance(obj, dict) or not all(isinstance(obj.get(k), str) for k in ("js", "inputs", "title")):
        return None
    js = obj["js"]
    if "</script" in js.lower() or re.search(r"\b(fetch|XMLHttpRequest|import\s*\(|eval|document\.cookie|localStorage)\b", js):
        return None                                                   # a lab never talks to the network or storage
    if not all(re.search(rf"\b{name}\b", js) for name in ("PRESETS", "function build", "function fill", "function readInputs")):
        return None
    if not _node_ok("const $=()=>null,esc=s=>s,fmt=s=>s,frac=(a,b)=>a+'/'+b;\n" + js):
        return None
    return obj


def lab_for_slide(title: str, text: str, family: str, data: Dict[str, Any], bullets: List[str], use_ai: bool = True) -> Optional[Dict[str, Any]]:
    """{id, name, html} for a slide, generated now (or read from the cache)."""
    clean_title = re.sub(r"\s*\(\d+/\d+\)\s*$", "", str(title)).strip() or "This topic"
    kind, items, cols = _items_from(family, data, bullets)
    try:
        from learnova.ai import assist

        ai_on = bool(use_ai and assist.llm_available())
    except Exception:
        ai_on = False
    key = hashlib.sha1(json.dumps([clean_title, kind, items, cols, ai_on], sort_keys=True).encode()).hexdigest()[:12]
    lab_id = f"auto-{key}"
    path = AUTO_DIR / f"{lab_id}.html"
    if path.is_file():
        html_text = path.read_text(encoding="utf-8")
        name = re.search(r"<title>(.*?)</title>", html_text)
        return {"id": lab_id, "name": name.group(1) if name else f"{clean_title} lab", "html": html_text}
    obj = _llm_lab(clean_title, text) if ai_on else None
    if obj:
        html_text = page(title=obj["title"][:80], h1=obj["title"][:80], topics=clean_title.lower(), lead=obj.get("lead", ""), cond=obj.get("cond", ""),
                         view="Interactive view", inputs=obj["inputs"], ideas=[str(x) for x in (obj.get("ideas") or [])][:5], js=obj["js"])
        name = obj["title"][:80]
    else:
        if len(items) < 3 or (kind == "concepts" and sum(1 for x in items if x.get("body")) < 3):
            return None                                       # too little structure to be worth a lab
        blurb = {"process": "Walk the steps in order, one at a time.", "timeline": "Move through the events in order.",
                 "compare": "Explore the comparison one criterion at a time.", "concepts": "Think first, then reveal each idea."}[kind]
        slide = {"title": clean_title, "kind": kind, "items": items, "cols": cols, "blurb": blurb}
        js = _GENERIC_JS.replace("__SLIDE__", json.dumps(slide, ensure_ascii=False).replace("</", "<\\/"))
        name = f"{clean_title} — step-through"
        html_text = page(title=name, h1=f"{clean_title}, step by step", topics=clean_title.lower(),
                         lead=f"An interactive walk-through of <b>{clean_title}</b>, built from the lecture's own content. {blurb}",
                         cond=f"{len(items)} {'steps' if kind == 'process' else 'events' if kind == 'timeline' else 'rows' if kind == 'compare' else 'ideas'}",
                         view="Walk-through", inputs=_GENERIC_INPUTS,
                         ideas=["Predict before you reveal: retrieval beats re-reading.", "Explain each point in one sentence of your own.",
                                "Edit the points below to make your own walk-through."], js=js)
    try:
        AUTO_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(html_text, encoding="utf-8")
    except OSError:
        pass
    return {"id": lab_id, "name": name, "html": html_text}


AUTO_FAMILIES = set(_KIND)
