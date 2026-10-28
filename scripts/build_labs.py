"""
Build the built-in interactive NLP labs (src/learnova/labs/builtin/*.html).

Every lab is one self-contained page with the same bench as the Region Growing lab: presets, a live view on the left, a
"what is happening" panel with Step / Back / Play on the right, and "try your own input" below. Each lab only supplies its
inputs and a ``build(input) -> frames`` function; every frame is one small decision with its explanation.

    python scripts/build_labs.py
"""

from __future__ import annotations

import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "learnova" / "labs" / "builtin"

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from learnova.labs.engine import page  # noqa: E402

# ───────────────────────────────────────────── CYK ─────────────────────────────────────────────
CYK_JS = r"""
const PRESETS=[
 {tag:'Example 1 · grammatical',name:'“the dog saw a man”',desc:'A small grammar in Chomsky normal form. S appears in the top cell.',input:{grammar:`S -> NP VP
VP -> V NP
NP -> Det N
Det -> the | a
N -> dog | man
V -> saw`,sentence:'the dog saw a man'}},
 {tag:'Example 2 · ambiguity',name:'“she eats fish with forks”',desc:'Two ways to attach the PP; CYK finds every constituent at once.',input:{grammar:`S -> NP VP
VP -> V NP | VP PP
NP -> NP PP | she | fish | forks
PP -> P NP
V -> eats
P -> with`,sentence:'she eats fish with forks'}},
 {tag:'Example 3 · rejected',name:'“dog the saw”',desc:'The words are known, but no rule builds S over the whole string.',input:{grammar:`S -> NP VP
VP -> V NP
NP -> Det N
Det -> the
N -> dog
V -> saw`,sentence:'dog the saw'}}];
function fill(i){$('#g').value=i.grammar;$('#s').value=i.sentence}
function readInputs(){return {grammar:$('#g').value,sentence:$('#s').value}}
function build(inp){
 const lex={},bin={};let rules=0;
 inp.grammar.split('\n').forEach(line=>{const m=line.split(/->|→/);if(m.length<2)return;const A=m[0].trim();
  m[1].split('|').forEach(alt=>{const s=alt.trim().split(/\s+/).filter(Boolean);if(s.length===1){(lex[s[0].toLowerCase()]=lex[s[0].toLowerCase()]||[]).push(A);rules++}
   else if(s.length===2){const k=s[0]+' '+s[1];(bin[k]=bin[k]||[]).push(A);rules++}else if(s.length>2)throw new Error(`“${line.trim()}” is not in Chomsky normal form (A → B C or A → word).`)})});
 const w=inp.sentence.trim().toLowerCase().split(/\s+/).filter(Boolean);const n=w.length;if(n<2||n>8)throw new Error('Use a sentence of 2 to 8 words.');
 const T=Array.from({length:n},()=>Array.from({length:n},()=>new Set()));const F=[];
 const view=(cur,src=[])=>{let h='<table class="t"><tr><th></th>'+w.map((x,j)=>`<th>${j+1}<br>${esc(x)}</th>`).join('')+'</tr>';
  for(let i=0;i<n;i++){h+=`<tr><th>${i+1}</th>`;for(let j=0;j<n;j++){if(j<i){h+='<td class="empty"></td>';continue}
   const c=cur&&cur[0]===i&&cur[1]===j?'cur':src.some(s=>s[0]===i&&s[1]===j)?'src':'';h+=`<td class="${c}">${T[i][j].size?esc([...T[i][j]].join(', ')):'·'}</td>`}h+='</tr>'}
  return h+'</table><p class="small">Cell (row i, column j) holds every symbol that can produce words i…j. Diagonal = single words; top-right = the whole sentence.</p>'};
 F.push({k:'Set up',title:'An empty triangular chart',view:view(null),explain:`<p>The sentence has <b>${n}</b> words and the grammar has <b>${rules}</b> rules, all of the form <b>A → B C</b> or <b>A → word</b>.</p><p>CYK fills the chart from the shortest pieces (single words) up to the whole sentence.</p>`});
 for(let i=0;i<n;i++){(lex[w[i]]||[]).forEach(A=>T[i][i].add(A));
  F.push({k:'Diagonal',title:`Word ${i+1}: “${w[i]}”`,view:view([i,i]),explain:T[i][i].size?`<p>Rules that produce “${esc(w[i])}”:</p><div class="formula">${[...T[i][i]].map(A=>A+' → '+esc(w[i])).join('\n')}</div><p>So cell (${i+1},${i+1}) = {${esc([...T[i][i]].join(', '))}}.</p>`:`<p>No rule produces “${esc(w[i])}”, so this cell stays empty — the sentence can never be accepted.</p>`})}
 for(let len=2;len<=n;len++)for(let i=0;i+len-1<n;i++){const j=i+len-1;const lines=[],used=[];
  for(let k=i;k<j;k++){const L=[...T[i][k]],R=[...T[k+1][j]];let found=false;
   L.forEach(B=>R.forEach(C=>{(bin[B+' '+C]||[]).forEach(A=>{T[i][j].add(A);found=true;lines.push(`${A} → ${B} ${C}   (words ${i+1}–${k+1} | ${k+2}–${j+1})`)})}));
   if(found)used.push([i,k],[k+1,j]);else lines.push(`split after word ${k+1}: {${L.join(', ')||'∅'}} × {${R.join(', ')||'∅'}} → no rule`)}
  F.push({k:`Span of ${len} words`,title:`Words ${i+1}–${j+1}: “${w.slice(i,j+1).join(' ')}”`,view:view([i,j],used),
   explain:`<p>Try every way to cut these ${len} words into a left part and a right part. If a rule <b>A → B C</b> has B in the left cell and C in the right cell, A covers the whole stretch.</p><div class="formula">${esc(lines.join('\n'))}</div><p>Cell (${i+1},${j+1}) = {${esc([...T[i][j]].join(', '))||'∅'}}.</p>`})}
 const ok=T[0][n-1].has('S');
 F.push({k:'Answer',title:ok?'Accepted':'Rejected',view:view([0,n-1]),explain:`<p class="verdict ${ok?'ok':'no'}">${ok?'S is in the top cell — the grammar generates this sentence ✓':'S is not in the top cell — no parse covers the whole sentence ✗'}</p><p>Top cell: {${esc([...T[0][n-1]].join(', '))||'∅'}}</p>`});
 return F}
"""

