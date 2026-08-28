import { useEffect, useState } from "react";
import { Check, Moon, Sun, X } from "lucide-react";
import * as api from "@/api";
import { UserProfile } from "@/auth";
import AppLayout from "@/components/app/AppLayout";
import { useTheme } from "@/components/theme.jsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const DENSITY_KEY = "learnova-default-density";
const QUIZ_KEY = "learnova-default-quizfreq";

function StatusRow({ label, on, hint }) {
  return (
    <div className="flex items-center justify-between py-2 text-sm">
      <div>
        <p className="font-medium">{label}</p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
          on
            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
            : "bg-muted text-muted-foreground"
        )}
      >
        {on ? <Check className="size-3" /> : <X className="size-3" />}
        {on ? "Configured" : "Not set"}
      </span>
    </div>
  );
}

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const [cfg, setCfg] = useState(null);
  const [density, setDensity] = useState(() => localStorage.getItem(DENSITY_KEY) || "medium");
  const [quizFreq, setQuizFreq] = useState(() => localStorage.getItem(QUIZ_KEY) || "4");

  useEffect(() => {
    api.getConfig().then(setCfg).catch(() => setCfg({ providers: {}, flags: {} }));
  }, []);

  return (
    <AppLayout title="Settings">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Settings</h2>
          <p className="text-sm text-muted-foreground">Appearance, generation defaults, and integration status.</p>
        </div>

        <Card>
          <CardHeader><CardTitle className="text-base">Appearance</CardTitle></CardHeader>
          <CardContent>
            <RadioGroup value={theme} onValueChange={setTheme} className="grid gap-2 sm:grid-cols-2">
              {[
                ["dark", "Dark", Moon],
                ["light", "Light", Sun],
              ].map(([v, label, Icon]) => (
                <label
                  key={v}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm",
                    theme === v ? "border-primary bg-primary/5" : "hover:bg-muted/40"
                  )}
                >
                  <RadioGroupItem value={v} />
                  <Icon className="size-4" /> {label}
                </label>
              ))}
            </RadioGroup>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Generation defaults</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap items-center gap-6">
            <div className="flex flex-col gap-1.5">
              <Label>Text density</Label>
              <Select
                value={density}
                onValueChange={(v) => {
                  setDensity(v);
                  localStorage.setItem(DENSITY_KEY, v);
                }}
              >
                <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["low", "medium", "heavy"].map((d) => (
                    <SelectItem key={d} value={d}>{d[0].toUpperCase() + d.slice(1)}</SelectItem>
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
                  localStorage.setItem(QUIZ_KEY, v);
                }}
              >
                <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["2", "3", "4", "5", "6"].map((n) => <SelectItem key={n} value={n}>{n}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Integrations</CardTitle></CardHeader>
          <CardContent className="divide-y">
            {!cfg ? (
              <Skeleton className="h-32" />
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
            {cfg && !cfg.llm_available ? (
              <p className="pt-3 text-xs text-muted-foreground">
                No LLM provider — running on the extractive summariser. Add
                <code className="mx-1">GROQ_API_KEY</code> to <code>.env</code> for full rewriting and quizzes.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Keyboard shortcuts</CardTitle></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3 text-sm">
            {[
              ["Presenter", [["→ / Space", "Next build / slide"], ["←", "Previous"], ["F", "Fullscreen"], ["B or .", "Blackout"], ["P", "Pause timer"], ["R", "Reset timer"]]],
              ["Diagram editor", [["Scroll", "Zoom at cursor"], ["Drag", "Pan"], ["Toolbar", "Fit / reset"], ["Toolbar", "Download SVG / PNG"]]],
              ["App", [["Cmd/Ctrl + B", "Collapse sidebar"]]],
            ].map(([group, rows]) => (
              <div key={group}>
                <p className="mb-2 font-medium">{group}</p>
                <dl className="flex flex-col gap-1.5">
                  {rows.map(([k, v]) => (
                    <div key={k + v} className="flex items-center justify-between gap-2">
                      <dt className="text-muted-foreground">{v}</dt>
                      <dd>
                        <kbd className="rounded border bg-muted px-1.5 py-0.5 text-[11px] font-medium">
                          {k}
                        </kbd>
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Data & storage</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm leading-relaxed text-muted-foreground">
            <p>
              Each deck is stored on the server running Learnova under{" "}
              <code className="rounded bg-muted px-1">.data/users/&lt;your-id&gt;/</code>{" "}
              — the markdown source, the PowerPoint, the web deck, and a slides
              JSON payload. Deleting a project removes that folder.
            </p>
            <p>
              LLM requests go only to the provider whose key is configured above.
              No analytics or telemetry leave the machine. Generation defaults on
              this page are stored in your browser's local storage, not on the
              server.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">About Learnova</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm leading-relaxed text-muted-foreground">
            <p>
              An AI presentation engine that reasons about the structure of your
              content — choosing per slide whether to keep text verbatim, tighten
              it, or turn it into a flowchart, timeline, chart, or diagram — then
              builds an animated PPTX and an interactive web deck from one model.
            </p>
            <p>
              The engagement score (PSF) and the pagination algorithm (CLASS) are
              grounded in Cognitive Load Theory and Mayer's multimedia principles.
            </p>
            <div className="flex gap-4 pt-1">
              <a href="/app/docs" className="underline hover:text-foreground">Documentation</a>
              <a href="/app/library" className="underline hover:text-foreground">Templates</a>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Account</CardTitle></CardHeader>
          <CardContent className="overflow-hidden">
            {typeof UserProfile === "function" ? (
              <UserProfile routing="hash" />
            ) : (
              <p className="text-sm text-muted-foreground">Sign in to manage your account.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
