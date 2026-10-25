/** Mini slide renderings: the "raw text wall" and the visual forms Learnova turns it into. */
const INK = "#0B1F44";

export function RawFace({ title = "Photosynthesis" }) {
  const w = [270, 255, 265, 190, 270, 250, 262, 150, 268, 240, 120];
  return (
    <svg viewBox="0 0 300 186" className="cv-svg">
      <rect width="300" height="186" fill="#fff" />
      <text x="16" y="28" fontSize="15" fontWeight="700" fill={INK} fontFamily="Times, serif">{title}</text>
      {w.map((x, i) => <rect key={i} x="16" y={42 + i * 12.5} width={x} height="5" rx="2" fill="#0B1F44" opacity={0.22 + (i % 3) * 0.06} />)}
    </svg>
  );
}

const H = [222, 162, 44, 356, 198, 262];
export function VisualFace({ kind = 0 }) {
  const h = H[kind % H.length];
  const a = `hsl(${h} 80% 56%)`, soft = `hsl(${h} 90% 94%)`, mid = `hsl(${h} 85% 82%)`;
  return (
    <svg viewBox="0 0 300 186" className="cv-svg">
      <defs><linearGradient id={`vf${kind}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor={soft} /></linearGradient></defs>
      <rect width="300" height="186" fill={`url(#vf${kind})`} />
      <rect x="16" y="16" width="86" height="9" rx="4.5" fill={a} />
      <rect x="16" y="32" width="140" height="5" rx="2.5" fill={INK} opacity=".2" />
      {kind % 6 === 0 && [50, 90, 70, 118, 100].map((v, i) => <rect key={i} x={30 + i * 50} y={170 - v} width="32" height={v} rx="6" fill={i === 3 ? a : mid} />)}
      {kind % 6 === 1 && [0, 1, 2, 3].map((i) => (
        <g key={i}>
          <rect x={18 + i * 70} y="86" width="56" height="40" rx="10" fill="#fff" stroke={a} strokeWidth="2.5" />
          <rect x={28 + i * 70} y="102" width="36" height="5" rx="2.5" fill={a} opacity=".5" />
          {i < 3 && <path d={`M${76 + i * 70} 106h10m-4 -4l4 4l-4 4`} stroke={a} strokeWidth="2.5" fill="none" strokeLinecap="round" />}
        </g>
      ))}
      {kind % 6 === 2 && <g>
        <line x1="24" y1="112" x2="276" y2="112" stroke={a} strokeWidth="3" strokeLinecap="round" />
        {[0, 1, 2, 3, 4].map((i) => <g key={i}><circle cx={40 + i * 55} cy="112" r="9" fill={a} /><rect x={22 + i * 55} y={i % 2 ? 130 : 78} width="36" height="14" rx="5" fill="#fff" stroke={mid} /></g>)}
      </g>}
      {kind % 6 === 3 && [0, 1, 2].map((i) => <g key={i}><rect x={18 + i * 94} y="60" width="84" height="94" rx="14" fill="#fff" stroke={mid} /><text x={30 + i * 94} y="112" fontSize="30" fontWeight="800" fill={a} fontFamily="Bricolage Grotesque, sans-serif">{["92%", "3×", "48"][i]}</text><rect x={30 + i * 94} y="128" width="50" height="5" rx="2.5" fill={INK} opacity=".25" /></g>)}
      {kind % 6 === 4 && <g>
        {[0, 1, 2, 3].map((i) => { const t = (i / 4) * Math.PI * 2 - Math.PI / 2; return <g key={i}><circle cx={150 + Math.cos(t) * 52} cy={112 + Math.sin(t) * 44} r="16" fill={i === 0 ? a : mid} /></g>; })}
        <circle cx="150" cy="112" r="52" fill="none" stroke={a} strokeWidth="2.5" strokeDasharray="6 7" opacity=".55" />
      </g>}
      {kind % 6 === 5 && <g>
        <rect x="24" y="64" width="120" height="100" rx="12" fill="#fff" stroke={mid} />
        <rect x="156" y="64" width="120" height="100" rx="12" fill={soft} stroke={a} strokeWidth="2" />
        {[0, 1, 2].map((i) => <g key={i}><rect x="38" y={80 + i * 26} width="80" height="6" rx="3" fill={INK} opacity=".25" /><rect x="170" y={80 + i * 26} width={70 - i * 12} height="6" rx="3" fill={a} /></g>)}
      </g>}
    </svg>
  );
}