# ─────────────────────────────────────────── Viterbi ───────────────────────────────────────────
VIT_CORE = r"""
function viterbiFrames(states,obs,start,trans,emit,labelObs){
 const n=obs.length,V=[],B=[];const F=[];
 const view=(cur,cands,path)=>{let h='<table class="t"><tr><th></th>'+obs.map((o,t)=>`<th>t${t+1}<br>${esc(labelObs?labelObs[t]:o)}</th>`).join('')+'</tr>';
  states.forEach(s=>{h+=`<tr><th>${esc(s)}</th>`;for(let t=0;t<n;t++){let c='';if(path&&path[t]===s)c='path';else if(cur&&cur[0]===s&&cur[1]===t)c='cur';else if(cands&&t===cur[1]-1&&cands.includes(s))c='src';
   const v=V[t]&&V[t][s]!==undefined?V[t][s]:null;h+=`<td class="${c}">${v===null?'·':fmt(v)}${B[t]&&B[t][s]&&v!==null?`<br><span class="small">← ${esc(B[t][s])}</span>`:''}</td>`}h+='</tr>'});
  return h+'</table><p class="small">Each cell = the probability of the best path that ends in that state at that time; “← X” is the backpointer.</p>'};
 F.push({k:'Set up',title:'The trellis: one column per observation',view:view(),explain:`<p>States: <b>${esc(states.join(', '))}</b>. Observations: <b>${esc((labelObs||obs).join(' '))}</b>.</p><p>Viterbi keeps, for every state and time, only the <b>best</b> path that ends there.</p><div class="formula">v_t(s) = max_r [ v_{t-1}(r) · a(r→s) ] · b(s, o_t)</div>`});
 V[0]={};B[0]={};
 states.forEach(s=>{const p=(start[s]||0)*(emit[s+'|'+obs[0]]||0);V[0][s]=p;
  F.push({k:'First column',title:`v1(${s})`,view:view([s,0]),explain:`<p>No previous state yet: start probability × emission.</p><div class="formula">v1(${esc(s)}) = π(${esc(s)}) · b(${esc(s)}, ${esc(obs[0])}) = ${fmt(start[s]||0)} × ${fmt(emit[s+'|'+obs[0]]||0)} = ${fmt(p)}</div>`})});
 for(let t=1;t<n;t++){V[t]={};B[t]={};states.forEach(s=>{let best=-1,arg=null;const lines=[];
  states.forEach(r=>{const c=V[t-1][r]*(trans[r+'>'+s]||0);lines.push(`from ${r}: ${fmt(V[t-1][r])} × a(${r}→${s})=${fmt(trans[r+'>'+s]||0)} = ${fmt(c)}`);if(c>best){best=c;arg=r}});
  const e=emit[s+'|'+obs[t]]||0;V[t][s]=best*e;B[t][s]=arg;
  F.push({k:`Column ${t+1}`,title:`v${t+1}(${s})`,view:view([s,t],states),explain:`<p>Arrive in <b>${esc(s)}</b> from every previous state; keep the best, remember where it came from.</p><div class="formula">${esc(lines.join('\n'))}</div><p>Best is from <b>${esc(arg)}</b>; times the emission b(${esc(s)}, ${esc(obs[t])}) = ${fmt(e)}:</p><div class="formula">v${t+1}(${esc(s)}) = ${fmt(best)} × ${fmt(e)} = ${fmt(V[t][s])}</div>`})})}
 let last=states.reduce((a,s)=>V[n-1][s]>V[n-1][a]?s:a,states[0]);const path=[last];for(let t=n-1;t>0;t--)path.unshift(B[t][path[0]]);
 F.push({k:'Backtrace',title:'Follow the backpointers',view:view(null,null,path),explain:`<p>The best final cell is <b>${esc(last)}</b> (${fmt(V[n-1][last])}). Walking back along the arrows gives the whole sequence:</p><p class="verdict ok">${esc(path.join(' → '))}</p>`});
 return F}
"""

