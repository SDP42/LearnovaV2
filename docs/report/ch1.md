# Certificate {.unnumbered}

This is to certify that the project report entitled **"Learnova: Redesigning Outdated Lecture Presentations into Modern, Illustrated and Interactive Teaching Decks"** is a bonafide record of the Interdisciplinary Project work carried out by Swayam Devendra Panchal (60018240013), Kawaljeet Singh Bharaj (60018240016), Jeevesh Bharat Bodhani (60018240096) and Rishit Pankajkumar Lahoti (6001840101) of the Department of Artificial Intelligence and Data Science, Dwarkadas J. Sanghvi College of Engineering, Mumbai, during the academic year 2025–2026 and the odd semester of 2026–2027, under our guidance and supervision.

\

|  |  |
|---|---|
| Project Mentor: ______________________ | Head of Department: Dr. Pratik Kanani |
| Signature: ______________________ | Signature: ______________________ |
| Date: ______________________ | Date: ______________________ |


# Acknowledgement {.unnumbered}

We express our sincere gratitude to Dr. Pratik Kanani, Head of the Department of Artificial Intelligence and Data Science, for providing the facilities, encouragement and academic direction that made this project possible. We are grateful to our project mentor for regular reviews, for pointing us towards real lecture material when our early prototype worked only on clean sample files, and for the critical questions that shaped the design of the system. We thank the faculty members of the department whose lecture decks we used to test Learnova, and our classmates who tried early versions of the application and told us honestly what confused them. Finally, we thank our families for their patience during the many evenings and weekends that went into this work.


# Abstract {.unnumbered}

Lecture slides are the main study material in most engineering courses, yet a large share of the decks in use have been reused for years. They are dense bullet lists; equations, graphs and diagrams are pasted as pictures; many slides have no title; and nothing on the slide lets a student check their understanding. Redesigning a deck by hand takes a teacher several hours per lecture, and the artificial-intelligence presentation tools now available solve a different problem: they generate new slides from a prompt, and in doing so they paraphrase the teacher's points, merge or drop list items and lose the original figures. There is no tool that takes the deck a teacher already uses and improves it without changing what it says.

This report presents **Learnova**, a web platform that rebuilds an existing lecture deck — a PowerPoint file, a slide PDF, Word notes or a typed topic — into an editable PowerPoint presentation, an interactive web deck and a study pack, while keeping every point of the original. The system reads slide decks page by page, recovering titles, bullet levels, tables and figures, and uses optical character recognition only when a picture-only slide can be read reliably. An explainable rule-based Content Decision Engine chooses a suitable visual form for every slide — a process flow, a timeline, a comparison table, a definition, a chart or cards — and records the reason for its choice. A layout engine measures text glyph by glyph so that no word is ever broken across lines. Every topic slide receives an illustration: the teacher's own figure, a diagram written by a large language model and validated before use, or an offline illustration; each illustration is published as an HTML page linked from the PowerPoint. Checkpoint quizzes, exact step-by-step solutions to problems and interactive laboratories for difficult topics turn reading into practice. Two original methods support the design: Pedagogical Slide Fitness (PSF), a slide-quality metric derived from cognitive-load and multimedia-learning theory, and CLASS, a dynamic program that splits an overloaded slide into consecutive slides of minimum total cognitive load.

Learnova was evaluated on gold sets of 101 labelled slides and on seven real course decks of 15 to 216 slides. The decision engine selected an appropriate visual for 96.8–97.4% of slides in under one millisecond per slide. The rebuilt decks retained 98–100% of the numeric and named facts of their sources, the number of untitled slides across five decks fell from 83 to zero, and no slide was flagged for overflowing or broken text. The step-by-step solvers answered all 26 problems of a held-out benchmark correctly, and CLASS was never worse than even splitting while being strictly better on 37% of overloaded sections. The system works with free API keys when they are available and completely offline when they are not.

**Keywords:** educational technology, presentation redesign, document structure recovery, explainable artificial intelligence, cognitive load, large language models, interactive learning.


# Introduction

## Background

Slides have become the backbone of classroom teaching in engineering colleges. A typical course is taught from a set of decks prepared once and refined slowly over several years; the same decks are shared with students and become their primary revision material before internal and university examinations. When we collected the decks used in three of our own courses — Natural Language Processing, Machine Learning, and Image Processing and Computer Vision — we found the same pattern in almost all of them. Slides carried long bullet lists that read like notes rather than explanations. Important equations, derivations and diagrams had been copied from textbooks as screenshots, so they could not be searched, resized or explained. Many slides had no title, or a title that only repeated the topic name, so a student flipping through the deck could not tell what each slide was supposed to teach. None of the decks contained anything a student could interact with: there were no questions to check understanding, no worked steps that a beginner could follow, and no way to try an algorithm on a different input.

