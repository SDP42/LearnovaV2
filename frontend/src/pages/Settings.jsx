import { useEffect, useState } from "react";
import { Check, KeyRound, Keyboard, Server, SlidersHorizontal, UserRound, X } from "lucide-react";
import ProviderKeys from "@/components/app/ProviderKeys";
import { toast } from "sonner";
import * as api from "@/api";
import { UserProfile } from "@/auth";
import AppLayout from "@/components/app/AppLayout";
import { PageHeader } from "@/components/app/Page";
import { Stagger, StaggerItem } from "@/components/app/motion";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { readPref, writePref } from "@/lib/storage";
import { cn } from "@/lib/utils";

const DENSITY_KEY = "learnova-default-density";
const QUIZ_KEY = "learnova-default-quizfreq";

function StatusRow({ label, on, hint }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3 text-sm">
      <div className="min-w-0">
        <p className="font-semibold text-[#402B25]">{label}</p>
        {hint ? <p className="truncate text-xs text-[#715A4E]">{hint}</p> : null}
      </div>
      <span
        className={cn(
          "inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold",
          on ? "bg-[#E6F2E8] text-[#2F5D37]" : "bg-[#F3E6DA] text-[#715A4E]"
        )}
      >
        {on ? <Check className="size-3" strokeWidth={3} /> : <X className="size-3" />}
        {on ? "Configured" : "Not set"}
      </span>
    </div>
  );
}

function Section({ icon: Icon, title, children, className }) {
  return (
    <section className={cn("lv-surface lv-r-hero p-5 sm:p-6", className)}>
      <div className="mb-4 flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-xl bg-[#FCE5D6] text-[#8F3A18]">
          <Icon className="size-[18px]" />
        </span>
        <h2 className="t-h2">{title}</h2>
      </div>
      {children}
    </section>
  );
}

const SHORTCUTS = [
  ["Presenter", [["→ / Space", "Next build / slide"], ["←", "Previous"], ["F", "Fullscreen"], ["B or .", "Blackout"], ["T", "Open the tutor"], ["P / R", "Pause / reset timer"]]],
  ["Editor", [["↑ ↓ ← →", "Move between slides"], ["T", "Open the tutor"], ["?", "Shortcut cheat sheet"]]],
  ["Anywhere", [["⌘/Ctrl K", "Search decks and actions"], ["N", "New deck"], ["?", "Shortcut cheat sheet"]]],
];