VIT_JS = VIT_CORE + r"""
const PRESETS=[
 {tag:'Example 1 · ice cream (Eisner)',name:'Hot or cold days?',desc:'Observations = ice creams eaten (1–3); hidden states = Hot / Cold weather.',input:{states:'H C',obs:'3 1 3',start:'H=0.8 C=0.2',trans:'H>H=0.6 H>C=0.4 C>H=0.5 C>C=0.5',emit:'H:1=0.2 H:2=0.4 H:3=0.4 C:1=0.5 C:2=0.4 C:3=0.1'}},
 {tag:'Example 2 · longer sequence',name:'3 3 1 1 2',desc:'See the path switch state when the evidence changes.',input:{states:'H C',obs:'3 3 1 1 2',start:'H=0.8 C=0.2',trans:'H>H=0.7 H>C=0.3 C>H=0.4 C>C=0.6',emit:'H:1=0.2 H:2=0.4 H:3=0.4 C:1=0.5 C:2=0.4 C:3=0.1'}},
 {tag:'Example 3 · three states',name:'Rainy / Cloudy / Sunny',desc:'Weather from activities: walk, shop, clean.',input:{states:'R C S',obs:'walk shop clean',start:'R=0.4 C=0.3 S=0.3',trans:'R>R=0.5 R>C=0.3 R>S=0.2 C>R=0.3 C>C=0.4 C>S=0.3 S>R=0.2 S>C=0.3 S>S=0.5',emit:'R:walk=0.1 R:shop=0.4 R:clean=0.5 C:walk=0.4 C:shop=0.3 C:clean=0.3 S:walk=0.6 S:shop=0.3 S:clean=0.1'}}];
function fill(i){['states','obs','start','trans','emit'].forEach(k=>$('#'+k).value=i[k])}
function readInputs(){const o={};['states','obs','start','trans','emit'].forEach(k=>o[k]=$('#'+k).value);return o}
function kv(str,sep){const o={};str.trim().split(/[\s,;]+/).filter(Boolean).forEach(p=>{const m=p.split('=');if(m.length!==2||isNaN(+m[1]))throw new Error(`Cannot read “${p}”. Use name=number.`);o[m[0].replace(sep,sep)]=+m[1]});return o}
function build(i){const states=i.states.trim().split(/[\s,]+/).filter(Boolean),obs=i.obs.trim().split(/[\s,]+/).filter(Boolean);
 if(states.length<2||obs.length<1||obs.length>8)throw new Error('Give 2+ states and 1–8 observations.');
 const start=kv(i.start),trans=kv(i.trans),emitRaw=kv(i.emit),emit={};Object.keys(emitRaw).forEach(k=>{const m=k.split(':');emit[m[0]+'|'+m[1]]=emitRaw[k]});
 return viterbiFrames(states,obs,start,trans,emit)}
"""

# ─────────────────────────────────────────── Bigram ────────────────────────────────────────────
BI_JS = r"""
const PRESETS=[
 {tag:'Example 1 · Jurafsky & Martin',name:'P(<s> I am Sam </s>)',desc:'The classic three-sentence corpus.',input:{corpus:'I am Sam\nSam I am\nI do not like green eggs and ham',sentence:'I am Sam',smooth:false}},
 {tag:'Example 2 · unseen pair',name:'P(<s> Sam am I </s>)',desc:'One pair never occurs, so the whole sentence gets probability 0.',input:{corpus:'I am Sam\nSam I am\nI do not like green eggs and ham',sentence:'Sam am I',smooth:false}},
 {tag:'Example 3 · add-one smoothing',name:'Same sentence, smoothed',desc:'Add 1 to every count so unseen pairs are rare, not impossible.',input:{corpus:'I am Sam\nSam I am\nI do not like green eggs and ham',sentence:'Sam am I',smooth:true}}];
function fill(i){$('#corpus').value=i.corpus;$('#sent').value=i.sentence;$('#smooth').checked=!!i.smooth}
function readInputs(){return {corpus:$('#corpus').value,sentence:$('#sent').value,smooth:$('#smooth').checked}}
function build(inp){
 const sents=inp.corpus.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>['<s>',...l.replace(/<\/?s>/g,' ').split(/\s+/).filter(Boolean),'</s>']);
 if(sents.length<1)throw new Error('Type at least one corpus sentence.');
 const q=['<s>',...inp.sentence.replace(/<\/?s>/g,' ').trim().split(/\s+/).filter(Boolean),'</s>'];if(q.length<3)throw new Error('Type a sentence to score.');
 const uni={},bi={};sents.forEach(s=>{for(let k=0;k<s.length-1;k++){uni[s[k]]=(uni[s[k]]||0)+1;const p=s[k]+' '+s[k+1];bi[p]=(bi[p]||0)+1}});
 const V=new Set();sents.forEach(s=>s.forEach(w=>{if(w!=='<s>')V.add(w)}));const Vn=V.size;const F=[];const rows=[];
 const corpusView=(a,b)=>sents.map(s=>'<div>'+s.map((w,k)=>{let c='';if(a!==undefined&&w===a&&s[k+1]===b)c='ok';else if(a!==undefined&&w===a)c='cur';else if(a!==undefined&&s[k-1]===a&&w===b)c='ok';return `<span class="tok ${c}">${esc(w)}</span>`}).join('')+'</div>').join('');
 const table=cur=>rows.length?'<table class="t" style="margin-top:12px"><tr><th>pair</th><th>count(a b)</th><th>count(a)</th><th>P(b|a)</th></tr>'+rows.map((r,k)=>`<tr><td class="${k===cur?'cur':''}">${esc(r.a)} → ${esc(r.b)}</td><td>${r.cab}</td><td>${r.ca}</td><td class="${k===cur?'cur':''}">${r.p}</td></tr>`).join('')+'</table>':'';
 F.push({k:'Set up',title:'Pad every sentence with <s> and </s>',view:corpusView(),explain:`<p>A bigram model predicts each word from the <b>one word before it</b>. The start and end markers let the first and last words have a neighbour too.</p><div class="formula">P(sentence) = Π P(w_i | w_{i-1})</div>`});
 F.push({k:'The rule',title:inp.smooth?'Add-one (Laplace) smoothing':'Maximum-likelihood estimate',view:corpusView(),explain:inp.smooth?`<div class="formula">P(b|a) = (count(a b) + 1) / (count(a) + V)</div><p>V = ${Vn} distinct words. Every pair gets one extra imaginary sighting, so nothing is impossible.</p>`:`<div class="formula">P(b|a) = count(a b) / count(a)</div><p>Count how often the pair occurs, divide by how often <b>a</b> appears as a left neighbour.</p>`});
 let total=1,num=[],den=[];
 for(let k=0;k<q.length-1;k++){const a=q[k],b=q[k+1],cab=bi[a+' '+b]||0,ca=uni[a]||0;let N=cab,D=ca;if(inp.smooth){N=cab+1;D=ca+Vn}
  const p=D?N/D:0;total*=p;num.push(N);den.push(D);rows.push({a,b,cab,ca,p:D?frac(N,D):'0'});
  F.push({k:`Pair ${k+1} of ${q.length-1}`,title:`P(${b} | ${a})`,view:corpusView(a,b)+table(rows.length-1),explain:`<p>Highlighted: every <b>${esc(a)}</b> in the corpus (yellow) and the times it is followed by <b>${esc(b)}</b> (green).</p><div class="formula">P(${esc(b)}|${esc(a)}) = ${inp.smooth?`(${cab} + 1) / (${ca} + ${Vn})`:`${cab} / ${ca}`} = ${D?frac(N,D):'0'}</div>${cab===0&&!inp.smooth?'<p class="verdict no">This pair never occurs — the whole sentence will get probability 0.</p>':''}`})}
 const nn=num.reduce((x,y)=>x*y,1),dd=den.reduce((x,y)=>x*y,1);
 F.push({k:'Answer',title:'Multiply along the sentence',view:table(-1),explain:`<div class="formula">P = ${rows.map(r=>r.p).join(' × ')}\n  = ${dd?frac(nn,dd):'0'} ≈ ${fmt(total)}</div><p class="verdict ${total>0?'ok':'no'}">${total>0?'The sentence is possible under this model.':'Zero: an unseen pair kills the product. Try add-one smoothing.'}</p>`});
 return F}
"""

