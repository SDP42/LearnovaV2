import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, Palette, Search, Sparkles, X } from "lucide-react";
import * as api from "@/api";
import { cn } from "@/lib/utils";

/**
 * Palette + template picker for the Composer / Create flow.
 *
 *   design = { palette: null | {id,name,…}, template: null | {id,name,…} }
 *
 * `null` means "Auto" — the generate request then carries nothing extra, so a
 * deck made without touching the picker is identical to before. Use
 * `designOptions(design)` to turn the choice into generate options.
 */
export const AUTO_DESIGN = { palette: null, template: null };

export function designOptions(design) {
  const o = {};
  if (design?.palette?.id) o.theme_id = design.palette.id;
  if (design?.template?.id) o.template_id = design.template.id;
  return o;
}

const WARM = { background: "#FFFAF5", card: "#FFFFFF", primary: "#C2502A", accent: "#F47B45", text: "#402B25", subtext: "#715A4E" };

const colorsOf = (p) =>
  p
    ? { background: p.background, card: p.card || "#fff", primary: p.primary, accent: p.accent || p.secondary || p.primary, text: p.text, subtext: p.subtext || p.text }
    : WARM;

/** Tiny CSS rendition of a template's title slide and content slide. */
function TemplateMini({ t, c }) {
  const r = Math.min(7, (t.card_radius || 0) * 22);
  const cardStyle = {
    background: c.card,
    borderRadius: r,
    border: t.card_border ? `1px solid ${c.subtext}55` : "1px solid transparent",
    boxShadow: t.card_border ? "none" : `0 1px 3px ${c.text}26`,
  };
  const bar = (w, color = c.text, h = 2.5, extra = {}) => (
    <span className="block rounded-full" style={{ width: `${w}%`, height: h, background: color, ...extra }} />
  );

  // ── title slide ──────────────────────────────────────────────────────────
  const title = (() => {
    switch (t.title_layout) {
      case "hero_split":
        return (
          <>
            <span className="absolute inset-y-0 left-0 w-1/2" style={{ background: c.primary }} />
            <span className="absolute left-[8%] top-[34%] flex w-[36%] flex-col gap-[3px]">
              {bar(100, c.background, 3)}
              {bar(70, c.background, 3)}
            </span>
            <span className="absolute right-[12%] top-[28%] size-[30%] rounded-full" style={{ background: c.accent }} />
          </>
        );
      case "left_band":
        return (
          <>
            <span className="absolute inset-y-0 left-0 w-[22%]" style={{ background: c.primary }} />
            <span className="absolute left-[32%] top-[36%] flex w-[56%] flex-col gap-[3px]">
              {bar(100, c.text, 3)}
              {bar(60, c.subtext, 2)}
            </span>
          </>
        );
      case "frame":
        return (
          <>
            <span className="absolute inset-[9%] rounded-[2px]" style={{ border: `1.5px solid ${c.primary}` }} />
            <span className="absolute inset-x-[24%] top-[38%] flex flex-col items-center gap-[3px]">
              {bar(100, c.text, 3)}
              {bar(60, c.subtext, 2)}
            </span>
          </>
        );
      case "poster":
        return (
          <>
            <span className="absolute inset-0" style={{ background: c.primary }} />
            <span className="absolute bottom-[16%] left-[10%] flex w-[64%] flex-col gap-[3px]">
              {bar(100, c.background, 4.5)}
              {bar(78, c.background, 4.5)}
            </span>
            <span className="absolute right-0 top-0 size-[26%]" style={{ background: c.accent, clipPath: "polygon(0 0,100% 0,100% 100%)" }} />
          </>
        );
      default: // centered
        return (
          <span className="absolute inset-x-[20%] top-[34%] flex flex-col items-center gap-[3px]">
            {bar(100, c.text, 3)}
            {bar(64, c.subtext, 2)}
            {bar(22, c.accent, 2.5, { marginTop: 3 })}
          </span>
        );
    }
  })();
  const titleBg = t.title_layout === "poster" ? c.primary : c.background;

  // ── content slide ────────────────────────────────────────────────────────
  const deco =
    t.decoration === "circles" ? (
      <>
        <span className="absolute -right-[8%] -top-[18%] size-[34%] rounded-full opacity-35" style={{ background: c.accent }} />
        <span className="absolute -bottom-[16%] right-[16%] size-[22%] rounded-full opacity-25" style={{ background: c.primary }} />
      </>
    ) : t.decoration === "dots" ? (
      <span className="absolute right-[6%] top-[6%] grid grid-cols-3 gap-[2px] opacity-70">
        {Array.from({ length: 6 }).map((_, i) => (
          <i key={i} className="block size-[3px] rounded-full" style={{ background: c.accent }} />
        ))}
      </span>
    ) : t.decoration === "lines" ? (
      <span className="absolute right-[6%] top-[8%] flex w-[22%] flex-col gap-[3px] opacity-60">
        {bar(100, c.accent, 1.5)}
        {bar(70, c.accent, 1.5)}
      </span>
    ) : t.decoration === "corner" ? (
      <span className="absolute bottom-0 right-0 size-[22%]" style={{ background: c.accent, clipPath: "polygon(100% 0,100% 100%,0 100%)" }} />
    ) : null;

  const header =
    t.header === "bar" ? (
      <span className="absolute inset-x-0 top-0 h-[24%]" style={{ background: c.primary }}>
        <span className="absolute left-[8%] top-1/2 -translate-y-1/2" style={{ width: "34%" }}>
          {bar(100, c.background, 3)}
        </span>
      </span>
    ) : t.header === "underline" ? (
      <span className="absolute inset-x-[8%] top-[10%] flex flex-col gap-[3px]">
        {bar(40, c.text, 3.5)}
        {bar(100, c.primary, 1.5)}
      </span>
    ) : t.header === "side" ? (
      <>
        <span className="absolute inset-y-0 left-0 w-[9%]" style={{ background: c.primary }} />
        <span className="absolute left-[16%] top-[10%] w-[36%]">{bar(100, c.text, 3.5)}</span>
      </>
    ) : t.header === "ribbon" ? (
      <span className="absolute left-[6%] top-[8%] flex h-[16%] w-[46%] items-center rounded-full pl-[6%]" style={{ background: c.primary }}>
        <span className="w-[70%]">{bar(100, c.background, 3)}</span>
      </span>
    ) : (
      <span className="absolute left-[8%] top-[10%] w-[34%]">{bar(100, c.text, 4)}</span>
    );

  const footer =
    t.footer === "pill" ? (
      <span className="absolute bottom-[5%] left-1/2 h-[6px] w-[22%] -translate-x-1/2 rounded-full" style={{ background: c.primary, opacity: 0.85 }} />
    ) : t.footer === "rule" ? (
      <span className="absolute inset-x-[8%] bottom-[8%] flex flex-col gap-[2px]">
        {bar(100, `${c.subtext}66`, 1)}
      </span>
    ) : (
      <span className="absolute bottom-[7%] right-[8%] size-[4px] rounded-full" style={{ background: c.subtext }} />
    );

  const leftPad = t.header === "side" ? "21%" : "8%";

  return (
    <div className="grid grid-cols-2 gap-1.5">
      <div className="relative aspect-[16/10] overflow-hidden rounded-[5px] border border-black/10" style={{ background: titleBg }}>
        {title}
      </div>
      <div className="relative aspect-[16/10] overflow-hidden rounded-[5px] border border-black/10" style={{ background: c.background }}>
        {deco}
        {header}
        <span className="absolute bottom-[18%] top-[36%] flex gap-[4px]" style={{ left: leftPad, right: "8%" }}>
          <span className="flex-1" style={cardStyle} />
          <span className="flex-1" style={cardStyle} />
        </span>
        {footer}
      </div>
    </div>
  );
}