export default function Settings() {
  const [cfg, setCfg] = useState(null);
  const [density, setDensity] = useState(() => readPref(DENSITY_KEY, "medium") || "medium");
  const [quizFreq, setQuizFreq] = useState(() => readPref(QUIZ_KEY, "4") || "4");

  useEffect(() => {
    api.getConfig().then(setCfg).catch(() => setCfg({ providers: {}, flags: {} }));
  }, []);

  return (
    <AppLayout title="Settings">
      <div className="mx-auto max-w-3xl">
        <PageHeader title="Settings" subtitle="Generation defaults, account and integration status." className="mb-6" />

        <Stagger stagger={0.06} className="flex flex-col gap-5">
          <StaggerItem>
            <Section icon={SlidersHorizontal} title="Generation defaults">
              <div className="flex flex-wrap items-end gap-6">
                <div className="flex flex-col gap-1.5">
                  <Label>Text density</Label>
                  <Select
                    value={density}
                    onValueChange={(v) => {
                      setDensity(v);
                      writePref(DENSITY_KEY, v);
                      toast.success(`Default density set to ${v}`);
                    }}
                  >
                    <SelectTrigger className="w-44">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["low", "medium", "teaching", "heavy"].map((d) => (
                        <SelectItem key={d} value={d}>
                          {d[0].toUpperCase() + d.slice(1)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Quiz every</Label>
                  <Select
                    value={quizFreq}
                    onValueChange={(v) => {
                      setQuizFreq(v);
                      writePref(QUIZ_KEY, v);
                      toast.success(`A quiz question every ${v} slides`);
                    }}
                  >
                    <SelectTrigger className="w-28">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["2", "3", "4", "5", "6"].map((n) => (
                        <SelectItem key={n} value={n}>
                          {n} slides
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <p className="mt-3 text-xs text-[#715A4E]">Saved in this browser and used whenever you generate a new deck.</p>
            </Section>
          </StaggerItem>

          <StaggerItem>
            <Section icon={KeyRound} title="AI keys">
              <ProviderKeys />
            </Section>
          </StaggerItem>

          <StaggerItem>
            <Section icon={Server} title="Integrations">
              <div className="divide-y divide-[#E8D8C9]">
                {!cfg ? (
                  <div className="space-y-3 py-1">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="lv-skel h-10" />
                    ))}
                  </div>
                ) : (
                  <>
                    <StatusRow label="Groq" on={cfg.providers?.groq} hint="Rewriting, layout, quizzes" />
                    <StatusRow label="NVIDIA NIM" on={cfg.providers?.nvidia} hint="Fallback rewriting + quizzes" />
                    <StatusRow label="Gemini Vision" on={cfg.providers?.gemini} hint="OCR for scanned PDFs" />
                    <StatusRow label="Master prompt" on={cfg.flags?.master_prompt} hint="LEARNOVA_MASTER_PROMPT=1" />
                    <StatusRow label="CLASS pagination" on={cfg.flags?.class_segmentation} hint="LEARNOVA_USE_CLASS=1" />
                    <StatusRow label="PPTX animations" on={cfg.flags?.pptx_animation} hint="LEARNOVA_PPTX_ANIM=1" />
                  </>
                )}
              </div>
              {cfg && !cfg.llm_available ? (
                <p className="mt-3 rounded-xl bg-[#FFF3D6] px-3 py-2.5 text-xs leading-5 text-[#6B4A00]">
                  No LLM provider — running on the extractive summariser. Add <code className="rounded bg-white/70 px-1">GROQ_API_KEY</code> to{" "}
                  <code className="rounded bg-white/70 px-1">.env</code> for full rewriting and quizzes.
                </p>
              ) : null}
            </Section>
          </StaggerItem>

          <StaggerItem>
            <Section icon={Keyboard} title="Keyboard shortcuts">
              <div className="grid gap-5 text-sm sm:grid-cols-3">
                {SHORTCUTS.map(([group, rows]) => (
                  <div key={group}>
                    <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.12em] text-[#715A4E]">{group}</p>
                    <dl className="flex flex-col gap-2">
                      {rows.map(([k, v]) => (
                        <div key={k + v} className="flex items-center justify-between gap-2">
                          <dt className="text-[#4F3A31]">{v}</dt>
                          <dd>
                            <kbd className="lv-kbd">{k}</kbd>
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ))}
              </div>
            </Section>
          </StaggerItem>

          <StaggerItem>
            <Section icon={Server} title="Data & storage">
              <div className="flex flex-col gap-2 text-sm leading-6 text-[#4F3A31]">
                <p>
                  Each deck is stored on the server running Learnova under{" "}
                  <code className="rounded bg-[#F3E6DA] px-1">.data/users/&lt;your-id&gt;/</code> — the markdown source, the PowerPoint, the web
                  deck, and a slides JSON payload. Deleting a deck removes that folder.
                </p>
                <p>
                  LLM requests go only to the provider whose key is configured above. Generation defaults on this page are stored in your
                  browser, not on the server.
                </p>
              </div>
            </Section>
          </StaggerItem>

          <StaggerItem>
            <Section icon={UserRound} title="Account">
              {typeof UserProfile === "function" ? (
                <UserProfile />
              ) : (
                <p className="text-sm text-muted-foreground">Sign in to manage your account.</p>
              )}
            </Section>
          </StaggerItem>

          <StaggerItem>
            <p className="px-1 text-center text-xs text-[#715A4E]">
              Learnova — an AI presentation engine ·{" "}
              <a href="/app/docs" className="font-semibold text-[#8F3A18] underline">Documentation</a> ·{" "}
              <a href="/privacy" className="font-semibold text-[#8F3A18] underline">Privacy</a> ·{" "}
              <a href="/terms" className="font-semibold text-[#8F3A18] underline">Terms</a>
            </p>
          </StaggerItem>
        </Stagger>
      </div>
    </AppLayout>
  );
}
