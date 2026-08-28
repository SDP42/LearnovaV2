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
    h: "Progressive reveal",
    body: [
      "Slides build one idea per click in the web deck and the PowerPoint export. In the normal editor and preview every point is visible; the builds only play in the presenter / slideshow view.",
      "The presenter console (Present button) shows the current slide, the next slide, speaker notes, a timer, and a step counter. Open the audience view on a second screen — it stays in sync.",
    ],
  },
  {
    h: "Pedagogical Slide Fitness (PSF)",
    body: [
      "The engagement score is a metric grounded in Cognitive Load Theory and Mayer's multimedia principles: information efficiency, cognitive load, and multimedia coherence, combined multiplicatively. The same model that scores a slide also decides how to paginate it.",
    ],
  },
  {
    h: "Keyboard shortcuts",
    body: [
      "Presenter view — → / Space: next (advances a build, then the slide) · ← : previous · F: fullscreen the current slide.",
      "Diagram editor — scroll: zoom · drag: pan · toolbar: fit, reset, download SVG/PNG, fullscreen.",
      "Sidebar — Cmd/Ctrl + B: collapse.",
    ],
  },
  {
    h: "API keys",
    body: [
      "Put keys in the project-root .env: GROQ_API_KEY (free tier, gsk_…) or NVIDIA_API_KEY for rewriting + quizzes; GEMINI_API_KEY for OCR of scanned PDFs. Clerk keys live in frontend/.env.local (written by `clerk env pull`).",
      "Optional flags: LEARNOVA_MASTER_PROMPT=1 (full 40-family visual reasoning), LEARNOVA_USE_CLASS=1 (cognitive-load-optimal pagination), LEARNOVA_PPTX_ANIM=1 (PowerPoint entrance animations).",
    ],
  },
];

export default function Docs() {
  return (
    <AppLayout title="Docs">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Documentation</h2>
          <p className="text-sm text-muted-foreground">How the engine works and how to get more out of it.</p>
        </div>
        {SECTIONS.map((s) => (
          <Card key={s.h} className="lv-card">
            <CardContent className="flex flex-col gap-2 p-5">
              <h3 className="font-medium">{s.h}</h3>
              {s.body.map((p, i) => (
                <p key={i} className="text-sm leading-relaxed text-muted-foreground">{p}</p>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </AppLayout>
  );
}