# ───────────────────────────────────────── Naive Bayes WSD ─────────────────────────────────────
NB_JS = r"""
const PRESETS=[
 {tag:'Example 1 · “bass”',name:'Fish or music?',desc:'Context words around “bass” decide the sense.',input:{train:`fish: caught river fishing lake boat
fish: grilled fish dinner river
music: guitar play band sound
music: player band jazz amplifier
music: play sound low notes`,test:'play river band'}},
 {tag:'Example 2 · “bank”',name:'Money or river?',desc:'A sense with fewer examples starts with a smaller prior.',input:{train:`money: deposit loan account cash
money: account interest loan
money: cash withdraw deposit
river: water shore fishing
river: water mud boat`,test:'water boat loan'}},
 {tag:'Example 3 · movie reviews (J&M)',name:'Comedy or action?',desc:'The textbook example: the same arithmetic, different labels.',input:{train:`comedy: fun couple love love
action: fast furious shoot
comedy: couple fly fast fun fun
action: furious shoot shoot fun
action: fly fast shoot love`,test:'fast couple shoot fly'}}];
function fill(i){$('#train').value=i.train;$('#test').value=i.test}
function readInputs(){return {train:$('#train').value,test:$('#test').value}}
function build(inp){
 const docs=inp.train.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{const m=l.split(':');if(m.length<2)throw new Error(`Write each training line as sense: words (“${l}”).`);return {c:m[0].trim(),w:m.slice(1).join(':').toLowerCase().split(/[\s,]+/).filter(Boolean)}});
 const C=[...new Set(docs.map(d=>d.c))];if(C.length<2)throw new Error('Give examples for at least two senses.');
 const test=inp.test.toLowerCase().split(/[\s,]+/).filter(Boolean);const V=[...new Set(docs.flatMap(d=>d.w))];const F=[];
 const words={},count={};C.forEach(c=>{words[c]=docs.filter(d=>d.c===c).flatMap(d=>d.w);count[c]={};words[c].forEach(w=>count[c][w]=(count[c][w]||0)+1)});
 const known=test.filter(w=>V.includes(w)),unknown=test.filter(w=>!V.includes(w));const score={},parts={};
 const view=(cur)=>'<table class="t"><tr><th>word</th>'+C.map(c=>`<th>${esc(c)}<br><span class="small">${words[c].length} words</span></th>`).join('')+'</tr>'+
  known.map(w=>'<tr><th>'+esc(w)+'</th>'+C.map(c=>{const n=count[c][w]||0;const on=cur&&cur.c===c&&(cur.w===w||cur.all);return `<td class="${on?'cur':''}">${n} → ${frac(n+1,words[c].length+V.length)}</td>`}).join('')+'</tr>').join('')+
  '<tr><th>prior</th>'+C.map(c=>`<td class="${cur&&cur.c===c&&cur.prior?'cur':''}">${frac(docs.filter(d=>d.c===c).length,docs.length)}</td>`).join('')+'</tr>'+
  (Object.keys(score).length?'<tr><th>score</th>'+C.map(c=>`<td class="${cur&&cur.best===c?'path':''}">${score[c]!==undefined?fmt(score[c]):'·'}</td>`).join('')+'</tr>':'')+'</table><p class="small">Each cell: count of the word in that sense → its add-one smoothed probability.</p>';
 F.push({k:'Set up',title:`Disambiguate: ${test.join(' ')}`,view:view(),explain:`<p>We have ${docs.length} labelled contexts for ${C.length} senses and a vocabulary of <b>V = ${V.length}</b> words.</p><div class="formula">ŝ = argmax_s  P(s) · Π P(w | s)</div><p>“Naive”: every context word is treated as independent evidence.</p>${unknown.length?`<p class="small">Ignored (never seen in training): ${esc(unknown.join(', '))}</p>`:''}`});
 C.forEach(c=>{const nd=docs.filter(d=>d.c===c).length;F.push({k:'Prior',title:`P(${c})`,view:view({c,prior:true}),explain:`<p>How common is this sense before reading the context?</p><div class="formula">P(${esc(c)}) = contexts labelled ${esc(c)} / all contexts = ${nd} / ${docs.length} = ${frac(nd,docs.length)}</div>`})});
 C.forEach(c=>{let p=docs.filter(d=>d.c===c).length/docs.length;parts[c]=[frac(docs.filter(d=>d.c===c).length,docs.length)];
  known.forEach(w=>{const n=count[c][w]||0,d=words[c].length+V.length;p*=(n+1)/d;parts[c].push(frac(n+1,d));
   F.push({k:`Likelihood · ${c}`,title:`P(${w} | ${c})`,view:view({c,w}),explain:`<p>“${esc(w)}” appears <b>${n}</b> time(s) in the ${esc(c)} contexts (${words[c].length} words). Add one so an unseen word is not zero:</p><div class="formula">P(${esc(w)}|${esc(c)}) = (${n} + 1) / (${words[c].length} + ${V.length}) = ${frac(n+1,d)}</div>`})});score[c]=p;
  F.push({k:`Score · ${c}`,title:`score(${c})`,view:view({c,all:true}),explain:`<div class="formula">score(${esc(c)}) = ${parts[c].join(' × ')}\n          ≈ ${fmt(p)}</div>`})});
 const best=C.reduce((a,c)=>score[c]>score[a]?c:a,C[0]);
 F.push({k:'Answer',title:`Sense: ${best}`,view:view({best}),explain:`<p>${C.map(c=>`${esc(c)}: ${fmt(score[c])}`).join('<br>')}</p><p class="verdict ok">The larger score wins → <b>${esc(best)}</b>.</p>`});
 return F}
"""