These observations match what educational research has reported for a long time. Cognitive load theory explains that working memory can hold only a few new elements at once, so a slide that presents twelve unconnected bullet points overloads the learner. Mayer's principles of multimedia learning show that people learn better when a picture appears next to the words that explain it, when irrelevant material is removed and when the structure of the material is signalled clearly. Studies of the assertion–evidence approach show that slides with a full-sentence headline supported by a visual are understood and remembered better than slides with a topic title and bullets. The problem, therefore, is not that teachers do not know what a good slide looks like; it is that redesigning hundreds of existing slides by hand is not practical.

## Motivation

Two developments made this project timely. First, large language models can now write fluent text, propose titles and even draw simple diagrams, which suggested that much of the redesign work could be automated. Second, the tools that apply these models to presentations — Gamma, Microsoft Copilot in PowerPoint, Gemini in Google Slides and Canva Magic Design — had become widely available. When we tried them on our lecture decks, however, the results were disappointing for teaching. The tools produced attractive slides, but they rewrote the teacher's wording, merged or dropped items from lists, lost the original figures and equations, and offered no way to check what had changed. They also required a paid subscription and a continuous internet connection. For a study aid, a deck that looks better but silently loses the point that will be asked in the examination is worse than the original.

Our motivation was to build a tool that a teacher could trust: one that improves how a deck is presented while guaranteeing that what the deck says is preserved, that explains each of its design decisions, and that adds the interactive elements research recommends — all without depending on paid services.

## Problem Statement

Faculty members need a way to turn their existing lecture decks into modern, readable and interactive teaching material without redesigning them by hand and without losing or altering their content. Existing AI presentation tools generate new decks from prompts, are not faithful to the source, ignore picture-only and equation slides, provide no interaction and depend on paid cloud services. The problem addressed by this project is therefore:

> *To design and build a system that takes an existing lecture deck in any common format and rebuilds it as an illustrated, interactive and editable deck that preserves every point of the source, explains its design decisions, and works both with and without AI services.*

## Objectives

The project set out to achieve the following objectives:

1. **Faithful reading of real lecture material.** Read PowerPoint files, slide PDFs, Word documents and typed topics, and recover the title, bullet levels, tables, figures and picture-only slides of every page, including decks with symbol-font bullets, repeated logos and missing titles.
2. **Explainable visual redesign.** Choose a suitable visual form for every slide using inspectable rules, and record the reason and confidence of every choice so that a teacher can review it.
3. **Content preservation.** Keep all of the source content: no item dropped, no fact invented and no word broken across lines, and measure this on real decks.
4. **Illustration on every slide.** Give every topic slide a relevant picture, preferring the teacher's own figures, and make each illustration available as a page that can be opened from the PowerPoint.
5. **Interactivity.** Add checkpoint quizzes, exact step-by-step solutions for problems and interactive laboratories for difficult topics.
6. **Dependability.** Use AI services where they improve the result and can be checked, and fall back to offline logic whenever a key is missing, rejected or exhausted.

## Scope

Learnova handles lecture material written in English for engineering and science subjects. The inputs supported are PowerPoint (.pptx) files, PDF files exported from slide software, Word (.docx) documents, Markdown or plain text, and short typed topics. The outputs are an editable PowerPoint file using native shapes, a self-contained web deck that runs in any modern browser, a study pack (flashcards in CSV and Anki formats, a quiz bank, a cheat sheet and narration notes) and a view-only share link. The system is a decision-support tool for teachers: it does not replace their judgement, every slide it produces can be edited, and every automatic decision is shown with its reason. Handwritten notes, scanned textbooks and languages other than English are outside the present scope.

## Organisation of the Report

Chapter 2 reviews research on automatic slide generation, faithfulness of AI-generated text, slide design and learning, and the commercial tools available today, and identifies the gap Learnova addresses. Chapter 3 analyses the requirements and the feasibility of the system. Chapter 4 describes the architecture and the design of each subsystem. Chapter 5 presents the methods and algorithms we developed, including the Pedagogical Slide Fitness metric and the CLASS segmentation algorithm. Chapter 6 describes the implementation, and Chapter 7 reports the evaluation on gold sets and real decks. Chapter 8 discusses how Learnova differs from existing approaches, and Chapter 9 concludes the report with limitations and future work.


# Literature Survey

## Automatic Generation of Slides from Documents

Research on generating presentations automatically has mostly treated the task as summarisation of a scientific paper. **PPSGen** (Hu and Wan, IEEE Transactions on Knowledge and Data Engineering, 2015) learned a regression model that scores how important each sentence of a paper is and then used integer linear programming to select sentences and arrange them into slides. The approach produced reasonable slide text for papers, but it is extractive summarisation: content judged less important is left out, and it produces no visuals beyond the bullet text.

