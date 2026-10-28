---
title: "Learnova — IPD Review Speaker Script"
subtitle: "10 slides · about 12 minutes · 4 speakers"
mainfont: "Times New Roman"
fontsize: 12pt
linestretch: 1.3
geometry: "margin=1in"
---

# Who speaks when

| Speaker | Slides | Time |
|---|---|---|
| Swayam Devendra Panchal | 1 Title, 2 Idea and problem, 3 Technical approach and tech stack | 3.5 min |
| Kawaljeet Singh Bharaj | 4 Methodology, 5 Feasibility and viability | 3 min |
| Jeevesh Bharat Bodhani | 6 Impact and benefits, 7 Literature review | 2.5 min |
| Rishit Pankajkumar Lahoti | 8 Research and references, 9 Conclusions, 10 Thank you and demo | 3 min |

Keep each slide to its time. Point at the slide while you speak; do not read the slide aloud. The words below are a guide, so
say them in your own way. Each part ends with a handover line so the next speaker knows when to start.

# Slide 1 — Title (Swayam, 20 s)

Good morning. We are Group 1 from the Department of AI and Data Science, and our project is **Learnova**. I am Swayam, and with me
are Kawaljeet, Jeevesh and Rishit. We worked under the guidance of our Head of Department, Dr. Pratik Kanani. In the next twelve
minutes we will show you the problem we saw, how we solved it, and what we measured.

# Slide 2 — Idea and the problem (Swayam, 1 min 30 s)

Every one of us has studied from lecture slides the night before an exam. Teachers reuse the same decks for years, and most of
them are walls of bullet points, pictures of equations and slides with no title at all. *(point at the red number at the top)*
In five real decks from our own courses we counted 83 slides without a title, no diagrams and no quizzes.

Tools like Gamma or Copilot make a new deck from a prompt. But a teacher does not want a new deck; they want their own deck, with
their own content, made better. And those tools rewrite the text, so facts can change.

So our idea is simple: **redesign, do not regenerate**. Learnova takes the deck the teacher already has, as PowerPoint, PDF or
Word notes, and rebuilds it. Every point is kept. Each slide gets a title that states its point, a suitable visual, an
illustration, and where it helps, a step-by-step solution, a lab or a quiz. *(point at the before-and-after picture)* This is
the same slide before and after.

What makes it different is on the right: it is faithful by design, every choice shows its reason, it has our own scoring metric,
and it works even without internet or any paid AI.

# Slide 3 — Technical approach and tech stack (Swayam, 1 min 40 s)

This is the architecture, left to right. **Inputs**: PowerPoint, PDF, Word notes or a typed topic. **Ingest**: LibreOffice
converts PowerPoint to PDF, and our slide reader, built on PyMuPDF, recovers titles, bullet levels, tables and figures. OCR with
Tesseract runs only when a page is mostly a picture.

The **engines** are our own work: the planner splits long sections, the decision engine picks one of 27 visual forms with a reason,
the layout engine measures text so nothing overflows, and the solvers compute every number exactly with SymPy.

The **AI service** uses five Gemini keys with Groq and NVIDIA as backups, and everything it writes is checked before use. If no
key works, offline rules still finish the deck. **Outputs** are an editable PowerPoint, an interactive web deck, a study pack and
a share link.

On the right is the stack: React and Vite for the front end, FastAPI and Python for the back end, SQLite for data, and pytest with
755 tests. The bottom row shows storage, the API, security and deployment.

*Handover:* Kawaljeet will now explain the method step by step and why it is feasible.

# Slide 4 — Methodology (Kawaljeet, 1 min 30 s)

Thank you, Swayam. Our method has six stages. **Read**: every word is read with its position, size and weight, so we know what is
a title and what is a bullet. **Clean**: anything repeated on many pages, like a college logo or a footer, is removed, and titles
that lost their spaces are split back into words using dynamic programming.

**Plan**: long sections are split with our algorithm CLASS, which picks the split points with the lowest cognitive load.
**Decide**: 27 detectors score each slide, and the best one decides whether it becomes a process, a timeline, a comparison, and
so on. **Enrich**: AI adds titles, diagrams and labs, but only after a check, and solved problems get exact steps. **Build and
audit**: we produce the files and then score every slide.

*(point at the formulas)* These four formulas are ours: when to use OCR, the Pedagogical Slide Fitness score, the CLASS cost, and
the rule that keeps words from breaking. On the right is how we worked: research from September to December, building until
July, and testing and writing since August.

# Slide 5 — Feasibility and viability (Kawaljeet, 1 min 30 s)

Is it feasible? It already runs. **Technically**, it works end to end with 755 automated tests. **Data**: we need no dataset; the
input is the college's own material, and we tested on seven real decks. **Economically**, it costs nothing offline, and one
department computer replaces paid AI-slide plans. **Operationally**, teachers only upload and download, and everything stays
editable.