function PaletteSwatch({ p, selected, onPick }) {
  const dots = [
    [p.background, "Background"],
    [p.primary, "Primary"],
    [p.accent || p.secondary, "Accent"],
    [p.text, "Text"],
  ];
  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      onClick={() => onPick(p)}
      title={`${p.name} — ${p.category}, ${p.mode}`}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-xl border bg-white text-left transition duration-150 hover:-translate-y-0.5 hover:border-[#E3A98B] hover:shadow-[0_10px_22px_-14px_rgb(64_43_37/0.4)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#D95D39]",
        selected && "border-[#C2502A] ring-2 ring-[#C2502A]/30"
      )}
    >
      <span className="relative flex h-12 items-end gap-1.5 p-2" style={{ background: p.background }}>
        <span className="flex h-full flex-1 flex-col justify-center gap-1 rounded-md px-1.5" style={{ background: p.card || "#fff", boxShadow: `0 0 0 1px ${p.text}1f` }}>
          <span className="block h-[3px] w-3/4 rounded-full" style={{ background: p.primary }} />
          <span className="block h-[2px] w-1/2 rounded-full" style={{ background: p.text, opacity: 0.55 }} />
        </span>
        <span className="mb-0.5 font-[Bricolage_Grotesque] text-[15px] font-bold leading-none" style={{ color: p.text }}>
          Aa
        </span>
        {selected ? (
          <span className="absolute right-1.5 top-1.5 grid size-4 place-items-center rounded-full bg-[#C2502A] text-white">
            <Check className="size-2.5" strokeWidth={3.5} />
          </span>
        ) : null}
      </span>
      <span className="flex items-center gap-1 px-2 pb-1 pt-1.5">
        {dots.map(([c, label], i) => (
          <span key={i} aria-hidden title={label} className="size-3 rounded-full ring-1 ring-black/15" style={{ background: c }} />
        ))}
      </span>
      <span className="line-clamp-2 min-h-[30px] px-2 pb-2 text-[12px] font-semibold leading-[15px] text-[#402B25]">{p.name}</span>
    </button>
  );
}

