import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { FileText, Loader2, Paperclip, Sparkles, UploadCloud, Wand2, X, ArrowUp } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { defaultGenerateOptions } from "@/pages/Generate";

export const TEMPLATE_CHIPS = [
  { id: "lecture", label: "Lecture", text: "A 45-minute lecture introducing the topic to first-year students: why it matters, the core concepts, one worked example and a short recap.\n\nTopic: " },
  { id: "revision", label: "Revision", text: "A revision deck that condenses the chapter into key definitions, formulas, common mistakes and quick self-check questions.\n\nChapter: " },
  { id: "exam", label: "Exam prep", text: "An exam-prep deck: the most testable concepts, typical question patterns, step-by-step solved examples and a last-minute checklist.\n\nSubject: " },
  { id: "pitch", label: "Pitch", text: "A pitch deck: the problem, our solution, how it works, market size, traction, business model and the ask.\n\nProduct: " },
  { id: "lab", label: "Lab report", text: "A lab report presentation: aim, hypothesis, method, apparatus, results with a chart, analysis, sources of error and conclusion.\n\nExperiment: " },
  { id: "story", label: "Story", text: "A story-driven talk that teaches the idea through a narrative: a hook, a character facing the problem, a turning point, and the lesson.\n\nIdea: " },
];

export const SAMPLE_SYLLABUS = `## Photosynthesis Process
Photosynthesis happens in stages. First, chlorophyll absorbs sunlight in the thylakoid membranes. Next, water molecules are split to release oxygen and electrons. Then the energy is stored in ATP and NADPH. Finally, the Calvin cycle uses ATP and carbon dioxide to build glucose.

## History of Computing
In 1936 Alan Turing described the universal machine. In 1945 ENIAC became the first general purpose electronic computer. In 1971 Intel released the first microprocessor. In 1991 the World Wide Web opened to the public. In 2007 the iPhone launched the smartphone era.

## Supervised vs Unsupervised Learning
Supervised learning uses labelled data, while unsupervised learning finds patterns in unlabelled data. Supervised models predict outputs such as prices or classes. Unsupervised models group similar items, for example customers.

## Layers of the Earth
The Earth has four main layers. The crust is the thin outer shell. Beneath it lies the mantle, which is the thickest layer. The outer core is liquid iron and nickel. The inner core is solid and extremely hot.
`;

const AUDIENCES = ["Grade 6", "High school", "University", "Professionals", "Executives"];
const LENGTHS = [
  { v: "6-10", label: "6–10 slides", density: "low" },
  { v: "10-15", label: "10–15 slides", density: "medium" },
  { v: "15-25", label: "15–25 slides", density: "teaching" },
];
const TONES = ["Friendly", "Formal", "Concise", "Storytelling"];
const OK_EXT = /\.(pdf|pptx|docx|md|txt)$/i;

