import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Mic, MicOff, Send, Sparkles, Volume2, VolumeX, X } from "lucide-react";
import * as api from "@/api";
import { isTypingTarget } from "@/components/app/ShortcutsOverlay";

const SUGGESTIONS = ["Summarise this deck", "Quiz me", "Explain slide 2", "What are the key terms?"];

/** Speech synthesis tuned by the persona's voice hints (rate, pitch, language). */
function speak(text, voice) {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text.replace(/\[S\d+\]/g, "").replace(/[•*_`#]/g, " "));
    u.rate = voice?.rate ?? 1;
    u.pitch = voice?.pitch ?? 1;
    u.lang = voice?.lang ?? "en-US";
    const match = synth.getVoices().find((v) => v.lang === u.lang) || synth.getVoices().find((v) => v.lang?.startsWith(u.lang.slice(0, 2)));
    if (match) u.voice = match;
    synth.speak(u);
  } catch {
    /* speech unavailable */
  }
}

function Quiz({ quiz, onAnswered }) {
  const [picked, setPicked] = useState(null);
  const done = picked !== null;
  return (
    <div className="mt-2 flex flex-col gap-1.5">
      {quiz.options.map((o, i) => {
        const letter = "ABCD"[i];
        const right = letter === quiz.correct;
        return (
          <button
            key={letter}
            disabled={done}
            onClick={() => { setPicked(letter); onAnswered?.(letter === quiz.correct); }}
            className={[
              "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-[13px] transition",
              !done ? "border-[#E8D8C9] bg-white hover:border-[#F47B45] hover:bg-[#FDEEE3]" : "",
              done && right ? "border-[#6B9B72] bg-[#E6F2E8] text-[#2F5D37]" : "",
              done && !right && picked === letter ? "border-[#C0392B] bg-[#FBE9E7] text-[#8E2A1F]" : "",
              done && !right && picked !== letter ? "border-[#E8D8C9] bg-white opacity-60" : "",
            ].join(" ")}
          >
            <b className="grid size-5 shrink-0 place-items-center rounded-full bg-[#F3E6DA] text-[11px]">{letter}</b>
            <span className="min-w-0 flex-1">{o}</span>
            {done && right ? <Check className="size-4" /> : null}
          </button>
        );
      })}
      {done ? (
        <p className="rounded-lg bg-[#FDEEE3] px-3 py-2 text-[12.5px] text-[#5A453B]">
          {picked === quiz.correct ? "Correct. " : `The answer is ${quiz.correct}. `}
          {quiz.explanation}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Persona-based tutor for one deck: pick a voice, ask anything, hear the answer.
 * Answers come from /api/decks/:id/chat (LLM when a key is configured, the
 * built-in retrieval otherwise) and cite the slides they used.
 */
export default function TutorPanel({ deckId, open, onClose, onJumpToSlide }) {
  const [personas, setPersonas] = useState([]);
  const [persona, setPersona] = useState("teacher");
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [talk, setTalk] = useState(() => {
    try { return localStorage.getItem("learnova-tutor-voice") === "1"; } catch { return false; }
  });
  const [listening, setListening] = useState(false);
  const [score, setScore] = useState({ right: 0, total: 0 });
  const recRef = useRef(null);
  const endRef = useRef(null);
  const current = useMemo(() => personas.find((p) => p.id === persona), [personas, persona]);
  const sttSupported = typeof window !== "undefined" && !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  useEffect(() => {
    api.tutorPersonas().then((r) => { setPersonas(r.personas); setPersona((p) => p || r.default); }).catch(() => {});
  }, []);

  // Greeting changes with the persona; an existing conversation is kept.
  useEffect(() => {
    if (current && msgs.length === 0) setMsgs([{ role: "assistant", content: current.greeting, greeting: true }]);
  }, [current]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);
  useEffect(() => { try { localStorage.setItem("learnova-tutor-voice", talk ? "1" : "0"); } catch { /* ignore */ } if (!talk) window.speechSynthesis?.cancel(); }, [talk]);
  useEffect(() => () => { window.speechSynthesis?.cancel(); recRef.current?.stop?.(); }, []);

  const send = useCallback(async (raw) => {
    const message = (raw ?? text).trim();
    if (!message || busy) return;
    setText("");
    const history = msgs.filter((m) => !m.greeting).map((m) => ({ role: m.role, content: m.content }));
    setMsgs((m) => [...m, { role: "user", content: message }]);
    setBusy(true);
    try {
      const r = await api.tutorChat(deckId, message, persona, history);
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, sources: r.sources || [], quiz: r.quiz, mode: r.mode }]);
      if (talk) speak(r.answer, current?.voice);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", content: `Sorry, I couldn't answer that (${e.message}).`, error: true }]);
    } finally {
      setBusy(false);
    }
  }, [text, busy, msgs, deckId, persona, talk, current]);

  function toggleMic() {
    if (listening) { recRef.current?.stop(); return; }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.lang = current?.voice?.lang || "en-US";
    rec.interimResults = true;
    rec.onresult = (e) => {
      const t = Array.from(e.results).map((r) => r[0].transcript).join("");
      setText(t);
      if (e.results[e.results.length - 1].isFinal) { setListening(false); send(t); }
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.aside
          key="tutor"
          role="dialog"
          aria-label="Deck tutor"
          initial={{ x: 420, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 420, opacity: 0 }}
          transition={{ type: "spring", damping: 28, stiffness: 260 }}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[400px] flex-col border-l border-[#E8D8C9] bg-[#FFFAF5] shadow-[-20px_0_60px_-30px_rgba(64,43,37,.4)]"
        >
          <header className="flex items-start gap-3 border-b border-[#E8D8C9] px-4 py-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#F47B45] text-2xl">{current?.emoji || "🧑‍🏫"}</span>
            <div className="min-w-0 flex-1">
              <p className="font-[Bricolage_Grotesque] text-[17px] font-bold leading-tight text-[#402B25]">{current?.name || "Deck tutor"}</p>
              <p className="truncate text-[12px] text-[#715A4E]">{current?.tagline || "Ask anything about this deck"}</p>
            </div>
            <button onClick={() => setTalk((v) => !v)} aria-pressed={talk} aria-label={talk ? "Mute voice" : "Read answers aloud"} title={talk ? "Voice on" : "Voice off"}
              className={`grid size-8 place-items-center rounded-full border transition ${talk ? "border-[#F47B45] bg-[#FCE5D6] text-[#8F3A18]" : "border-[#E8D8C9] bg-white text-[#715A4E]"}`}>
              {talk ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
            </button>
            <button onClick={onClose} aria-label="Close tutor" className="grid size-8 place-items-center rounded-full border border-[#E8D8C9] bg-white text-[#715A4E] hover:bg-[#F3E6DA]"><X className="size-4" /></button>
          </header>

          <div className="flex gap-1.5 overflow-x-auto border-b border-[#E8D8C9] px-3 py-2 lv-no-scrollbar" role="radiogroup" aria-label="Tutor persona">
            {personas.map((p) => (
              <button key={p.id} role="radio" aria-checked={p.id === persona} onClick={() => { setPersona(p.id); setMsgs([{ role: "assistant", content: p.greeting, greeting: true }]); }}
                className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-semibold transition ${p.id === persona ? "border-[#402B25] bg-[#402B25] text-[#FFFAF5]" : "border-[#E8D8C9] bg-white text-[#402B25] hover:border-[#F47B45]"}`}>
                <span>{p.emoji}</span>{p.name}
              </button>
            ))}
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed ${m.role === "user" ? "rounded-br-md bg-[#402B25] text-[#FFFAF5]" : m.error ? "rounded-bl-md bg-[#FBE9E7] text-[#8E2A1F]" : "rounded-bl-md border border-[#E8D8C9] bg-white text-[#402B25]"}`}>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  {m.quiz ? <Quiz quiz={m.quiz} onAnswered={(ok) => setScore((s) => ({ right: s.right + (ok ? 1 : 0), total: s.total + 1 }))} /> : null}
                  {m.sources?.length ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.sources.map((s) => (
                        <button key={`${s.slide}-${s.title}`} onClick={() => onJumpToSlide?.(s.slide - 1)} title={s.title}
                          className="rounded-full bg-[#F3E6DA] px-2.5 py-0.5 text-[11.5px] font-semibold text-[#8F3A18] transition hover:bg-[#FCE5D6]">
                          Slide {s.slide}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
            {busy ? (
              <div className="flex justify-start"><div className="flex gap-1 rounded-2xl rounded-bl-md border border-[#E8D8C9] bg-white px-4 py-3" aria-label="Thinking">
                {[0, 1, 2].map((d) => <span key={d} className="size-1.5 animate-bounce rounded-full bg-[#F47B45]" style={{ animationDelay: `${d * 120}ms` }} />)}
              </div></div>
            ) : null}
            <div ref={endRef} />
          </div>

          <footer className="border-t border-[#E8D8C9] bg-white px-3 pb-3 pt-2">
            {msgs.length <= 1 ? (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="rounded-full border border-[#E8D8C9] bg-[#FFFAF5] px-3 py-1 text-[12.5px] font-medium text-[#402B25] transition hover:-translate-y-px hover:border-[#F47B45]">{s}</button>
                ))}
              </div>
            ) : null}
            {score.total ? <p className="mb-1.5 text-[12px] font-semibold text-[#715A4E]">Quiz score: {score.right}/{score.total}</p> : null}
            <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex items-center gap-2">
              {sttSupported ? (
                <button type="button" onClick={toggleMic} aria-pressed={listening} aria-label={listening ? "Stop listening" : "Speak your question"}
                  className={`grid size-10 shrink-0 place-items-center rounded-full border transition ${listening ? "animate-pulse border-[#C0392B] bg-[#FBE9E7] text-[#C0392B]" : "border-[#E8D8C9] bg-[#FFFAF5] text-[#402B25] hover:border-[#F47B45]"}`}>
                  {listening ? <MicOff className="size-4" /> : <Mic className="size-4" />}
                </button>
              ) : null}
              <input value={text} onChange={(e) => setText(e.target.value)} placeholder={listening ? "Listening…" : "Ask about this deck…"} aria-label="Message the tutor" maxLength={1200}
                className="h-10 min-w-0 flex-1 rounded-full border border-[#E8D8C9] bg-[#FFFAF5] px-4 text-[14px] text-[#402B25] outline-none placeholder:text-[#765F53] focus:border-[#D95D39] focus:ring-2 focus:ring-[#F47B4533]" />
              <button type="submit" disabled={!text.trim() || busy} aria-label="Send"
                className="grid size-10 shrink-0 place-items-center rounded-full bg-[#F47B45] text-[#2A1A14] transition hover:bg-[#D95D39] hover:text-white disabled:opacity-50"><Send className="size-4" /></button>
            </form>
          </footer>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}

/** Floating launcher; keeps its own open state so a page only needs <TutorLauncher deckId=… />. */
export function TutorLauncher({ deckId, onJumpToSlide, className = "" }) {
  const [open, setOpen] = useState(false);

  // T toggles the tutor from anywhere on the page (not while typing); Esc closes it.
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "Escape") return setOpen(false);
      if ((e.key === "t" || e.key === "T") && !isTypingTarget(e.target)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      {!open ? (
        <button onClick={() => setOpen(true)} aria-label="Ask the tutor (T)" title="Ask the tutor (T)"
          className={`fixed bottom-5 right-5 z-40 flex h-12 items-center gap-2 rounded-full bg-[#402B25] px-5 text-[14px] font-semibold text-[#FFFAF5] shadow-lg transition duration-150 hover:-translate-y-0.5 hover:bg-[#2E1E19] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F47B45] ${className}`}>
          <Sparkles className="size-4 text-[#F47B45]" /> Ask the tutor
          <kbd className="ml-0.5 hidden rounded bg-[#FFFAF5]/15 px-1.5 text-[11px] font-semibold sm:inline">T</kbd>
        </button>
      ) : null}
      <TutorPanel deckId={deckId} open={open} onClose={() => setOpen(false)} onJumpToSlide={onJumpToSlide} />
    </>
  );
}