**DOC2PPT** (Fu, Wang, McDuff and Song, AAAI, 2022) introduced a hierarchical neural model that summarises each section of a scientific document, selects figures from the paper and predicts a slide layout. It was trained on thousands of paper–slide pairs. DOC2PPT showed that figures and layout can be handled jointly with text, but it requires large training data, its abstractive summaries can change or omit facts, and its input must be a scientific paper rather than an existing deck.

**D2S** (Sun, Hou, Wang, Zhang and Wang, NAACL, 2021) took a different view: given slide titles, it treated each title as a query, retrieved relevant passages from the paper and summarised them into the slide body. This made the generated slides more focused, but D2S works only with text, produces no figures, quizzes or interaction, and again assumes a paper as input.

Across these systems, the input is a long document and the output is a shorter one. None of them starts from an existing deck, and all of them trade completeness for brevity.

## Faithfulness of AI-Generated Text

Work on abstractive summarisation has shown that neural models frequently produce content that is not supported by their input. **Maynez, Narayan, Bohnet and McDonald** (ACL, 2020) annotated summaries produced by several models and found a large share of them contained hallucinated content, both contradicting the source and adding unsupported information. **Ji and colleagues** (ACM Computing Surveys, 2023) surveyed hallucination across natural language generation tasks and concluded that it remains an open problem for large language models. **Kasneci and colleagues** (Learning and Individual Differences, 2023) discussed the opportunities and risks of large language models in education and stressed that unchecked errors are especially harmful for learners, who are not in a position to detect them. These findings motivate a central design choice of Learnova: the teacher's text is kept verbatim, and any text written by a model is accepted only after it has been checked against the slide.

## Slide Design and Learning

**Cognitive load theory** (Sweller, Cognitive Science, 1988) distinguishes intrinsic load, which comes from the material itself, from extraneous load, which comes from the way the material is presented. **Cowan** (Behavioral and Brain Sciences, 2001) argued that working memory holds about four chunks at a time. Slides that present many new elements at once, or force the learner to split attention between separate sources, waste this limited capacity. **Mayer's** principles of multimedia learning (Cambridge University Press, 2009) translate these findings into design rules: coherence (remove material that does not serve the goal), signalling (make the structure explicit), spatial contiguity (place pictures next to the words that describe them) and segmenting (present material in learner-paced parts).

The **assertion–evidence** approach (Alley, Schreiber, Ramsdell and Muffo, Technical Communication, 2006; Garner and Alley, International Journal of Engineering Education, 2013) replaces topic titles and bullet lists with a full-sentence headline that states the slide's main point, supported by visual evidence. Controlled studies found better comprehension and retention with this design. **Tufte** (The Cognitive Style of PowerPoint, 2003) argued that bullet outlines fragment reasoning and hide the relationships between ideas.

## Worked Examples and Interactive Visualisation

**Sweller and Cooper** (Cognition and Instruction, 1985) showed that students learning algebra benefited more from studying worked examples than from solving the same problems unaided. **Atkinson, Derry, Renkl and Wortham** (Review of Educational Research, 2000) and **Renkl** (Cognitive Science, 2014) refined this into principles: each step should be visible on its own and the reason for the step should be stated. In computing education, the meta-study of **Hundhausen, Douglas and Stasko** (Journal of Visual Languages and Computing, 2002) found that algorithm visualisations help learning when students actively engage with them — changing inputs, predicting results — rather than passively watching. The **PhET** simulations (Wieman, Adams and Perkins, Science, 2008) and the **ICAP** framework (Chi and Wylie, Educational Psychologist, 2014) support the same conclusion: interactive engagement produces better learning than passive viewing.

## Automatic Visual Design and Layout

**Mackinlay's APT** (ACM Transactions on Graphics, 1986) chose graphical encodings automatically from the characteristics of data, using explicit expressiveness and effectiveness rules. **Draco** (Moritz and colleagues, IEEE Transactions on Visualization and Computer Graphics, 2019) encoded visualisation design knowledge as constraints that can be inspected and extended. These works inspired the decision engine of Learnova, which applies explicit, inspectable rules to sentences rather than to data tables. For text layout, **Knuth and Plass** (Software: Practice and Experience, 1981) formulated paragraph line breaking as an optimisation over break points solved by dynamic programming; our CLASS algorithm uses the same structure to break a long slide into several slides.

## Commercial Presentation Tools

**Gamma**, **Microsoft Copilot in PowerPoint**, **Gemini in Google Slides** and **Canva Magic Design** generate a deck by asking a language model for an outline and then filling a template. In our trials with lecture material, all of them produced visually attractive slides from a prompt. When given an existing deck, however, they rewrote and condensed the content, lost figures and equations that existed only as pictures, added no quizzes, solved examples or laboratories, required a subscription for full use and did not work offline.