# ─────────────────────────────────────────── POS (HMM) ─────────────────────────────────────────
POS_JS = VIT_CORE + r"""
const PRESETS=[
 {tag:'Example 1 · from the lecture',name:'“Will can spot Mary”',desc:'Learn an HMM from four tagged sentences, then tag a new one with Viterbi.',input:{corpus:`Mary/N Jane/N can/M see/V Will/N
Spot/N will/M see/V Mary/N
Will/M Jane/N spot/V Mary/N
Mary/N will/M pat/V Spot/N`,sentence:'Will can spot Mary'}},
 {tag:'Example 2 · ambiguous words',name:'“Jane will spot Will”',desc:'“will” and “spot” each have two possible tags.',input:{corpus:`Mary/N Jane/N can/M see/V Will/N
Spot/N will/M see/V Mary/N
Will/M Jane/N spot/V Mary/N
Mary/N will/M pat/V Spot/N`,sentence:'Jane will spot Will'}},
 {tag:'Example 3 · determiners',name:'“the dog can run”',desc:'A different tag set: Det, N, M, V.',input:{corpus:`the/Det dog/N can/M run/V
a/Det cat/N will/M sleep/V
the/Det cat/N can/M see/V the/Det dog/N
dogs/N run/V`,sentence:'the dog can run'}}];
function fill(i){$('#corpus').value=i.corpus;$('#sent').value=i.sentence}
function readInputs(){return {corpus:$('#corpus').value,sentence:$('#sent').value}}
function build(inp){
 const S=inp.corpus.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>l.split(/\s+/).map(t=>{const k=t.lastIndexOf('/');if(k<1)throw new Error(`Tag every word as word/TAG (“${t}”).`);return [t.slice(0,k).toLowerCase(),t.slice(k+1)]}));
 const tags=[...new Set(S.flatMap(s=>s.map(x=>x[1])))];const tr={},em={},tc={},from={};
 S.forEach(s=>{let prev='<s>';s.forEach(([w,t])=>{tr[prev+'>'+t]=(tr[prev+'>'+t]||0)+1;from[prev]=(from[prev]||0)+1;em[t+'|'+w]=(em[t+'|'+w]||0)+1;tc[t]=(tc[t]||0)+1;prev=t});tr[prev+'>'+'</s>']=(tr[prev+'>'+'</s>']||0)+1;from[prev]=(from[prev]||0)+1});
 const words=inp.sentence.toLowerCase().trim().split(/\s+/).filter(Boolean);if(!words.length||words.length>7)throw new Error('Type a sentence of 1–7 words.');
 const start={},trans={},emit={};tags.forEach(t=>{start[t]=(tr['<s>>'+t]||0)/(from['<s>']||1);tags.forEach(u=>trans[t+'>'+u]=(tr[t+'>'+u]||0)/(from[t]||1));words.forEach(w=>emit[t+'|'+w]=(em[t+'|'+w]||0)/tc[t])});
 const F=[];
 const ttab='<table class="t"><tr><th>from \\ to</th>'+tags.map(t=>`<th>${esc(t)}</th>`).join('')+'</tr>'+['<s>',...tags].map(r=>'<tr><th>'+esc(r)+'</th>'+tags.map(u=>`<td>${frac(tr[r+'>'+u]||0,from[r]||0)}</td>`).join('')+'</tr>').join('')+'</table>';
 const etab='<table class="t"><tr><th>tag \\ word</th>'+words.map(w=>`<th>${esc(w)}</th>`).join('')+'</tr>'+tags.map(t=>'<tr><th>'+esc(t)+'</th>'+words.map(w=>`<td>${frac(em[t+'|'+w]||0,tc[t])}</td>`).join('')+'</tr>').join('')+'</table>';
 F.push({k:'Step 1 · count transitions',title:'How often does one tag follow another?',view:ttab+'<p class="small">Row = previous tag (or start <s>), column = next tag; count(prev → next) / count(prev).</p>',explain:`<p>From ${S.length} tagged sentences we count tag pairs. This is the <b>transition</b> table a(t→u).</p><div class="formula">a(t→u) = count(t u) / count(t)</div>`});
 F.push({k:'Step 2 · count emissions',title:'How often does a tag produce each word?',view:etab+'<p class="small">Only the words of the sentence we will tag are shown.</p>',explain:`<p>The <b>emission</b> table b(t, w): of all the times we saw tag t, how often was the word w?</p><div class="formula">b(t, w) = count(w tagged t) / count(t)</div>`});
 const vf=viterbiFrames(tags,words,start,trans,emit);vf[0].k='Step 3 · Viterbi';vf[0].explain='<p>Now tag the new sentence: the hidden states are the tags, the observations are the words.</p>'+vf[0].explain;
 const last=vf[vf.length-1];last.k='Answer';last.title='The most likely tags';
 return F.concat(vf)}
"""


