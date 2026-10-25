/** Inline SVG empty-state illustrations in the Learnova palette. */
const B = "#2563EB", N = "#0B1F44", M = "#12C99B", Y = "#FFC93C", T = "#E6EEFD";

export function DecksIllustration({ className = "w-56" }) {
  return (
    <svg viewBox="0 0 240 160" className={className} fill="none" aria-hidden="true">
      <ellipse cx="120" cy="146" rx="84" ry="8" fill={T} />
      <rect x="58" y="34" width="124" height="82" rx="10" fill="#fff" stroke={N} strokeWidth="2.5" transform="rotate(-6 120 75)" />
      <rect x="52" y="40" width="124" height="82" rx="10" fill={T} stroke={N} strokeWidth="2.5" transform="rotate(-2 114 81)" />
      <rect x="64" y="30" width="124" height="86" rx="10" fill="#fff" stroke={N} strokeWidth="2.5" transform="rotate(4 126 73)" />
      <g transform="rotate(4 126 73)">
        <rect x="76" y="44" width="52" height="8" rx="4" fill={B} />
        <rect x="76" y="60" width="76" height="5" rx="2.5" fill="#C7D6F0" />
        <rect x="76" y="71" width="62" height="5" rx="2.5" fill="#C7D6F0" />
        <rect x="76" y="86" width="30" height="20" rx="4" fill={M} />
        <rect x="112" y="86" width="30" height="20" rx="4" fill={Y} />
        <rect x="148" y="86" width="26" height="20" rx="4" fill={B} opacity=".25" />
      </g>
      <circle cx="196" cy="38" r="9" fill={Y} stroke={N} strokeWidth="2.5" />
      <path d="M196 33v10M191 38h10" stroke={N} strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="40" cy="104" r="5" fill={M} stroke={N} strokeWidth="2.5" />
    </svg>
  );
}

export function NoResultsIllustration({ className = "w-44" }) {
  return (
    <svg viewBox="0 0 200 140" className={className} fill="none" aria-hidden="true">
      <ellipse cx="100" cy="126" rx="66" ry="7" fill={T} />
      <circle cx="90" cy="64" r="38" fill="#fff" stroke={N} strokeWidth="2.5" />
      <circle cx="90" cy="64" r="28" fill={T} />
      <path d="M118 92l30 30" stroke={N} strokeWidth="8" strokeLinecap="round" />
      <path d="M118 92l30 30" stroke={B} strokeWidth="3.5" strokeLinecap="round" />
      <path d="M78 58h24M82 70h16" stroke={B} strokeWidth="3" strokeLinecap="round" />
      <circle cx="152" cy="34" r="6" fill={Y} stroke={N} strokeWidth="2.5" />
      <circle cx="40" cy="92" r="4" fill={M} stroke={N} strokeWidth="2" />
    </svg>
  );
}

export function QuizIllustration({ className = "w-48" }) {
  return (
    <svg viewBox="0 0 220 150" className={className} fill="none" aria-hidden="true">
      <ellipse cx="110" cy="136" rx="76" ry="7" fill={T} />
      <rect x="50" y="22" width="120" height="96" rx="12" fill="#fff" stroke={N} strokeWidth="2.5" />
      <rect x="66" y="38" width="64" height="8" rx="4" fill={B} />
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(0 ${i * 22})`}>
          <circle cx="72" cy="66" r="7" fill={i === 1 ? M : "#fff"} stroke={N} strokeWidth="2.5" />
          {i === 1 && <path d="M68.5 66l2.5 2.5 4.5-5" stroke={N} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />}
          <rect x="88" y="63" width={60 - i * 8} height="6" rx="3" fill="#C7D6F0" />
        </g>
      ))}
      <circle cx="176" cy="30" r="14" fill={Y} stroke={N} strokeWidth="2.5" />
      <text x="176" y="36" textAnchor="middle" fontSize="18" fontWeight="700" fill={N}>?</text>
    </svg>
  );
}

export function InsightsIllustration({ className = "w-48" }) {
  return (
    <svg viewBox="0 0 220 150" className={className} fill="none" aria-hidden="true">
      <ellipse cx="110" cy="136" rx="80" ry="7" fill={T} />
      <rect x="30" y="20" width="160" height="98" rx="12" fill="#fff" stroke={N} strokeWidth="2.5" />
      <rect x="48" y="78" width="20" height="26" rx="4" fill={B} />
      <rect x="78" y="62" width="20" height="42" rx="4" fill={M} />
      <rect x="108" y="48" width="20" height="56" rx="4" fill={Y} stroke={N} strokeWidth="2" />
      <rect x="138" y="68" width="20" height="36" rx="4" fill={B} opacity=".35" />
      <path d="M46 52c20-4 34-16 50-12s30 8 52-8" stroke={N} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
