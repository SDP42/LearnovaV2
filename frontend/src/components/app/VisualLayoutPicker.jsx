import { cn } from "@/lib/utils";

/**
 * "Choose visual style" — a grid of layout cards with a small schematic glyph.
 * Controlled: `value` is a family key (or "auto"), `onChange(key)` fires on click.
 * Advisory only — it biases generation; the Deck Director still validates
 * each slide against its content.
 */
const S = { className: "h-10 w-full", viewBox: "0 0 80 40", fill: "none" };
const stroke = "currentColor";

const GLYPHS = {
  auto: (
    <svg {...S}>
      <circle cx="40" cy="20" r="9" stroke={stroke} strokeWidth="2" />
      <path d="M40 6v4M40 30v4M26 20h4M50 20h4" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  PROCESS_LINEAR: (
    <svg {...S}>
      <rect x="6" y="14" width="16" height="12" rx="2" stroke={stroke} strokeWidth="2" />
      <rect x="32" y="14" width="16" height="12" rx="2" stroke={stroke} strokeWidth="2" />
      <rect x="58" y="14" width="16" height="12" rx="2" stroke={stroke} strokeWidth="2" />
      <path d="M22 20h10M48 20h10" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  PROCESS_CYCLIC: (
    <svg {...S}>
      <path d="M40 8a12 12 0 1 1-10 6" stroke={stroke} strokeWidth="2" />
      <path d="M28 12l2 6 6-2" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  TIMELINE: (
    <svg {...S}>
      <path d="M8 20h64" stroke={stroke} strokeWidth="2" />
      {[16, 36, 56].map((x) => (
        <circle key={x} cx={x} cy="20" r="4" fill={stroke} />
      ))}
    </svg>
  ),
  COMPARE_TABLE: (
    <svg {...S}>
      <rect x="8" y="8" width="64" height="24" rx="2" stroke={stroke} strokeWidth="2" />
      <path d="M40 8v24M8 20h64" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  KPI: (
    <svg {...S}>
      <rect x="8" y="10" width="28" height="20" rx="3" stroke={stroke} strokeWidth="2" />
      <rect x="44" y="10" width="28" height="20" rx="3" stroke={stroke} strokeWidth="2" />
      <path d="M16 22h12M52 22h12" stroke={stroke} strokeWidth="3" />
    </svg>
  ),
  MATRIX_GRID: (
    <svg {...S}>
      <rect x="16" y="6" width="48" height="28" rx="2" stroke={stroke} strokeWidth="2" />
      <path d="M40 6v28M16 20h48" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  HIERARCHY_NEST: (
    <svg {...S}>
      <path d="M40 6l14 24H26z" stroke={stroke} strokeWidth="2" />
      <path d="M31 22h18" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  SET_DIAGRAM: (
    <svg {...S}>
      <circle cx="32" cy="20" r="12" stroke={stroke} strokeWidth="2" />
      <circle cx="48" cy="20" r="12" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  MIND_MAP: (
    <svg {...S}>
      <circle cx="40" cy="20" r="6" stroke={stroke} strokeWidth="2" />
      <path d="M40 14l-14-6M40 26l-14 6M46 20h16" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
  CHART_CATEGORICAL: (
    <svg {...S}>
      <path d="M12 32V22M28 32V12M44 32V18M60 32V8" stroke={stroke} strokeWidth="4" />
    </svg>
  ),
  CHART_PART_TO_WHOLE: (
    <svg {...S}>
      <circle cx="40" cy="20" r="12" stroke={stroke} strokeWidth="2" />
      <path d="M40 20V8M40 20l10 6" stroke={stroke} strokeWidth="2" />
    </svg>
  ),
};

const OPTIONS = [
  { key: "auto", label: "Auto" },
  { key: "PROCESS_LINEAR", label: "Flow" },
  { key: "PROCESS_CYCLIC", label: "Cycle" },
  { key: "TIMELINE", label: "Timeline" },
  { key: "COMPARE_TABLE", label: "Comparison" },
  { key: "KPI", label: "KPI cards" },
  { key: "MATRIX_GRID", label: "2x2 matrix" },
  { key: "HIERARCHY_NEST", label: "Pyramid" },
  { key: "SET_DIAGRAM", label: "Venn" },
  { key: "MIND_MAP", label: "Mind map" },
  { key: "CHART_CATEGORICAL", label: "Bar chart" },
  { key: "CHART_PART_TO_WHOLE", label: "Pie chart" },
];

export default function VisualLayoutPicker({ value = "auto", onChange }) {
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
      {OPTIONS.map((o) => (
        <button
          key={o.key}
          type="button"
          onClick={() => onChange?.(o.key)}
          className={cn(
            "flex flex-col items-center gap-1.5 rounded-lg border p-3 text-xs transition-colors",
            value === o.key
              ? "border-primary bg-primary/5 text-foreground"
              : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
          )}
        >
          <span className={value === o.key ? "text-primary" : ""}>{GLYPHS[o.key]}</span>
          <span className="font-medium">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
