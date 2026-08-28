import AppLayout from "@/components/app/AppLayout";
import { Card, CardContent } from "@/components/ui/card";

const SECTIONS = [
  {
    h: "How Learnova decides what to do with your content",
    body: [
      "Every slide is analysed for structure, not keywords. A passage with three or more ordered steps becomes a flowchart; two named things compared across the same aspects become a comparison; several percentages that sum to 100 become a pie; one headline figure becomes a metric callout.",
      "If nothing structural fits, the text is kept — tightened if it is a wordy paragraph, left verbatim if the exact wording matters (definitions, theorems, quotations, code, formulae).",
      "With no LLM key configured, an extractive summariser scores and compresses sentences. Add a Groq or NVIDIA key for full rewriting and quiz generation.",
    ],
  },
  {
    h: "Supported inputs",
    body: [
      "Upload — a .pptx or .pdf. Text, headings and lists are extracted into one markdown representation; embedded images are carried through and each is judged (kept, redrawn, enhanced or dropped).",
      "Typed — paste a syllabus, lecture notes, a chapter summary or a process document straight into the Create screen. Use ## for slide/section headings and -, * or 1. for list items so the structure detector has something to work with.",
      "Scanned PDFs — pages with no text layer are OCR'd when a GEMINI_API_KEY is present; otherwise those pages are skipped with a warning.",
      "Practical limits — very long documents are chunked; the pipeline reasons chunk by chunk, so a 60-page PDF produces a proportionally longer deck rather than failing.",
    ],
  },
  {
    h: "The pipeline, stage by stage",
    body: [
      "1. Ingest → markdown IR. 2. Structure & layout classification — each block is tagged with the visual family that fits its shape. 3. Visual planning — the family is turned into concrete data (nodes, series, rows) deterministically. 4. Text policy — keep verbatim / tighten / summarise. 5. Progressive-reveal timing — build steps and per-step seconds. 6. Quiz insertion — checkpoint questions every N slides. 7. Scoring — PSF per slide, with repagination if a slide is overloaded. 8. Export — animated PPTX and Reveal.js web deck from the one slide model.",
      "You see the editable structure after stage 2. What you change there is what the later stages build.",
    ],
  },
  {
    h: "Visual families",
    body: [
      "40 families cover ordered processes (flowchart, timeline, pipeline), comparison (two-column, table, Venn), quantity (bar, pie, metric callout, progress), hierarchy (pyramid, tree, org chart, mind map), and formal content (proof steps, equations, labelled diagrams, circuits).",
      "Each family has several variants and parametric axes (density, orientation, emphasis), which is where the 1000+ addressable-visual figure comes from. The family is chosen by matching your content's shape; you never pick a chart type.",
      "Set LEARNOVA_MASTER_PROMPT=1 to enable the full 40-family reasoning prompt instead of the compact classifier.",
    ],
  },
  {
    h: "Progressive reveal",
    body: [
      "Slides build one idea per click in the web deck and the PowerPoint export. In the normal editor and preview every point is visible; the builds only play in the presenter / slideshow view.",
      "The presenter console (Present button) shows the current slide, the next slide, speaker notes, a timer, and a step counter. Open the audience view on a second screen — it stays in sync over a BroadcastChannel, including blackout.",
    ],
  },
  {
    h: "Pedagogical Slide Fitness (PSF)",
    body: [
      "The engagement score is a metric grounded in Cognitive Load Theory and Mayer's multimedia principles: information efficiency, cognitive load, and multimedia coherence, combined multiplicatively so a slide that fails one dimension cannot be rescued by the other two.",
      "The same model that scores a slide also decides how to paginate it — the CLASS segmentation step searches pagination boundaries for the one that minimises total cognitive-load 'badness' across the whole deck. Enable it with LEARNOVA_USE_CLASS=1.",
      "A deck-level score in the 80s is typical for well-structured source material; a low score usually points at slides that are still text-heavy or at figures with poor relevance.",
    ],
  },
  {
    h: "Exports",
    body: [
      "PowerPoint (.pptx) — built with python-pptx. Set LEARNOVA_PPTX_ANIM=1 for entrance animations that mirror the web deck's build steps.",
      "Web deck (.html) — a single standalone Reveal.js file with the presenter view, checkpoint quizzes and images inlined. It opens straight in a browser with no server.",
      "Both are regenerated from the same slide model, so editing and re-exporting keeps them consistent.",
    ],
  },
  {
    h: "Keyboard shortcuts",
    body: [
      "Presenter view — → / Space / PageDown: next (advances a build, then the slide) · ← / PageUp: previous · Home / End: first / last · F: fullscreen · B or . : blackout · P: pause the timer · R: reset the timer.",
      "Diagram editor — scroll: zoom at cursor · drag: pan · toolbar: fit, reset, download SVG/PNG, fullscreen · the Mermaid source is editable inline.",
      "Sidebar — Cmd/Ctrl + B: collapse.",
    ],
  },
  {
    h: "API keys & flags",
    body: [
      "Put keys in the project-root .env: GROQ_API_KEY (free tier, gsk_…) or NVIDIA_API_KEY (nvapi-…) for rewriting + quizzes; GEMINI_API_KEY for OCR of scanned PDFs. Clerk keys live in frontend/.env.local (written by `clerk env pull`).",
      "Model overrides: GROQ_MODEL (default openai/gpt-oss-20b), NVIDIA_MODEL (default nvidia/nemotron-3.5-lightning-30b-a3b). NVIDIA_THINKING=1 re-enables chain-of-thought for NVIDIA reasoning models.",
      "Feature flags: LEARNOVA_MASTER_PROMPT=1, LEARNOVA_USE_CLASS=1, LEARNOVA_PPTX_ANIM=1. The Settings screen shows which providers and flags are live.",
    ],
  },
  {
    h: "Troubleshooting",
    body: [
      "Deck reads as a summary, not a lecture — the source probably had no headings or lists. Add ## and bullets and regenerate.",
      "Quizzes are empty — no LLM key is configured, or the provider returned nothing. Check Settings; the extractive path does not generate quizzes.",
      "A saved deck opens but the slide area is blank — older decks were built before a Reveal fix; regenerate from Create to get a fresh export.",
      "Generation is slow — NVIDIA NIM models answer in 15–90 s per call. Groq is the faster default; NVIDIA is used as failover and for quality-sensitive stages.",
    ],
  },
  {
    h: "Privacy & data",
    body: [
      "Decks are stored per user under .data/users/<id>/ on the server running the app — markdown, the PPTX, the HTML deck, and a slides JSON payload.",
      "LLM requests go only to the provider whose key you set (Groq, NVIDIA, Gemini). Nothing is sent anywhere else, and no telemetry leaves the machine.",
    ],
  },
];

export default function Docs() {
  return (
    <AppLayout title="Docs">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Documentation</h2>
          <p className="text-sm text-muted-foreground">
            How the engine works and how to get more out of it.
          </p>
        </div>

        <Card className="lv-card">
          <CardContent className="p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              On this page
            </p>
            <ul className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
              {SECTIONS.map((s) => (
                <li key={s.h}>
                  <a
                    href={`#${slug(s.h)}`}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {s.h}
                  </a>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {SECTIONS.map((s) => (
          <Card key={s.h} id={slug(s.h)} className="lv-card scroll-mt-20">
            <CardContent className="flex flex-col gap-2 p-5">
              <h3 className="font-medium">{s.h}</h3>
              {s.body.map((p, i) => (
                <p key={i} className="text-sm leading-relaxed text-muted-foreground">
                  {p}
                </p>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </AppLayout>
  );
}

function slug(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