/** Small dot trio used in the trigger and chips. */
export function PaletteDots({ p, size = 10 }) {
  if (!p) return <Sparkles className="size-3.5 text-[#B44A22]" aria-hidden />;
  return (
    <span className="inline-flex" aria-hidden>
      {[p.background, p.primary, p.accent || p.secondary].map((c, i) => (
        <span key={i} className="rounded-full ring-1 ring-black/20" style={{ width: size, height: size, background: c, marginLeft: i ? -3 : 0 }} />
      ))}
    </span>
  );
}

/** Stateless-ish modal: owns its fetches, but not the chosen design. */
export default function DesignPicker({ design, onChange, className, triggerClassName }) {
  const [open, setOpen] = useState(false);
  const [lib, setLib] = useState(null); // {palettes, categories}
  const [tpls, setTpls] = useState(null); // [{...}]
  const [failed, setFailed] = useState(false);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");
  const [mode, setMode] = useState("light");

  // Fetch lazily the first time the panel opens; never block the Composer on it.
  useEffect(() => {
    if (!open || lib || failed) return;
    let live = true;
    Promise.all([api.listPalettes(), api.listTemplates()])
      .then(([p, t]) => {
        if (!live) return;
        setLib({ palettes: p.palettes || [], categories: p.categories || [] });
        setTpls(t.templates || []);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [open, lib, failed]);

  const palettes = useMemo(() => {
    if (!lib) return [];
    const t = q.trim().toLowerCase();
    return lib.palettes.filter(
      (p) =>
        p.mode === mode &&
        (cat === "All" || p.category === cat) &&
        (!t || p.name.toLowerCase().includes(t) || (p.tags || []).some((x) => x.toLowerCase().includes(t)))
    );
  }, [lib, q, cat, mode]);

  const cats = useMemo(() => ["All", ...(lib?.categories || [])], [lib]);
  const colors = colorsOf(design.palette);
  const set = (patch) => onChange({ ...design, ...patch });
  const isAuto = !design.palette && !design.template;
  const label = [design.palette?.name, design.template?.name].filter(Boolean).join(" · ") || "Auto";

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          aria-label={`Design: ${label}. Choose a palette and template`}
          className={cn(
            "inline-flex h-10 max-w-full items-center gap-2 rounded-full border border-[#E8D8C9] bg-[#FFFAF5] px-3 text-[13px] font-medium text-[#4F3A31] transition duration-150 hover:-translate-y-px hover:border-[#E3A98B] hover:bg-white sm:h-9",
            !isAuto && "border-[#E3A98B] bg-[#FDEEE3]",
            triggerClassName
          )}
        >
          <Palette className="size-4 shrink-0 text-[#B44A22]" aria-hidden />
          <span className="text-[#765F53]">Design:</span>
          <span className="max-w-[180px] truncate">{isAuto ? "Auto" : "Custom"}</span>
          {design.palette ? <PaletteDots p={design.palette} /> : null}
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-[#402B25]/45 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          aria-describedby={undefined}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className={cn(
            "fixed z-[61] flex flex-col overflow-hidden border border-[#E8D8C9] bg-[#FFFAF5] text-[#402B25] shadow-[0_30px_80px_-24px_rgb(64_43_37/0.55)] outline-none",
            // phone: bottom sheet; desktop: centred card
            "inset-x-0 bottom-0 max-h-[90svh] rounded-t-[24px] data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom data-[state=closed]:animate-out data-[state=closed]:slide-out-to-bottom",
            "sm:inset-auto sm:left-1/2 sm:top-1/2 sm:max-h-[min(88svh,780px)] sm:w-[min(94vw,760px)] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[24px] sm:data-[state=open]:zoom-in-95 sm:data-[state=open]:slide-in-from-bottom-0",
            className
          )}
        >
          <header className="flex items-center gap-3 border-b border-[#E8D8C9] bg-white px-4 py-3 sm:px-5">
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#FCE5D6] text-[#8F3A18]">
              <Palette className="size-[18px]" />
            </span>
            <div className="min-w-0 flex-1">
              <Dialog.Title className="font-[Bricolage_Grotesque] text-[19px] font-bold leading-tight tracking-tight">Choose a look</Dialog.Title>
              <p className="truncate text-[12.5px] text-[#715A4E]">Pick a palette and a template, or let Auto choose by topic.</p>
            </div>
            <Dialog.Close
              aria-label="Close"
              className="grid size-10 shrink-0 place-items-center rounded-full text-[#715A4E] transition-colors hover:bg-[#F3E6DA] focus-visible:outline-2 focus-visible:outline-[#D95D39] sm:size-9"
            >
              <X className="size-4" />
            </Dialog.Close>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">
            {/* Auto */}
            <button
              type="button"
              onClick={() => onChange(AUTO_DESIGN)}
              aria-pressed={isAuto}
              className={cn(
                "flex w-full items-center gap-3 rounded-2xl border bg-white px-3 py-2.5 text-left transition duration-150 hover:border-[#E3A98B] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#D95D39]",
                isAuto ? "border-[#C2502A] ring-2 ring-[#C2502A]/25" : "border-[#E8D8C9]"
              )}
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#F47B45] text-[#2A1A14]">
                <Sparkles className="size-[18px]" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[14px] font-bold">Auto <span className="ml-1 rounded-full bg-[#FCE5D6] px-2 py-0.5 text-[11px] font-bold text-[#8F3A18]">Default</span></span>
                <span className="block text-[12.5px] leading-[18px] text-[#715A4E]">Learnova reads the topic and picks the colours, with the standard layout.</span>
              </span>
              {isAuto ? <Check className="size-5 shrink-0 text-[#C2502A]" strokeWidth={3} /> : null}
            </button>

            {failed ? (
              <p role="status" className="mt-4 rounded-xl border border-[#E8D8C9] bg-white px-4 py-3 text-[13px] leading-5 text-[#4F3A31]">
                The palette library isn’t available from this server yet, so Auto will choose the colours. Everything else keeps working.
              </p>
            ) : (
              <>
                {/* palettes */}
                <section className="mt-4" aria-label="Palettes">
                  <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-[12px] font-bold uppercase tracking-[0.12em] text-[#715A4E]">Palette</h3>
                    <div className="inline-flex rounded-full border border-[#E8D8C9] bg-white p-0.5" role="group" aria-label="Light or dark deck">
                      {["light", "dark"].map((m) => (
                        <button
                          key={m}
                          type="button"
                          aria-pressed={mode === m}
                          onClick={() => setMode(m)}
                          className={cn(
                            "h-8 rounded-full px-3.5 text-[12.5px] font-semibold capitalize text-[#715A4E] transition-colors focus-visible:outline-2 focus-visible:outline-[#D95D39]",
                            mode === m && "bg-[#402B25] text-[#FFFAF5]"
                          )}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#765F53]" />
                    <input
                      value={q}
                      onChange={(e) => setQ(e.target.value)}
                      placeholder="Search palettes, e.g. teal, warm, tech"
                      aria-label="Search palettes"
                      className="h-10 w-full rounded-full border border-[#E8D8C9] bg-white pl-9 pr-9 text-[14px] text-[#402B25] outline-none transition placeholder:text-[#765F53] focus:border-[#E3A98B] focus:ring-[3px] focus:ring-[#F47B45]/20"
                    />
                    {q ? (
                      <button type="button" onClick={() => setQ("")} aria-label="Clear search" className="absolute right-1.5 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-full text-[#765F53] hover:bg-[#F3E6DA]">
                        <X className="size-3.5" />
                      </button>
                    ) : null}
                  </div>
                  <div className="lv-no-scrollbar -mx-1 mt-2.5 flex gap-1.5 overflow-x-auto px-1 pb-0.5" role="group" aria-label="Palette category">
                    {cats.map((c) => (
                      <button
                        key={c}
                        type="button"
                        aria-pressed={cat === c}
                        onClick={() => setCat(c)}
                        className={cn(
                          "h-9 shrink-0 rounded-full border px-3.5 text-[13px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-[#D95D39]",
                          cat === c ? "border-[#C2502A] bg-[#FCE5D6] text-[#8F3A18]" : "border-[#E8D8C9] bg-white text-[#4F3A31] hover:border-[#E3A98B]"
                        )}
                      >
                        {c}
                      </button>
                    ))}
                  </div>

                  <div
                    role="listbox"
                    aria-label="Palettes"
                    className="mt-3 grid max-h-[34svh] grid-cols-2 gap-2.5 overflow-y-auto rounded-2xl border border-[#E8D8C9] bg-[#F7EFE8] p-2.5 sm:max-h-[236px] sm:grid-cols-3 md:grid-cols-4"
                  >
                    {!lib
                      ? Array.from({ length: 8 }).map((_, i) => <div key={i} className="lv-skel h-[112px] rounded-xl" />)
                      : palettes.length
                      ? palettes.map((p) => (
                          <PaletteSwatch key={p.id} p={p} selected={design.palette?.id === p.id} onPick={(x) => set({ palette: design.palette?.id === x.id ? null : x })} />
                        ))
                      : (
                        <p className="col-span-full px-2 py-8 text-center text-[13px] text-[#715A4E]">No {mode} palettes match “{q}”. Try another word or switch to {mode === "light" ? "dark" : "light"}.</p>
                      )}
                  </div>
                  {lib ? <p className="mt-1.5 text-[12px] text-[#715A4E]">{palettes.length} {mode} palette{palettes.length === 1 ? "" : "s"} · every one is contrast-checked</p> : null}
                </section>

                {/* templates */}
                <section className="mt-4" aria-label="Templates">
                  <h3 className="mb-2.5 text-[12px] font-bold uppercase tracking-[0.12em] text-[#715A4E]">Template</h3>
                  <div className="-mx-1 flex snap-x gap-2.5 overflow-x-auto px-1 pb-2" role="listbox" aria-label="Templates">
                    <button
                      type="button"
                      role="option"
                      aria-selected={!design.template}
                      onClick={() => set({ template: null })}
                      className={cn(
                        "flex w-[148px] shrink-0 snap-start flex-col justify-between gap-2 rounded-xl border bg-white p-2.5 text-left transition duration-150 hover:-translate-y-0.5 hover:border-[#E3A98B] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#D95D39]",
                        !design.template ? "border-[#C2502A] ring-2 ring-[#C2502A]/25" : "border-[#E8D8C9]"
                      )}
                    >
                      <span className="grid aspect-[16/6.2] place-items-center rounded-[6px] bg-[#FCE5D6] text-[#8F3A18]">
                        <Sparkles className="size-5" />
                      </span>
                      <span>
                        <span className="block text-[13px] font-bold">Auto</span>
                        <span className="block text-[11.5px] leading-4 text-[#715A4E]">Standard layout</span>
                      </span>
                    </button>
                    {!tpls
                      ? Array.from({ length: 5 }).map((_, i) => <div key={i} className="lv-skel h-[116px] w-[148px] shrink-0 rounded-xl" />)
                      : tpls.map((t) => {
                          const on = design.template?.id === t.id;
                          return (
                            <button
                              key={t.id}
                              type="button"
                              role="option"
                              aria-selected={on}
                              onClick={() => set({ template: on ? null : t })}
                              title={t.description}
                              className={cn(
                                "flex w-[148px] shrink-0 snap-start flex-col gap-2 rounded-xl border bg-white p-2.5 text-left transition duration-150 hover:-translate-y-0.5 hover:border-[#E3A98B] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#D95D39]",
                                on ? "border-[#C2502A] ring-2 ring-[#C2502A]/25" : "border-[#E8D8C9]"
                              )}
                            >
                              <TemplateMini t={t} c={colors} />
                              <span className="flex items-center justify-between gap-1">
                                <span className="truncate text-[13px] font-bold">{t.name}</span>
                                {on ? <Check className="size-3.5 shrink-0 text-[#C2502A]" strokeWidth={3.5} /> : null}
                              </span>
                            </button>
                          );
                        })}
                  </div>
                  {design.template ? <p className="text-[12.5px] leading-5 text-[#715A4E]">{design.template.description}</p> : null}
                </section>
              </>
            )}
          </div>

          <footer className="flex items-center gap-2 border-t border-[#E8D8C9] bg-white px-4 py-3 sm:px-5">
            <span className="min-w-0 flex-1 truncate text-[12.5px] text-[#715A4E]">
              {isAuto ? "Auto — chosen by topic" : label}
            </span>
            <button
              type="button"
              onClick={() => onChange(AUTO_DESIGN)}
              disabled={isAuto}
              className="h-10 rounded-full border border-[#E8D8C9] bg-white px-4 text-[13px] font-semibold text-[#4F3A31] transition hover:border-[#E3A98B] disabled:opacity-40 sm:h-9"
            >
              Reset to Auto
            </button>
            <Dialog.Close className="h-10 rounded-full bg-[#F47B45] px-5 text-[13px] font-bold text-[#2A1A14] transition duration-150 hover:-translate-y-px hover:bg-[#FF8A58] sm:h-9">
              Done
            </Dialog.Close>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/** The chosen palette / template as removable chips (renders nothing for Auto). */
export function DesignChips({ design, onChange, className }) {
  if (!design.palette && !design.template) return null;
  const chip = (key, icon, text, onRemove) => (
    <span key={key} className="inline-flex h-8 items-center gap-2 rounded-full border border-[#E3A98B] bg-[#FDEEE3] pl-3 pr-1 text-[12.5px] font-semibold text-[#8F3A18]">
      {icon}
      <span className="max-w-[200px] truncate">{text}</span>
      <button type="button" onClick={onRemove} aria-label={`Remove ${text}`} className="grid size-6 place-items-center rounded-full transition-colors hover:bg-[#FCE5D6] focus-visible:outline-2 focus-visible:outline-[#D95D39]">
        <X className="size-3.5" />
      </button>
    </span>
  );
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {design.palette ? chip("p", <PaletteDots p={design.palette} />, design.palette.name, () => onChange({ ...design, palette: null })) : null}
      {design.template ? chip("t", <Palette className="size-3.5" aria-hidden />, `${design.template.name} template`, () => onChange({ ...design, template: null })) : null}
    </div>
  );
}
