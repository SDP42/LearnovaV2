# What to say to sir — 5 minutes, simple words

*Read this like you're talking, not presenting. ~700 words ≈ 5 minutes.*

---

### 1. What Learnova does (20 sec)

"Learnova takes a document — notes, a chapter, a syllabus — and turns it into
a slide deck automatically. The problem I worked on is: **how do we know if a
slide it made is actually good for learning, and not just good-looking?**"

### 2. The problem with the old way (30 sec)

"Before, we scored a slide by adding up points — a bit for good length, a bit
for having a title, a bit for a nice bullet count. But that's broken: **a
slide with almost nothing on it can still score well**, because it's short and
clean. It rewards empty slides by accident."

"So I built something better, in two parts: one part **scores** a slide, the
other part **decides how much content goes on each slide** — and both parts
use the *same* idea underneath."

### 3. The scoring idea — PSF (90 sec)

"I call it PSF — Pedagogical Slide Fitness. Instead of *adding* three things
up, I **multiply** them:

- Does the slide say something new? (**Efficiency**)
- Is it easy to take in, or too crowded? (**Load**)
- Does it hang together, or ramble? (**Coherence**)

Multiplying instead of adding is the whole trick. If you *add*, one bad thing
gets hidden by two good things. If you *multiply*, one bad thing drags the
whole score down — like a chain: it's only as strong as its weakest link. A
slide that says nothing scores near zero, **even if it looks pretty**."

"And these three things aren't made up — they come from real learning-science
research: Cognitive Load Theory, which says our short-term memory can only
hold about four things at once, and Mayer's Multimedia Learning theory, which
says a slide should be focused, signposted, and not repeat itself."

"So PSF isn't a guess — it's that research turned into a number, 0 to 100."

### 4. The splitting idea — CLASS (90 sec)

"Now — once you can *score* a slide, you can also use that same score to
*build* a better slide. That's the second part, CLASS.

Say a section has ten bullet points. How many go on slide 1, how many on
slide 2? The old way just cut every N bullets — dumb, fixed.

CLASS instead tries every reasonable way to split them, and **picks the split
where slides have the lowest cognitive load overall** — using the exact same
'Load' score from PSF. And there's a small penalty for making too many tiny
slides, so it doesn't just split everything into one bullet each.

This is actually the **same technique Microsoft Word uses to break lines of
text evenly** in a paragraph — I just swapped 'line of text' for 'slide' and
'ugly line' for 'mentally overloaded slide'. It's a well-known, **provably
optimal** method — it always finds the *best* split, not just an okay one.

And because every bullet has to land on *some* slide, **nothing ever gets
silently dropped** — which matters a lot for a study tool, because a student
can't tell what's missing."

### 5. Why this matters (30 sec)

"So the contribution is: one small piece of maths — 'how loaded is this
slide' — does **two jobs**. It *judges* whether a slide is good, and it
*builds* the split that minimizes that same load. That's the novel part: the
same model is both the referee and the coach."

"And importantly — this isn't AI or machine learning making a black-box
guess. It's a transparent formula with a handful of tunable numbers, and an
algorithm with a mathematical guarantee. You can trace every decision."

### 6. One-line closer

"In short: **instead of a slide-quality score I made up, I built one grounded
in learning-science research — and then reused it to automatically decide how
to split content, with a guarantee that nothing gets lost.**"

---

## If sir interrupts with a question

**"Why multiply and not add?"**
→ "So one weak spot can't hide behind two strengths — an empty slide can't
score well just because it's short and tidy."

**"Is this trained on data / is it AI?"**
→ "No — it's a formula, not a trained model. The few numbers in it get
calibrated against real ratings later, the same way you'd calibrate any
measurement instrument, not by training a neural network."

**"What's actually new here, research-wise?"**
→ "Using the *same* load score both to judge a slide and to decide the
optimal way to build it — and proving the splitting algorithm always finds
the best split, and never drops content."
