import * as THREE from "three";

const INK = "#0B1F44";
const HUES = [222, 162, 44, 356, 198, 262];

function tex(draw, w = 320, h = 200) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 2;
  return t;
}

/** A dense wall-of-text page: what people usually put on slides. */
export function rawTexture(v) {
  return tex((g, w, h) => {
    g.fillStyle = "#fff";
    g.fillRect(0, 0, w, h);
    g.fillStyle = INK;
    g.font = "700 15px Georgia, serif";
    g.fillText(["Photosynthesis", "Supply chains", "Cell division"][v % 3], 16, 28);
    for (let i = 0; i < 11; i++) {
      g.fillStyle = `rgba(11,31,68,${0.2 + (i % 3) * 0.06})`;
      const lw = [285, 270, 280, 200, 285, 262, 276, 160, 282, 250, 130][(i + v * 2) % 11];
      g.fillRect(16, 44 + i * 13, lw, 5);
    }
  });
}

/** A designed visual slide: chart / flow / timeline / KPI / cycle / compare. */
export function visualTexture(k) {
  const h = HUES[k % HUES.length];
  const a = `hsl(${h} 82% 52%)`;
  const mid = `hsl(${h} 85% 80%)`;
  const soft = `hsl(${h} 95% 95%)`;
  return tex((g, w, hh) => {
    const gr = g.createLinearGradient(0, 0, w, hh);
    gr.addColorStop(0, "#fff");
    gr.addColorStop(1, soft);
    g.fillStyle = gr;
    g.fillRect(0, 0, w, hh);
    g.fillStyle = a;
    g.fillRect(18, 18, 96, 10);
    g.fillStyle = "rgba(11,31,68,.2)";
    g.fillRect(18, 36, 150, 6);
    const kind = k % 6;
    g.lineWidth = 3;
    g.strokeStyle = a;
    if (kind === 0) {
      [60, 100, 78, 126, 108].forEach((v, i) => {
        g.fillStyle = i === 3 ? a : mid;
        g.fillRect(36 + i * 54, 184 - v, 34, v);
      });
    } else if (kind === 1) {
      for (let i = 0; i < 4; i++) {
        g.fillStyle = "#fff";
        g.beginPath();
        g.roundRect(20 + i * 74, 96, 58, 42, 10);
        g.fill();
        g.stroke();
        if (i < 3) {
          g.beginPath();
          g.moveTo(80 + i * 74, 117);
          g.lineTo(92 + i * 74, 117);
          g.stroke();
        }
      }
    } else if (kind === 2) {
      g.beginPath();
      g.moveTo(26, 120);
      g.lineTo(294, 120);
      g.stroke();
      for (let i = 0; i < 5; i++) {
        g.fillStyle = a;
        g.beginPath();
        g.arc(44 + i * 58, 120, 9, 0, 7);
        g.fill();
        g.fillStyle = mid;
        g.fillRect(26 + i * 58, i % 2 ? 140 : 84, 36, 12);
      }
    } else if (kind === 3) {
      for (let i = 0; i < 3; i++) {
        g.fillStyle = "#fff";
        g.beginPath();
        g.roundRect(20 + i * 100, 68, 88, 100, 14);
        g.fill();
        g.strokeStyle = mid;
        g.stroke();
        g.fillStyle = a;
        g.font = "800 30px sans-serif";
        g.fillText(["92%", "3×", "48"][i], 32 + i * 100, 122);
      }
    } else if (kind === 4) {
      g.setLineDash([6, 7]);
      g.beginPath();
      g.arc(160, 120, 54, 0, 7);
      g.stroke();
      g.setLineDash([]);
      for (let i = 0; i < 4; i++) {
        const t = (i / 4) * Math.PI * 2 - Math.PI / 2;
        g.fillStyle = i === 0 ? a : mid;
        g.beginPath();
        g.arc(160 + Math.cos(t) * 54, 120 + Math.sin(t) * 54, 15, 0, 7);
        g.fill();
      }
    } else {
      g.fillStyle = "#fff";
      g.fillRect(26, 70, 126, 108);
      g.fillStyle = soft;
      g.fillRect(168, 70, 126, 108);
      g.strokeStyle = a;
      g.strokeRect(168, 70, 126, 108);
      for (let i = 0; i < 3; i++) {
        g.fillStyle = "rgba(11,31,68,.22)";
        g.fillRect(40, 88 + i * 28, 84, 7);
        g.fillStyle = a;
        g.fillRect(182, 88 + i * 28, 90 - i * 14, 7);
      }
    }
  });
}

export function glowTexture(color = "#2563EB") {
  return tex((g, w, h) => {
    const r = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
    r.addColorStop(0, color + "cc");
    r.addColorStop(0.4, color + "44");
    r.addColorStop(1, color + "00");
    g.fillStyle = r;
    g.fillRect(0, 0, w, h);
  }, 128, 128);
}