## Comparison and Research Gap

Table: Comparison of existing systems with Learnova.

| System | Input is an existing deck | Keeps source content | Explains choices | Illustrations | Interaction | Works offline |
|---|---|---|---|---|---|---|
| PPSGen (2015) | No | No (summarises) | No | No | No | Yes |
| DOC2PPT (2022) | No | No (abstractive) | No | Paper figures | No | Yes |
| D2S (2021) | No | No | No | No | No | Yes |
| Gamma / Copilot / Gemini / Canva | Partly | No | No | Stock / generic | No | No |
| **Learnova** | **Yes** | **Yes (verified)** | **Yes** | **Every slide** | **Quizzes, solvers, labs** | **Yes** |

The survey reveals a clear gap. Research systems summarise papers rather than improving lecture decks and trade faithfulness for brevity. Commercial tools produce attractive new decks but cannot be checked against the source, ignore picture-only content and provide no interaction. Research on learning tells us what a good slide looks like and why interaction matters, but no tool applies this knowledge automatically to the decks teachers already use. Learnova is designed to fill exactly this gap.


# Requirements Analysis and Feasibility

## Stakeholders

The primary users of Learnova are **faculty members**, who upload their existing decks and present or share the redesigned versions, and **students**, who use the web deck, quizzes, explainers and laboratories to study. Secondary stakeholders are the **department**, which benefits from consistent and accessible course material, and **administrators** of the deployment, who manage accounts and API keys.

## Functional Requirements

Table: Functional requirements.

| ID | Requirement |
|---|---|
| FR1 | The user shall sign in with a mobile number and a one-time password. |
| FR2 | The user shall upload a PPTX, PDF, DOCX, Markdown or text file, or type a topic. |
| FR3 | The system shall convert the input into structured slides with titles, bullet levels, tables and figures. |
| FR4 | The system shall show live progress of each processing stage and allow a running job to be cancelled. |
| FR5 | The system shall choose a visual form for every slide and show the reason for the choice. |
| FR6 | The system shall attach an illustration to every topic slide and publish it as a linked HTML page. |
| FR7 | The system shall add checkpoint quizzes, a glossary, key takeaways and an agenda. |
| FR8 | The system shall produce step-by-step explanations for problems it can solve exactly. |
| FR9 | The system shall attach interactive laboratories to suitable topics. |
| FR10 | The user shall download an editable PPTX file, a web deck and a study pack. |
| FR11 | The user shall create and revoke view-only share links. |
| FR12 | The user shall edit slides, save versions and refresh an older deck with the current builders. |
| FR13 | The user shall ask questions about a deck to a tutor that answers only from the deck. |
| FR14 | The user shall add, replace or remove AI provider keys in Settings. |

## Non-Functional Requirements

Table: Non-functional requirements.

| Category | Requirement |
|---|---|
| Fidelity | At least 98% of the numeric and named facts of the source shall appear in the output. |
| Layout | No text shall overflow its box and no word shall be broken across lines. |
| Performance | A 36-page deck shall be processed in under 15 seconds without API keys on a laptop. |
| Availability | The system shall complete every deck even when every AI provider fails. |
| Security | Codes shall be stored hashed; requests shall be rate-limited; generated code and SVG shall be sanitised. |
| Usability | The interface shall work on desktops and phones and be installable as an app. |
| Maintainability | Every module shall be covered by automated tests that run without API keys. |

## Hardware and Software Requirements

For development and for running the system for one department, a laptop with a 64-bit processor, 8 GB of memory and 5 GB of free disk space is sufficient. The software stack consists of Python 3.12 with FastAPI, python-pptx, PyMuPDF, python-docx and SymPy; Node.js with React, Vite and Tailwind CSS for the front end; LibreOffice in headless mode for converting PowerPoint files; and the Tesseract OCR engine. Optional API keys for Google Gemini, Groq or NVIDIA enable the AI features. Users need only a modern web browser.

## Feasibility Study

**Technical feasibility.** Every component of the system relies on mature open-source libraries, and the complete pipeline runs on an ordinary laptop. The prototype is working end to end, with 755 automated tests.

**Economic feasibility.** Learnova can run entirely offline at no cost. The free tier of Gemini, used through a pool of five keys, is sufficient for AI titles, explanations and diagrams. A department server would cost less per year than a single paid licence of a commercial AI presentation tool.

**Operational feasibility.** Teachers keep full control: every slide stays editable and every automatic decision is explained. Students need nothing more than a browser, and the web deck also works on phones.

**Schedule feasibility.** The project was completed in four phases between September 2025 and October 2026: research and design, a first prototype, the Learnova V2 platform, and real-deck support with AI features and research publications.