In the middle are the seven risks we found, each rated by likelihood and impact, and the safeguard already in the code. For
example, the risk that AI invents facts is high impact, so AI text is accepted only if it uses the slide's own words, and numbers
always come from SymPy. On the right are our seven strategies, and at the bottom the adoption path: our own courses first, then
the department, then the college. You can scan these codes to check the code, tests and papers yourself.

*Handover:* Jeevesh will show what this changes for students and teachers.

# Slide 6 — Impact and benefits (Jeevesh, 1 min 20 s)

Thank you. Everything on this slide is measured, not promised. *(left to right)* Untitled slides went from 83 to zero. Slides
with a picture went up on every deck. Visual slides, quizzes, labs and illustrations went from zero to hundreds. And the time
grows in a straight line: a 216-page PDF becomes a full deck in about 35 seconds without any API key.

The impact is **educational**, because each slide has one idea and a picture, and hard topics have labs; **social**, because it is
free and works on a phone; **institutional**, because the department builds a shared library of decks and labs; and
**technological**, because AI is used only where its output can be checked. The bottom row sums it up: 98 to 100 percent of
facts kept, zero broken words, and all 26 test problems solved correctly.

# Slide 7 — Literature review (Jeevesh, 1 min 10 s)

We studied earlier work before building. DOC2PPT and D2S generate new slides from documents, but they rewrite the text and can
drop points. PPSGen keeps sentences but gives only bullets, with no visuals. Maynez and colleagues showed that model summaries
often contain content that is not in the source, which is why we keep the teacher's text and check every AI output. Garner and
Alley showed that sentence titles with visual evidence help students understand, and Mackinlay showed that visual choices can be
made by rules.

*(point at the research gap box)* The gap: no system takes an existing lecture deck, keeps every point, explains its design
choices and checks what AI adds. That is the gap Learnova fills.

*Handover:* Rishit will cover our research output and conclusions.

# Slide 8 — Research and references (Rishit, 40 s)

Thank you. These are the sources behind each part of the project, grouped by topic: why old decks fail learners, what a good
slide looks like, earlier slide generators, faithfulness, worked examples, labs, and layout rules. Every card has a QR code, so
you can open the source directly. From this work we wrote two research papers, one in IEEE format and one in Springer LNCS format,
on our own algorithms.

# Slide 9 — Conclusions obtained (Rishit, 1 min 20 s)

On the left are our objectives and what we achieved. We kept every point, removed every untitled slide, chose the right visual on
97 percent of 101 labelled slides, illustrated every topic slide, solved all test problems correctly, and had no overflow at all.
We are honest about one thing *(point at the orange row)*: our load score improved on long PDFs but is mixed on short decks,
because adding explanations makes slides longer.

Our key conclusions: redesigning beats regenerating; rules and checked AI work best together; exact maths matters, because our
solvers were right even where our own hand answers were wrong; and measuring honestly helped us find and fix real bugs. Next, we
plan a classroom study, Hindi and Marathi support, and export to Moodle and Google Classroom.

# Slide 10 — Thank you and live demo (Rishit, 40 s, then demo)

To sum up: Learnova turns old decks into new learning. Every point is kept, every slide is illustrated and every AI output is
checked. Thank you. We would be happy to show a live demo: we can upload any deck you give us right now. *(open
http://localhost:5190, upload a small PPT, show the progress, then open the web deck and the PowerPoint)* We welcome your
questions.

# Likely questions and who answers

| Question | Who | Short answer |
|---|---|---|
| How is this different from Gamma or Copilot? | Swayam | They generate a new deck from a prompt and rewrite text. We redesign the teacher's own deck and keep every point. |
| What if the AI is wrong? | Kawaljeet | AI text is used only if it reuses the slide's words; numbers come from SymPy; diagrams and lab code are checked. If a check fails, offline rules are used. |
| Does it need internet or money? | Kawaljeet | No. The whole deck can be built offline. Free Gemini keys only add extra diagrams and labs. |
| How do you know it works? | Jeevesh | 755 automated tests, 101 labelled slides, 7 real decks, and every number on the slides comes from a script in the repository. |
| What is PSF? | Jeevesh | Our Pedagogical Slide Fitness score: it combines how efficient a slide is, its cognitive load, and its coherence. |
| What is CLASS? | Kawaljeet | Our dynamic-programming algorithm that splits long sections at the points with the lowest load, instead of splitting evenly. |
| Can teachers edit the result? | Rishit | Yes. The PowerPoint uses native shapes, and the web editor lets them change any slide or visual. |
| Can it be deployed? | Swayam | It runs on one laptop or a department server. The front end can go on Vercel; the back end needs a server with LibreOffice and Tesseract. |
| What are the limitations? | Rishit | OCR on handwritten slides, PSF weights not yet calibrated with students, and no classroom study yet. These are our next steps. |
