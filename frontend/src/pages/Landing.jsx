import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { useAuth } from "@/auth";
import markup from "../landing/landing.html?raw";
import "../landing/landing.css";
import "../landing/landing-extra.css";

gsap.registerPlugin(ScrollTrigger);

const DESIGN_WIDTH = 1440;
const SEEN_KEY = "learnova.loader.seen";

/** Wrap each word of an element's text in a span, keeping <em> and <br>. */
function splitWords(el) {
  const walk = (node) => {
    [...node.childNodes].forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        const frag = document.createDocumentFragment();
        child.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) frag.appendChild(document.createTextNode(part));
          else {
            const span = document.createElement("span");
            span.className = "l-w";
            span.textContent = part;
            frag.appendChild(span);
          }
        });
        child.replaceWith(frag);
      } else if (child.nodeType === Node.ELEMENT_NODE && child.tagName !== "BR") {
        walk(child);
      }
    });
  };
  walk(el);
  return el.querySelectorAll(".l-w");
}

/**
 * Draw the pipeline's connectors from where the boxes actually are, so lines
 * always meet their boxes whatever the screen size. Uses offset positions
 * (layout, not transforms) so it is unaffected by the fit scaling or by boxes
 * mid-animation. Returns the main edges in drawing order.
 */
function drawFlow(fl) {
  const svg = fl.querySelector(".l-fledges");
  const cols = [...fl.querySelectorAll(".l-fcol")].map((col) =>
    [...col.querySelectorAll(".l-node")].map((n) => {
      const l = col.offsetLeft + n.offsetLeft;
      const t = col.offsetTop + n.offsetTop;
      return { l, r: l + n.offsetWidth, t, b: t + n.offsetHeight, cx: l + n.offsetWidth / 2, cy: t + n.offsetHeight / 2 };
    }),
  );
  const main = [];
  for (let i = 0; i < cols.length - 1; i += 1) {
    cols[i].forEach((a) => cols[i + 1].forEach((b) => {
      const mx = (a.r + b.l) / 2;
      main.push(`M${a.r} ${a.cy} H${mx} V${b.cy} H${b.l - 3}`);
    }));
  }
  const all = cols.flat();
  const bottom = Math.max(...all.map((n) => n.b));
  const top = Math.min(...all.map((n) => n.t));
  const auction = cols[4][0], audit = cols[5][0], out = cols[7][0];
  svg.innerHTML = `
    <defs><marker id="l-ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#D95D39"/></marker></defs>
    ${main.map((d) => `<path class="e" d="${d}"/>`).join("")}
    <path class="loop" marker-end="url(#l-ah)" d="M${audit.cx} ${audit.t} V${top - 22} H${auction.cx} V${auction.t - 4}"/>
    <text x="${(audit.cx + auction.cx) / 2}" y="${top - 30}" text-anchor="middle">re-fit until it reads cleanly</text>
    <path class="loop" marker-end="url(#l-ah)" d="M${out.cx} ${out.b} V${bottom + 26} H${auction.cx} V${auction.b + 4}"/>
    <text x="${(out.cx + auction.cx) / 2}" y="${bottom + 46}" text-anchor="middle">edit a slide or switch its visual → the deck rebuilds</text>`;
  return [...svg.querySelectorAll("path.e")];
}

