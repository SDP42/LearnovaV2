/**
 * Haikei-style SVG backgrounds (layered waves, blobs, stacked steps), authored
 * inline so they are crisp at any size, themeable via props, and cost no requests.
 * Haikei (haikei.app) is a generator; these reproduce its wave / blob / layered-
 * step output rather than embedding exported files.
 */
export function Waves({ colors = ["#FFF1E6", "#FDD9C2", "#F8B48E"], flip = false, className = "", height = 160 }) {
  const d = [
    "M0 70 C240 10 480 130 720 70 S1200 10 1440 70 V160 H0Z",
    "M0 100 C200 50 440 150 720 100 S1220 50 1440 100 V160 H0Z",
    "M0 130 C260 90 460 170 720 130 S1180 90 1440 130 V160 H0Z",
  ];
  return (
    <svg className={className} viewBox="0 0 1440 160" preserveAspectRatio="none" aria-hidden
      style={{ display: "block", width: "100%", height, transform: flip ? "scaleY(-1)" : undefined }}>
      {d.map((p, i) => <path key={i} d={p} fill={colors[i % colors.length]} />)}
    </svg>
  );
}

export function Blobs({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 900 600" preserveAspectRatio="xMidYMid slice" aria-hidden
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <defs>
        <linearGradient id="hk1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#FFC9A8" /><stop offset="1" stopColor="#F9A57A" /></linearGradient>
        <linearGradient id="hk2" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#FFE7B8" /><stop offset="1" stopColor="#FFF2D6" /></linearGradient>
      </defs>
      <path fill="url(#hk1)" opacity=".7" d="M0 80C80 40 190 20 280 70s170 130 110 210S190 360 100 330 0 190 0 80Z" />
      <path fill="url(#hk2)" opacity=".7" d="M900 600C820 560 740 500 700 420s-10-170 80-190 180 30 120 120-20 250 0 250Z">
      </path>
      <circle cx="620" cy="90" r="110" fill="url(#hk1)" opacity=".35" />
    </svg>
  );
}

export function Steps({ className = "" }) {
  const c = ["#FFF1E6", "#FDDFCB", "#F9C4A4", "#F4A57C"];
  return (
    <svg className={className} viewBox="0 0 900 200" preserveAspectRatio="none" aria-hidden style={{ display: "block", width: "100%", height: 120 }}>
      {c.map((f, i) => <path key={i} fill={f} d={`M0 ${60 + i * 36}L${150 + i * 40} ${60 + i * 36}L${150 + i * 40} ${80 + i * 36}L${450 + i * 60} ${80 + i * 36}L${450 + i * 60} ${40 + i * 36}L900 ${40 + i * 36}V200H0Z`} />)}
    </svg>
  );
}