SPLIT_JS = r"""
const PRESETS=[
 {tag:'Example 1 · two objects',name:'Bright square on dark ground',desc:'One bright block: the quadtree splits around it, then merging joins the background pieces.',input:{img:`1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 8 8 8 8 1 1
1 1 8 8 8 8 1 1
1 1 8 8 8 8 1 1
1 1 8 8 8 8 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1`,t:1}},
 {tag:'Example 2 · three regions',name:'Sky, field and a barn',desc:'Three flat areas of different brightness; small noise stays inside the threshold.',input:{img:`9 9 9 9 9 9 9 9
9 9 9 8 9 9 9 9
9 9 9 9 9 9 9 9
9 9 9 9 2 2 2 2
5 5 5 5 2 2 2 2
5 5 4 5 2 2 2 2
5 5 5 5 5 5 5 5
5 5 5 5 5 5 4 5`,t:1}},
 {tag:'Example 3 · threshold matters',name:'A soft gradient',desc:'With a large threshold the whole gradient merges into one region; try T = 1 to see it stay apart.',input:{img:`1 1 2 2 3 3 4 4
1 1 2 2 3 3 4 4
1 1 2 2 3 3 4 4
1 1 2 2 3 3 4 4`,t:3}}];
function fill(i){$('#img').value=i.img;$('#t').value=i.t}
function readInputs(){return {img:$('#img').value,t:$('#t').value}}
function build(inp){
 const G=inp.img.trim().split('\n').map(r=>r.trim().split(/[\s,]+/).filter(Boolean).map(Number));
 const H=G.length,W=H?G[0].length:0,T=Number(inp.t);
 if(!H||G.some(r=>r.length!==W||r.some(v=>!Number.isFinite(v))))throw new Error('Give a grid of numbers, the same count in every row.');
 const pow=n=>n>=1&&(n&(n-1))===0;if(!pow(H)||!pow(W)||H>16||W>16)throw new Error('Rows and columns must each be 1, 2, 4, 8 or 16 (the quadtree halves them).');
 if(!(T>=0))throw new Error('The threshold T must be a number ≥ 0.');
 const lab=Array.from({length:H},()=>Array(W).fill(0));let nid=0;const regs={};
 const stats=(r0,c0,h,w)=>{let mn=Infinity,mx=-Infinity;for(let r=r0;r<r0+h;r++)for(let c=c0;c<c0+w;c++){mn=Math.min(mn,G[r][c]);mx=Math.max(mx,G[r][c])}return [mn,mx]};
 const col=id=>`hsl(${(id*67)%360} 70% 86%)`;
 const view=(cur=[],note='')=>{const cs=new Set(cur.map(x=>x.join(',')));let h='<table class="t">';
  for(let r=0;r<H;r++){h+='<tr>';for(let c=0;c<W;c++){const id=lab[r][c];const b=[];
   if(r===0||lab[r-1][c]!==id)b.push('border-top:3px solid #172131');if(c===0||lab[r][c-1]!==id)b.push('border-left:3px solid #172131');
   if(r===H-1||lab[r+1][c]!==id)b.push('border-bottom:3px solid #172131');if(c===W-1||lab[r][c+1]!==id)b.push('border-right:3px solid #172131');
   h+=`<td class="${cs.has(r+','+c)?'cur':''}" style="background:${col(id)};${b.join(';')};min-width:34px">${G[r][c]}</td>`}h+='</tr>'}
  return h+`</table><p class="small">Thick lines are region borders; each colour is one region.${note?' '+note:''}</p>`};
 const F=[];const leaves=[];
 F.push({k:'Set up',title:'The image and the rule',view:view(),explain:`<p>The image is ${H}×${W} pixels. A region is <b>homogeneous</b> when its brightest and darkest pixels differ by at most <b>T = ${T}</b>:</p><div class="formula">P(R) = TRUE  ⇔  max(R) − min(R) ≤ ${T}</div><p>Start with the whole image as one region, split what fails P, then merge neighbours whose union passes P.</p>`});
 const cells=(r0,c0,h,w)=>{const o=[];for(let r=r0;r<r0+h;r++)for(let c=c0;c<c0+w;c++)o.push([r,c]);return o};
 function split(r0,c0,h,w){const id=nid++;for(let r=r0;r<r0+h;r++)for(let c=c0;c<c0+w;c++)lab[r][c]=id;const [mn,mx]=stats(r0,c0,h,w);
  const ok=mx-mn<=T||(h===1&&w===1);
  F.push({k:'Split',title:ok?`Region ${h}×${w} at (${r0},${c0}) is homogeneous`:`Region ${h}×${w} at (${r0},${c0}) must be split`,view:view(cells(r0,c0,h,w)),
   explain:`<div class="formula">max − min = ${mx} − ${mn} = ${mx-mn} ${mx-mn<=T?'≤':'>'} ${T}</div><p>${ok?'P(R) is TRUE, so this region stays as one leaf of the quadtree.':'P(R) is FALSE: divide it into four equal quadrants and test each one.'}</p>`});
  if(ok){regs[id]={cells:cells(r0,c0,h,w),mn,mx};leaves.push(id);return}
  const h2=Math.max(1,h/2),w2=Math.max(1,w/2);
  for(const [dr,dc] of [[0,0],[0,w2],[h2,0],[h2,w2]])if(dr<h&&dc<w)split(r0+dr,c0+dc,h===1?1:h2,w===1?1:w2)}
 split(0,0,H,W);
 F.push({k:'Split done',title:`${leaves.length} homogeneous leaves`,view:view(),explain:`<p>Splitting alone leaves <b>${leaves.length}</b> square regions. Many neighbours look the same — the quadtree cut them only because of where the square boundaries fall.</p><p>Now <b>merge</b>: join two adjacent regions when their union still satisfies P.</p>`});
 let changed=true,merges=0;
 const adj=(a,b)=>regs[a].cells.some(([r,c])=>[[1,0],[-1,0],[0,1],[0,-1]].some(([dr,dc])=>{const rr=r+dr,cc=c+dc;return rr>=0&&cc>=0&&rr<H&&cc<W&&lab[rr][cc]===b}));
 while(changed&&merges<60){changed=false;const ids=Object.keys(regs).map(Number);
  outer:for(const a of ids)for(const b of ids){if(a>=b||!regs[a]||!regs[b]||!adj(a,b))continue;
   const mn=Math.min(regs[a].mn,regs[b].mn),mx=Math.max(regs[a].mx,regs[b].mx);
   if(mx-mn<=T){const before=view([...regs[a].cells,...regs[b].cells]);
    regs[b].cells.forEach(([r,c])=>lab[r][c]=a);regs[a]={cells:[...regs[a].cells,...regs[b].cells],mn,mx};delete regs[b];merges++;changed=true;
    F.push({k:'Merge',title:`Merge two neighbouring regions`,view:before,explain:`<div class="formula">max(R₁ ∪ R₂) − min(R₁ ∪ R₂) = ${mx} − ${mn} = ${mx-mn} ≤ ${T}</div><p>The highlighted regions touch and their union is still homogeneous, so they become one region.</p>`});
    break outer}}}
 const n=Object.keys(regs).length;
 F.push({k:'Result',title:`${n} region${n>1?'s':''} after merging`,view:view(),explain:`<p>Split produced ${leaves.length} leaves; ${merges} merge${merges===1?'':'s'} reduced them to <b>${n}</b>.</p><p>Split handles <b>where</b> the image changes; merge removes the artificial square borders the quadtree introduced.</p>`});
 return F}
"""