function seenLoader() {
  try {
    return window.sessionStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

export default function Landing() {
  const rootRef = useRef(null);
  const navigate = useNavigate();
  const { isSignedIn } = useAuth();
  const reduce = typeof window !== "undefined"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [loading, setLoading] = useState(() => !reduce && !seenLoader());

  // Signed-in visitors get "Open app" instead of the sign-in prompts (the markup is static).
  useEffect(() => {
    if (!isSignedIn || !rootRef.current) return;
    rootRef.current.querySelectorAll('a[href="/sign-in"]').forEach((a) => {
      a.setAttribute("href", "/app");
      if (a.classList.contains("l-btn")) a.textContent = "Open app";
      else a.textContent = "Dashboard";
    });
  }, [isSignedIn]);

  useEffect(() => {
    const root = rootRef.current;
    const page = root.querySelector(".l-L");

    // One design px in real px; the CSS does the scaling, JS only needs it
    // for distances it computes itself.
    const unit = () => page.offsetWidth / DESIGN_WIDTH;

    const lenis = reduce ? null : new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    });
    let rafTick;
    if (lenis) {
      lenis.on("scroll", ScrollTrigger.update);
      rafTick = (time) => lenis.raf(time * 1000);
      gsap.ticker.add(rafTick);
      gsap.ticker.lagSmoothing(0);
    }

    // In-page anchors scroll smoothly; data-route links go through the router.
    const onClick = (event) => {
      const link = event.target.closest("a");
      if (!link || !root.contains(link)) return;
      const href = link.getAttribute("href") || "";
      if (link.hasAttribute("data-route")) {
        event.preventDefault();
        navigate(href);
      } else if (href.startsWith("#")) {
        event.preventDefault();
        const target = href === "#top" ? 0 : root.querySelector(href);
        if (lenis) lenis.scrollTo(target, { duration: 1.4 });
        else if (target) target.scrollIntoView();
        else window.scrollTo(0, 0);
      }
    };
    root.addEventListener("click", onClick);

    // Pinned chapters are composed 900–1180 design px tall, taller than most
    // windows, so while pinned their bottom would sit below the fold. Wrap
    // each one's content and scale it to fit the window, centred, so the whole
    // scene is in frame for the entire pin.
    const PINNED = ["what", "features", "how", "layouts", "workflow"];
    // The navbar must not sit inside a transformed stage (that would turn
    // `position: fixed` into "fixed to the stage"), so lift it out first.
    // a previous run (StrictMode / hot reload) may have left its lifted copy
    root.querySelectorAll(":scope > .l-nav").forEach((n) => n.remove());
    const navNode = page.querySelector(".l-nav");
    if (navNode) root.appendChild(navNode);
    const fits = [...page.querySelectorAll(":scope > section")].map((sec) => {
      const inner = document.createElement("div");
      inner.className = "l-fit";
      // full-bleed layers (e.g. the CTA's night scene) stay on the section
      [...sec.childNodes].forEach((n) => { if (!n.hasAttribute?.("data-bleed")) inner.appendChild(n); });
      sec.appendChild(inner);
      return { sec, inner, pinned: PINNED.includes(sec.id), designH: 0 };
    });
    const fitPinned = () => {
      fits.forEach((f) => {
        f.sec.style.height = "";
        f.inner.style.height = "";
        if (!f.pinned) {
          // scrolling sections: full-bleed background, centred stage, own height
          f.inner.style.height = `${f.sec.offsetHeight}px`;
          f.inner.style.top = "0px";
          f.inner.style.transform = "translateX(-50%)";
          return;
        }
        // the stylesheet's height, or further if content (e.g. a wrapped
        // flowchart box) reaches past it, plus a little breathing room
        f.inner.style.height = `${f.sec.offsetHeight}px`;
        // Features' slide stack is meant to be cropped by the section's bottom
        // edge, so it must not count as content that needs room.
        const deck = f.sec.querySelector(".l-deck");
        if (deck) deck.style.display = "none";
        f.designH = Math.max(f.sec.offsetHeight, f.inner.scrollHeight + 24);
        if (deck) deck.style.display = "";
        const vh = window.innerHeight;
        // keep the scene clear of the fixed navbar
        const reserve = navNode ? navNode.getBoundingClientRect().bottom + 8 : 0;
        const avail = vh - reserve;
        const scale = Math.min(1, avail / f.designH);
        f.sec.style.height = `${vh}px`;
        f.inner.style.height = `${f.designH}px`;
        f.inner.style.top = `${reserve + Math.max(0, (avail - f.designH * scale) / 2)}px`;
        f.inner.style.transform = `translateX(-50%) scale(${scale})`;
      });
    };
    fitPinned();

    const ctx = gsap.context(() => {
      const heroWords = splitWords(root.querySelector(".l-h1"));
      const nav = navNode || root.querySelector(".l-nav");

      // ── loader: dots → one dot → logo + wordmark → glide into the nav ──
      const intro = gsap.timeline({ paused: true });
      intro
        .from(heroWords, { opacity: 0, y: 26, filter: "blur(10px)", duration: 1, stagger: 0.06, ease: "power3.out" })
        .from(".l-sub, .l-heroctas", { opacity: 0, y: 16, duration: 0.8, stagger: 0.1, ease: "power3.out" }, "-=.6")
        .from(".l-stage", { y: 120, opacity: 0, duration: 1.2, ease: "power3.out" }, "-=.8")
        .from(".l-fc, .l-io, .l-links", { opacity: 0, x: (i, el) => (el.style.left ? -80 : 80), duration: 1.1, stagger: 0.06, ease: "power3.out" }, "-=1")
        .from(".l-hero .l-glass", { opacity: 0, scale: 0.6, duration: 0.6, stagger: { each: 0.05, from: "random" }, ease: "back.out(2)" }, "-=.9");

      if (loading) {
        lenis?.stop();
        const loader = document.querySelector(".l-loader");
        const dots = loader.querySelectorAll(".l-ldots i");
        const lockup = loader.querySelector(".l-lockup");
        const word = lockup.querySelector("span");
        const brand = nav.querySelector(".l-brand");
        gsap.set(nav, { opacity: 0, y: -12 });
        gsap.set(dots, { x: (i) => (i - 1) * 34 });

        // Start the lockup centred and enlarged, then FLIP it onto the brand.
        const START_SCALE = 2.4;
        const lw = lockup.offsetWidth, lh = lockup.offsetHeight;
        gsap.set(lockup, { x: -(lw * START_SCALE) / 2, y: -(lh * START_SCALE) / 2, scale: START_SCALE });
        gsap.set(lockup.querySelector("svg"), { scale: 0, rotate: -90, transformOrigin: "50% 50%" });

        const tl = gsap.timeline({ delay: 0.2 });
        tl.to(dots, { y: -16, duration: 0.25, stagger: 0.08, yoyo: true, repeat: 3, ease: "sine.inOut" })
          .to(dots, { x: -(lw * START_SCALE) / 2 + 15 * START_SCALE, duration: 0.45, ease: "power3.inOut" })
          .to(dots, { scale: 0, duration: 0.2 })
          .to(lockup.querySelector("svg"), { scale: 1, rotate: 0, duration: 0.5, ease: "back.out(2)" }, "-=.2")
          .to(word, { clipPath: "inset(0 0% 0 0)", duration: 0.5, ease: "power2.out" }, "-=.25")
          .add(() => {
            // measure where the brand really is, at whatever size the page is
            const target = brand.getBoundingClientRect();
            const from = lockup.getBoundingClientRect();
            const scale = target.height / (from.height / START_SCALE);
            gsap.to(lockup, {
              x: `+=${target.left - from.left}`,
              y: `+=${target.top - from.top}`,
              scale,
              duration: 1.1,
              ease: "expo.inOut",
            });
          }, "+=.25")
          .to(nav, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "+=.85")
          .to(loader.querySelector(".l-veil"), { opacity: 0, duration: 0.7, ease: "power2.out" }, "<")
          .add(() => intro.play(), "<")
          .add(() => {
            try { window.sessionStorage.setItem(SEEN_KEY, "1"); } catch { /* private mode */ }
            lenis?.start();
            setLoading(false);
          });
      } else if (!reduce) {
        intro.play();
      }

      if (reduce) return;

      // ── hero parallax ──
      gsap.to(".l-h1", { yPercent: -60, ease: "none", scrollTrigger: { trigger: ".l-hero", start: "top top", end: "bottom top", scrub: true } });
      gsap.to(".l-fc", { y: (i) => -80 - i * 30, ease: "none", scrollTrigger: { trigger: ".l-hero", start: "top top", end: "bottom top", scrub: true } });

      // ── nav: highlight the section in view ──
      ["what", "features", "how", "layouts", "workflow"].forEach((id) => {
        const link = nav.querySelector(`a[href="#${id}"]`);
        ScrollTrigger.create({
          trigger: `#${id}`,
          start: "top 50%",
          end: "bottom 50%",
          onToggle: (self) => link?.classList.toggle("l-on", self.isActive),
        });
      });
      nav.querySelector(".l-lk.l-on")?.classList.remove("l-on");

      // ── 01 · what we do: pinned, beats light up in turn ──
      const beats = gsap.utils.toArray(".l-beat");
      gsap.timeline({
        scrollTrigger: {
          trigger: "#what", start: "top top", end: "+=220%", pin: true, scrub: 1,
          onUpdate: (self) => {
            const at = Math.min(beats.length - 1, Math.floor(self.progress * beats.length));
            beats.forEach((b, i) => b.classList.toggle("l-on", i === at));
          },
        },
      })
        // the scanned page is there from the first frame; scrolling pulls the
        // pieces out of it one by one, then they assemble into the slide
        .from(".l-chip", { x: -140, scale: 0.6, opacity: 0, stagger: 0.5, duration: 1 })
        .from(".l-out", { y: 80, scale: 0.85, opacity: 0, duration: 1.2 })
        .to(".l-chip", { x: 60, y: 140, scale: 0.7, opacity: 0, stagger: 0.2, duration: 1 }, "-=.6")
        .to(".l-paper", { x: -40, rotate: -8, opacity: 0.35, duration: 1 }, "<");

      // ── 02 · features: pinned counters, deck rises ──
      const counters = gsap.utils.toArray(".l-tk b").map((el) => {
        // Remember the real figure once: the counter rewrites the text, and a
        // remount (StrictMode, HMR) would otherwise read back "0".
        if (!el.dataset.final) el.dataset.final = el.textContent;
        const match = el.dataset.final.match(/^([\d.]+)(.*)$/);
        return { el, to: match ? parseFloat(match[1]) : 0, suffix: match ? match[2] : "" };
      });
      const proxy = { p: 0 };
      gsap.timeline({ scrollTrigger: { trigger: "#features", start: "top top", end: "+=120%", pin: true, scrub: 1 } })
        .to(proxy, {
          p: 1, ease: "none",
          onUpdate: () => counters.forEach((c) => { c.el.textContent = Math.round(c.to * proxy.p) + c.suffix; }),
        })
        .fromTo(".l-deck", { yPercent: 70 }, { yPercent: 0, ease: "none" }, 0);
      gsap.from(".l-tk", { y: 40, opacity: 0, stagger: 0.08, duration: 0.8, scrollTrigger: { trigger: ".l-cards", start: "top 85%" } });

      // ── 03 · pipeline: connectors draw left to right, boxes pop as reached ──
      const fl = root.querySelector("#how .l-fl");
      const edges = drawFlow(fl);
      edges.forEach((edge) => {
        const len = edge.getTotalLength();
        gsap.set(edge, { strokeDasharray: len, strokeDashoffset: len });
      });
      const loops = fl.querySelectorAll(".l-fledges .loop, .l-fledges text");
      const cols = gsap.utils.toArray("#how .l-fcol");
      const flow = gsap.timeline({ scrollTrigger: { trigger: "#how", start: "top top", end: "+=160%", pin: true, scrub: 1 } });
      flow.from(cols[0].children, { opacity: 0, scale: 0.85, duration: 0.4 });
      // edges are emitted column by column; group them so a fan-out draws together
      let e = 0;
      cols.slice(1).forEach((col) => {
        const fanIn = cols[cols.indexOf(col) - 1].querySelectorAll(".l-node").length * col.querySelectorAll(".l-node").length;
        flow.to(edges.slice(e, e + fanIn), { strokeDashoffset: 0, duration: 0.5, ease: "none" });
        flow.from(col.children, { opacity: 0, scale: 0.85, duration: 0.35, stagger: 0.1 }, "-=.1");
        e += fanIn;
      });
      flow.from(loops, { opacity: 0, duration: 0.5 });

      // ── 04 · layouts: the strip slides sideways while pinned ──
      const strip = root.querySelector(".l-strip");
      strip.classList.add("js");
      gsap.to(strip, {
        x: () => -(strip.scrollWidth - page.offsetWidth + 240 * unit()),
        ease: "none",
        scrollTrigger: { trigger: "#layouts", start: "top top", end: "+=150%", pin: true, scrub: 1, invalidateOnRefresh: true },
      });

      // ── 05 · workflow: the scroll itself drives 1 → 2 → 3 ──
      // Panel widths and step fades are scrubbed, not toggled, so the
      // accordion slides continuously with the wheel and rests on each step.
      const track = root.querySelector("#workflow .l-track");
      const panels = gsap.utils.toArray("#workflow .l-panel");
      const steps = panels.map((p) => p.querySelector(".l-step"));
      track.classList.add("js");
      gsap.set(panels, { flexGrow: (i) => (i === 0 ? 1 : 0) });
      gsap.set(steps, { opacity: (i) => (i === 0 ? 1 : 0), x: (i) => (i === 0 ? 0 : -30) });
      panels.forEach((p, i) => p.classList.toggle("is-active", i === 0));
      const wf = gsap.timeline({
        defaults: { ease: "power2.inOut" },
        scrollTrigger: {
          trigger: "#workflow", start: "top top", end: "+=260%", pin: true, scrub: 0.6,
          onUpdate: (self) => {
            const at = Math.round(self.progress * (panels.length - 1));
            panels.forEach((p, i) => p.classList.toggle("is-active", i === at));
          },
        },
      });
      for (let i = 0; i < panels.length - 1; i += 1) {
        const label = `s${i}`;
        wf.to({}, { duration: 0.35 }) // rest on the open step
          .addLabel(label)
          .to(steps[i], { opacity: 0, x: -30, duration: 0.35 }, label)
          .to(panels[i], { flexGrow: 0, duration: 1 }, label)
          .to(panels[i + 1], { flexGrow: 1, duration: 1 }, label)
          .to(steps[i + 1], { opacity: 1, x: 0, duration: 0.45 }, `${label}+=0.55`);
      }
      wf.to({}, { duration: 0.35 });

      // ── CTA: wall tilts up, card lifts in ──
      gsap.fromTo(".l-wall", { rotateX: 62 }, { rotateX: 38, ease: "none", scrollTrigger: { trigger: "#start", start: "top bottom", end: "bottom bottom", scrub: true } });
      gsap.from(".l-ccard", { y: 80, scale: 0.94, opacity: 0, filter: "blur(10px)", duration: 1.2, ease: "power3.out", scrollTrigger: { trigger: "#start", start: "top 60%" } });

      // ── chapter headings: words rise from a blur ──
      root.querySelectorAll("section:not(.l-hero) .l-h2").forEach((h) => {
        gsap.from(splitWords(h), { opacity: 0, y: 22, filter: "blur(8px)", duration: 0.9, stagger: 0.05, ease: "power3.out", scrollTrigger: { trigger: h, start: "top 85%" } });
      });
    }, root);

    const onResize = () => {
      fitPinned();
      drawFlow(root.querySelector("#how .l-fl"));
      ScrollTrigger.refresh();
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("load", onResize);
    ScrollTrigger.refresh();

    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("load", onResize);
      root.removeEventListener("click", onClick);
      ctx.revert();
      // undo the fit wrappers so a remount (StrictMode) starts clean
      fits.forEach(({ sec, inner }) => {
        while (inner.firstChild) sec.insertBefore(inner.firstChild, inner);
        inner.remove();
        sec.style.height = "";
      });
      // put the navbar back only if the markup doesn't already have one
      if (navNode) {
        if (page.querySelector(".l-nav")) navNode.remove();
        else page.querySelector(".l-hero")?.prepend(navNode);
      }
      if (rafTick) gsap.ticker.remove(rafTick);
      lenis?.destroy();
    };
    // The timeline is built once per mount; `loading` only seeds it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={`l-page${loading ? " l-loading" : ""}`} ref={rootRef}>
      {loading ? (
        <div className="l-loader" aria-hidden="true">
          <div className="l-veil" />
          <div className="l-ldots"><i /><i /><i /></div>
          <div className="l-lockup">
            <svg viewBox="0 0 72 72"><path d="M20 8 H34 V46 L20 62 Z" fill="#402B25" /><path d="M20 62 L34 46 H62 L56 62 Z" fill="#F47B45" /><path d="M34 46 L20 62 V46 Z" fill="#D95D39" /></svg>
            <span>learnova</span>
          </div>
        </div>
      ) : null}
      {/* Static, trusted markup ported from the design board. */}
      <div className="l-L" dangerouslySetInnerHTML={{ __html: markup }} />
    </div>
  );
}
