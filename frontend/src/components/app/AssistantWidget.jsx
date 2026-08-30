import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, MicOff, Send, Sparkles, X, Loader2 } from "lucide-react";
import * as api from "@/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useVoice } from "@/lib/useVoice";

const SESSION_ID =
  (typeof crypto !== "undefined" && crypto.randomUUID && crypto.randomUUID()) ||
  `web-${Date.now()}`;

const GREETING = {
  role: "assistant",
  text: "Ask me to open a deck, move between slides, explain a concept, search your presentations, or run a quiz.",
};

/**
 * The Learnova assistant (chat + voice). Sends every utterance to
 * POST /api/assistant/query and executes the typed response:
 *   OPEN_PRESENTATION / SHOW_WEB_DECK -> route to the deck
 *   NAVIGATE                          -> route with ?slide=N
 *   ASK_CLARIFICATION                 -> render option chips
 *   SHOW_SEARCH_RESULTS               -> render deck cards
 *   others                            -> show + speak the message
 */
export default function AssistantWidget() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState([GREETING]);
  const scrollRef = useRef(null);

  const push = useCallback((t) => setTurns((cur) => [...cur, t]), []);

  const runAction = useCallback(
    (resp) => {
      const t = resp.type;
      if ((t === "OPEN_PRESENTATION" || t === "SHOW_WEB_DECK") && resp.deck_id) {
        const present = resp.payload?.present ? "?present" : "";
        navigate(`/app/preview/${resp.deck_id}${present}`);
      } else if (t === "NAVIGATE" && resp.deck_id) {
        const q = resp.slide_number ? `?slide=${resp.slide_number}` : "";
        navigate(`/app/preview/${resp.deck_id}${q}`);
        window.dispatchEvent(
          new CustomEvent("learnova:navigate-slide", { detail: resp.slide_number })
        );
      } else if (t === "CREATE_PRESENTATION") {
        navigate("/app/create", { state: { topic: resp.payload?.topic } });
      } else if (t === "SHOW_GALLERY_RESULTS") {
        const ready = (resp.results || []).find((r) => r.has_deck);
        if (ready) navigate(`/app/gallery?topic=${encodeURIComponent(ready.slug)}`);
      } else if (t === "SHOW_SEARCH_RESULTS" || t === "SHOW_WEB_DECK") {
        /* results are rendered inline */
      }
    },
    [navigate]
  );

  const send = useCallback(
    async (text) => {
      const q = (text ?? input).trim();
      if (!q || busy) return;
      setInput("");
      push({ role: "user", text: q });
      setBusy(true);
      try {
        const { response } = await api.assistantQuery(q, SESSION_ID);
        push({ role: "assistant", text: response.message, response });
        runAction(response);
        return response;
      } catch (e) {
        push({ role: "assistant", text: `Sorry — ${e.message}`, error: true });
      } finally {
        setBusy(false);
      }
      return null;
    },
    [input, busy, push, runAction]
  );

  const voice = useVoice({
    onResult: async (text) => {
      const resp = await send(text);
      if (resp && (resp.speech || resp.message)) voice.speak(resp.speech || resp.message);
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, open]);

  const lastResults = useMemo(() => {
    for (let i = turns.length - 1; i >= 0; i -= 1) {
      const r = turns[i].response;
      if (r?.type === "SHOW_SEARCH_RESULTS") return { kind: "deck", rows: r.results || [] };
      if (r?.type === "SHOW_GALLERY_RESULTS") return { kind: "gallery", rows: r.results || [] };
      if (r?.type === "ASK_CLARIFICATION") return null;
    }
    return null;
  }, [turns]);

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Open Learnova assistant"
          className="fixed bottom-5 right-5 z-40 flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition hover:scale-105"
        >
          <Sparkles className="size-5" />
        </button>
      )}

      {open && (
        <div className="fixed bottom-5 right-5 z-40 flex h-[520px] w-[360px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border bg-background shadow-2xl">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <Sparkles className="size-4 text-primary" />
            <span className="text-sm font-medium">Learnova assistant</span>
            {voice.speaking && (
              <button
                onClick={voice.stopSpeaking}
                className="ml-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-muted"
              >
                stop
              </button>
            )}
            <button
              onClick={() => setOpen(false)}
              className="ml-auto rounded p-1 hover:bg-muted"
              aria-label="Close"
            >
              <X className="size-4" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
            {turns.map((t, i) => (
              <div key={i} className={cn("flex", t.role === "user" && "justify-end")}>
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-3 py-2 text-sm",
                    t.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : t.error
                        ? "bg-destructive/10 text-destructive"
                        : "bg-muted"
                  )}
                >
                  {t.text}
                  {t.response?.type === "ASK_CLARIFICATION" && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(t.response.options || []).map((o) => (
                        <button
                          key={o.pres_id}
                          onClick={() => send(o.pres_id)}
                          className="rounded-full border bg-background px-2.5 py-1 text-xs hover:border-primary/50"
                        >
                          {o.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {lastResults?.rows?.length ? (
              <div className="space-y-1.5">
                {lastResults.rows.slice(0, 6).map((d) =>
                  lastResults.kind === "gallery" ? (
                    <button
                      key={d.slug}
                      onClick={() => navigate(`/app/gallery?topic=${encodeURIComponent(d.slug)}`)}
                      className="flex w-full items-center gap-2 rounded-lg border p-2 text-left text-xs hover:border-primary/40 hover:bg-primary/5"
                    >
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 text-[10px] font-medium",
                          d.has_deck ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                        )}
                      >
                        {d.has_deck ? "Ready" : "Generate"}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-medium">{d.title}</span>
                      <span className="text-muted-foreground">
                        {d.has_deck ? `${d.slide_count} sl` : d.subject}
                      </span>
                    </button>
                  ) : (
                    <button
                      key={d.pres_id}
                      onClick={() => navigate(`/app/preview/${d.deck_id}`)}
                      className="flex w-full items-center gap-2 rounded-lg border p-2 text-left text-xs hover:border-primary/40 hover:bg-primary/5"
                    >
                      <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary">
                        #{d.display_number}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-medium">{d.title}</span>
                      <span className="text-muted-foreground">{d.slide_count} sl</span>
                    </button>
                  )
                )}
              </div>
            ) : null}

            {busy && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="size-3 animate-spin" /> thinking…
              </div>
            )}
            {voice.partial && (
              <div className="text-right text-xs italic text-muted-foreground">
                {voice.partial}…
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="flex items-center gap-1.5 border-t p-2"
          >
            {voice.supported && (
              <Button
                type="button"
                size="icon"
                variant={voice.listening ? "default" : "ghost"}
                onClick={voice.listening ? voice.stopListening : voice.listen}
                aria-label={voice.listening ? "Stop listening" : "Speak"}
              >
                {voice.listening ? <MicOff className="size-4" /> : <Mic className="size-4" />}
              </Button>
            )}
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Learnova…"
              className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary/50"
            />
            <Button type="submit" size="icon" disabled={busy || !input.trim()}>
              <Send className="size-4" />
            </Button>
          </form>
        </div>
      )}
    </>
  );
}