LABS = [
    dict(id="cyk_parsing", title="CYK Parsing Lab", h1="CYK parsing, cell by cell",
         topics="cyk, cyk algorithm, cyk parsing, cocke-younger-kasami, cky, chomsky normal form, cnf, triangular table, constituency parsing",
         lead="The CYK algorithm decides whether a <b>context-free grammar</b> in Chomsky normal form can generate a sentence. It fills a <b>triangular chart</b> from single words up to the whole sentence, trying every split point.",
         cond="cell(i,j) ∋ A  if  A → B C,  B ∈ cell(i,k),  C ∈ cell(k+1,j)", view="The chart", js=CYK_JS,
         inputs='<div class="row"><div><label for="g">Grammar (CNF, one rule per line, | for alternatives)</label><textarea id="g"></textarea></div><div><label for="s">Sentence</label><input id="s" type="text"></div></div>',
         ideas=["Fill by span length: 1 word, then 2, … up to n.", "For each cell try every split point k between i and j.", "A rule A → B C fires when B covers the left part and C the right part.", "Accept if S is in the top cell; ambiguity shows up as several ways to build the same symbol."]),
    dict(id="viterbi_hmm", title="Viterbi / HMM Lab", h1="Viterbi decoding, step by step",
         topics="viterbi, viterbi algorithm, hidden markov model, hmm, hmm decoding, most likely state sequence, trellis, backpointer, hmm viterbi",
         lead="A <b>hidden Markov model</b> has hidden states that emit visible observations. Viterbi finds the <b>single most likely state sequence</b> by keeping only the best path into each state at each time.",
         cond="v_t(s) = max_r v_{t-1}(r) · a(r→s) · b(s, o_t)", view="The trellis", js=VIT_JS,
         inputs='<div class="row"><div><label for="states">States</label><input id="states" type="text"><label for="obs" style="margin-top:8px">Observations</label><input id="obs" type="text"><label for="start" style="margin-top:8px">Start probabilities (state=p)</label><input id="start" type="text"></div><div><label for="trans">Transitions (from&gt;to=p)</label><textarea id="trans"></textarea><label for="emit" style="margin-top:8px">Emissions (state:observation=p)</label><textarea id="emit"></textarea></div></div>',
         ideas=["One column per observation, one row per state.", "Each cell keeps only the best incoming path (max, not sum — that would be the forward algorithm).", "Remember the backpointer: which previous state gave the max.", "Trace back from the best final cell to read the sequence."]),
    dict(id="bigram_model", title="Bigram Language Model Lab", h1="Bigram probabilities, pair by pair",
         topics="bigram, bigram model, bigram probability, bigrams, n-gram, ngram, n-gram model, language model, language modelling, add-one smoothing, laplace smoothing",
         lead="A <b>bigram language model</b> scores a sentence by multiplying the probability of each word given the word before it, estimated from <b>counts in a corpus</b>.",
         cond="P(w1…wn) ≈ Π P(w_i | w_{i-1}),   P(b|a) = count(a b) / count(a)", view="The corpus", js=BI_JS,
         inputs='<div class="row"><div><label for="corpus">Corpus (one sentence per line)</label><textarea id="corpus"></textarea></div><div><label for="sent">Sentence to score</label><input id="sent" type="text"><label style="margin-top:10px"><input id="smooth" type="checkbox"> Add-one (Laplace) smoothing</label></div></div>',
         ideas=["Pad sentences with <s> and </s>.", "P(b|a) = count(a b) / count(a).", "One unseen pair makes the whole sentence probability 0.", "Add-one smoothing: (count + 1) / (count(a) + V)."]),
    dict(id="naive_bayes_wsd", title="Naive Bayes WSD Lab", h1="Naive Bayes word sense disambiguation",
         topics="naive bayes, naive bayes classifier, word sense disambiguation, wsd, supervised wsd, sense disambiguation, applying naive bayes to wsd, multinomial naive bayes",
         lead="<b>Word sense disambiguation</b> picks the meaning of an ambiguous word (<i>bass</i>: fish or music?) from the words around it. <b>Naive Bayes</b> multiplies the sense's prior by the probability of each context word under that sense.",
         cond="ŝ = argmax_s P(s) · Π P(w | s),   P(w|s) = (count(w,s) + 1) / (|s| + V)", view="Counts and probabilities", js=NB_JS,
         inputs='<div class="row"><div><label for="train">Training contexts (sense: words)</label><textarea id="train"></textarea></div><div><label for="test">Context to disambiguate</label><input id="test" type="text"></div></div>',
         ideas=["Prior P(s): how often the sense appears in the labelled data.", "Likelihood P(w|s) with add-one smoothing so unseen words are not zero.", "Multiply prior × likelihoods; the larger score wins.", "Words never seen in training are ignored."]),
    dict(id="pos_tagging_hmm", title="POS Tagging (HMM) Lab", h1="Part-of-speech tagging with an HMM",
         topics="pos tagging, part-of-speech tagging, part of speech tagging, pos tagger, hmm pos tagging, stochastic pos tagging, transition probability, emission probability, tagging",
         lead="An <b>HMM tagger</b> learns <b>transition</b> probabilities (tag → next tag) and <b>emission</b> probabilities (tag → word) from a tagged corpus, then uses <b>Viterbi</b> to find the best tag sequence for a new sentence.",
         cond="t̂ = argmax_t Π P(t_i | t_{i-1}) · P(w_i | t_i)", view="Tables and trellis", js=POS_JS,
         inputs='<div class="row"><div><label for="corpus">Tagged corpus (word/TAG, one sentence per line)</label><textarea id="corpus"></textarea></div><div><label for="sent">Sentence to tag</label><input id="sent" type="text"></div></div>',
         ideas=["Transition a(t→u) = count(t u) / count(t), including from the start <s>.", "Emission b(t, w) = count(w tagged t) / count(t).", "The same word can carry different tags (will/M vs Will/N); the context decides.", "Viterbi over tags gives the most likely tag sequence."]),
    dict(id="region_split_merge", title="Region Splitting and Merging Lab", h1="Region splitting and merging",
         topics="region splitting and merging, region split and merge, split and merge, splitting and merging, quadtree segmentation, quad tree, region splitting, region merging, region-based segmentation, region based segmentation, image segmentation",
         lead="<b>Split and merge</b> segments an image without seeds: the image is split into quadrants until every region is <b>homogeneous</b>, then adjacent regions are <b>merged</b> when their union is still homogeneous.",
         cond="P(R) = TRUE  ⇔  max(R) − min(R) ≤ T", view="Image and regions", js=SPLIT_JS,
         inputs='<div class="row"><div><label for="img">Image (grey levels, rows on separate lines)</label><textarea id="img"></textarea></div><div><label for="t">Threshold T</label><input id="t" type="number" min="0" step="1"></div></div>',
         ideas=["Split: test P on a region; if it fails, divide it into four quadrants (a quadtree).", "Merge: join two adjacent regions when P holds for their union.", "A small T gives many regions; a large T merges real objects together.", "Unlike region growing, no seed pixels are needed."]),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for lab in LABS:
        html = page(title=lab["title"], h1=lab["h1"], topics=lab["topics"], lead=lab["lead"], cond=lab["cond"], view=lab["view"],
                    inputs=lab["inputs"], ideas=lab["ideas"], js=lab["js"])
        (OUT / f"{lab['id']}.html").write_text(html, encoding="utf-8")
        print("wrote", lab["id"])


if __name__ == "__main__":
    main()