function Opt({ label, value, onChange, items }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        aria-label={label}
        className="h-8 w-auto gap-1.5 rounded-full border-[#DEE7F5] bg-[#F4F9FF] px-3 text-[13px] font-medium text-[#2A3B5F] shadow-none"
      >
        <span className="text-[#8190AD]">{label}:</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {items.map((i) => (
          <SelectItem key={i.v ?? i} value={i.v ?? i}>
            {i.label ?? i}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** Hero composer: describe or drop a source, tune it, Generate. */
export default function Composer({ value, onChange, textareaRef, className }) {
  const navigate = useNavigate();
  const innerRef = useRef(null);
  const ta = textareaRef || innerRef;
  const fileInput = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [audience, setAudience] = useState("University");
  const [length, setLength] = useState("10-15");
  const [tone, setTone] = useState("Friendly");
  const [hints, setHints] = useState([]);
  const [improving, setImproving] = useState(false);
  const [busy, setBusy] = useState(false);
  const depth = useRef(0);

  // auto-grow
  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 76), 280)}px`;
  }, [value, ta]);

  const accept = useCallback((f) => {
    if (!f) return;
    if (!OK_EXT.test(f.name)) {
      toast.error("Use a PDF, PPTX or DOCX file");
      return;
    }
    setFile(f);
    toast.success(`Attached ${f.name}`);
  }, []);

  const onDrop = (e) => {
    e.preventDefault();
    depth.current = 0;
    setDragging(false);
    accept(e.dataTransfer?.files?.[0]);
  };

  async function improve() {
    if (!value.trim()) {
      toast("Type a topic first, then I can sharpen it");
      return;
    }
    setImproving(true);
    setHints([]);
    try {
      const r = await api.assistPrompt(value);
      if (r.llm && r.text) {
        onChange(r.text);
        toast.success("Prompt improved");
      } else {
        setHints(r.hints?.length ? r.hints : ["Add the audience and what they should be able to do afterwards."]);
      }
    } catch (e) {
      toast.error(e.message || "Couldn’t improve the prompt");
    } finally {
      setImproving(false);
    }
  }

  const canGo = !busy && (file || value.trim().length > 0);

  async function generate() {
    if (!canGo) return;
    setBusy(true);
    const len = LENGTHS.find((l) => l.v === length);
    const options = defaultGenerateOptions({
      text_density: len?.density || "medium",
      audience: `${audience}, ${tone.toLowerCase()} tone, ${len?.label || ""}`.trim(),
    });
    try {
      if (file) {
        const job = await api.uploadDocument(file);
        navigate(`/app/generate/${job.id}`, { state: { options, title: file.name } });
      } else {
        const first = value.trim().split("\n")[0].replace(/^#+\s*/, "").slice(0, 60);
        const job = await api.createTypedJob(value, first || "Untitled deck");
        navigate(`/app/generate/${job.id}`, { state: { options, title: first } });
      }
    } catch (e) {
      setBusy(false);
      toast.error(e.message || "Couldn’t start the deck");
    }
  }

  return (
    <div
      className={cn(
        "lv-r-hero relative border bg-white shadow-[0_1px_0_rgb(11_31_68/0.04),0_16px_40px_-18px_rgb(37_99_235/0.28)] transition-shadow focus-within:border-[#9DBBF5] focus-within:shadow-[0_0_0_4px_rgb(37_99_235/0.10),0_16px_40px_-18px_rgb(37_99_235/0.35)]",
        className
      )}
      onDragEnter={(e) => {
        e.preventDefault();
        depth.current++;
        setDragging(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => {
        if (--depth.current <= 0) {
          depth.current = 0;
          setDragging(false);
        }
      }}
      onDrop={onDrop}
    >
      <div className="p-4 sm:p-5">
        <textarea
          ref={ta}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") generate();
          }}
          rows={2}
          placeholder="Describe what you’re teaching, paste a syllabus, or drop a PDF, PPTX or DOCX here…"
          aria-label="What are we teaching?"
          className="lv-bare block w-full resize-none bg-transparent text-[16px] leading-[26px] text-[#0B1F44] outline-none placeholder:text-[#8190AD]"
        />

        <AnimatePresence initial={false}>
          {file ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-2 inline-flex max-w-full items-center gap-2 rounded-lg border bg-[#F4F9FF] py-1.5 pl-2.5 pr-1.5 text-[13px]">
                <FileText className="size-4 shrink-0 text-[#2563EB]" />
                <span className="truncate font-medium">{file.name}</span>
                <span className="text-[#8190AD]">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                <button onClick={() => setFile(null)} aria-label="Remove file" className="grid size-5 place-items-center rounded hover:bg-white">
                  <X className="size-3.5" />
                </button>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {hints.length ? (
            <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="text-[12px] font-medium text-[#8190AD]">Try adding:</span>
              {hints.map((h) => (
                <button
                  key={h}
                  onClick={() => {
                    onChange(`${value.trim()}\n${h}`);
                    setHints((x) => x.filter((y) => y !== h));
                  }}
                  className="rounded-full bg-[#FFF6DB] px-2.5 py-1 text-left text-[12px] font-medium text-[#8A5A00] transition hover:bg-[#FFEDB8]"
                >
                  + {h}
                </button>
              ))}
            </motion.div>
          ) : null}
        </AnimatePresence>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            ref={fileInput}
            type="file"
            hidden
            accept=".pdf,.pptx,.docx,.md,.txt"
            onChange={(e) => {
              accept(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => fileInput.current?.click()}
            aria-label="Attach a file"
            className="grid size-8 place-items-center rounded-full border border-[#DEE7F5] bg-[#F4F9FF] text-[#2A3B5F] transition hover:bg-white"
          >
            <Paperclip className="size-4" />
          </button>
          <Opt label="Audience" value={audience} onChange={setAudience} items={AUDIENCES} />
          <Opt label="Slides" value={length} onChange={setLength} items={LENGTHS} />
          <Opt label="Tone" value={tone} onChange={setTone} items={TONES} />

          <div className="ml-auto flex w-full items-center gap-2 sm:w-auto">
            <button
              onClick={improve}
              disabled={improving}
              className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full border border-[#DEE7F5] bg-white px-3.5 text-[13px] font-semibold text-[#1D4ED8] transition hover:bg-[#EEF4FF] disabled:opacity-60 sm:flex-none"
            >
              {improving ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
              Improve my prompt <span aria-hidden>✨</span>
            </button>
            <button
              onClick={generate}
              disabled={!canGo}
              className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full bg-[#0B1F44] px-5 text-[14px] font-semibold text-white shadow-sm transition hover:bg-[#13306a] active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-[#9AA9C6] sm:flex-none"
            >
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Generate
              <ArrowUp className="size-4 rotate-45" />
            </button>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {dragging ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-10 grid place-items-center rounded-[inherit] border-2 border-dashed border-[#2563EB] bg-[#EEF4FF]/95"
          >
            <div className="flex flex-col items-center gap-2 text-[#1D4ED8]">
              <UploadCloud className="size-9" />
              <p className="font-[Bricolage_Grotesque] text-lg font-bold">Drop to read it</p>
              <p className="text-[12px] text-[#5A6B8C]">PDF, PPTX or DOCX</p>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
