"""
Slide transitions and click-build entrance animations for the generated PPTX.

python-pptx has no API for either, so both are injected into the slide XML. The
CT_Slide schema order is strict::

    cSld, clrMapOvr, transition, timing, extLst

A ``<p:transition>`` appended at the end of the slide (or a ``<p:timing>`` before
it) makes PowerPoint offer to "repair" the file, so both helpers insert at the
schema-correct position. Only classic OOXML transition elements are used.

Animations are driven by *groups*: ordered lists of shape ids recorded by
``pptx_visuals`` (a card = its rectangle + text + icon, a timeline event, a table
...). The first group is already visible; each later group fades in on click.

Opt out of animation with ``LEARNOVA_PPTX_ANIM=0``. ``build_pptx`` re-parses the
saved file and strips all timing if it does not round-trip.
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence

from lxml import etree

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"

# Reveal.js name → classic PowerPoint transition element (all valid in the base schema).
_TRANSITION_XML = {
    "fade": "<p:fade/>",
    "slide": '<p:push dir="l"/>',
    "convex": '<p:cover dir="r"/>',
    "concave": '<p:pull dir="r"/>',
    "zoom": '<p:zoom dir="in"/>',
}


def animations_enabled() -> bool:
    """Click-to-build animations are ON by default; ``LEARNOVA_PPTX_ANIM=0`` forces a static deck."""
    return os.getenv("LEARNOVA_PPTX_ANIM", "1").lower() in {"1", "true", "yes", "on"}


# ── transitions ──────────────────────────────────────────────────────────────
def _insert_before_successors(sld, new_el, successors: Sequence[str]) -> None:
    """Insert ``new_el`` before the first existing successor element, else append."""
    for child in sld:
        if etree.QName(child).localname in successors:
            child.addprevious(new_el)
            return
    sld.append(new_el)


def set_transition(slide, name: Optional[str]) -> bool:
    """Write the slide transition for ``name`` (a SlidePlan.transition). 'none'/unknown → no transition."""
    sld = slide._element
    for old in sld.findall(f"{{{_P}}}transition"):
        sld.remove(old)
    inner = _TRANSITION_XML.get(str(name or "none").lower())
    if not inner:
        return False
    el = etree.fromstring(f'<p:transition xmlns:p="{_P}" spd="med">{inner}</p:transition>')
    _insert_before_successors(sld, el, ("timing", "extLst"))
    return True


# ── click builds ─────────────────────────────────────────────────────────────
def _effect(spid: int, tn: int, node: str) -> str:
    return (
        f'<p:par><p:cTn id="{tn}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold" nodeType="{node}">'
        f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        f'<p:set><p:cBhvr><p:cTn id="{tn + 1}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
        f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>'
        f'<p:to><p:strVal val="visible"/></p:to></p:set>'
        f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{tn + 2}" dur="450"/>'
        f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
        f'</p:childTnLst></p:cTn></p:par>'
    )


def _click_par(group: Sequence[int], tn: int) -> tuple[str, int]:
    """One click: every shape of ``group`` fades in together. Returns (xml, next free id)."""
    outer, inner = tn, tn + 1
    tn += 2
    effects = []
    for k, spid in enumerate(group):
        effects.append(_effect(spid, tn, "clickEffect" if k == 0 else "withEffect"))
        tn += 3
    xml = (f'<p:par><p:cTn id="{outer}" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst>'
           f'<p:par><p:cTn id="{inner}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
           f'{"".join(effects)}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>')
    return xml, tn


def merge_groups(groups: Sequence[Sequence[int]], steps: int) -> List[List[int]]:
    """Fold ``groups`` into ``steps`` consecutive chunks (a plan with fewer steps than shapes)."""
    n = len(groups)
    if steps < 1 or steps >= n:
        return [list(g) for g in groups]
    out: List[List[int]] = []
    for i in range(steps):
        lo, hi = round(i * n / steps), round((i + 1) * n / steps)
        merged = [sid for g in groups[lo:hi] for sid in g]
        if merged:
            out.append(merged)
    return out


def apply_click_builds(slide, groups: Sequence[Sequence[int]], static_first: bool = True) -> bool:
    """
    Fade each group in on successive clicks. With ``static_first`` the first group is
    simply visible on arrival (progressive reveal); otherwise every group needs a click.

    Returns True if timing was added. On any error the slide is left unchanged.
    """
    clean = [[i for i in g if isinstance(i, int) and i > 0] for g in groups]
    clean = [g for g in clean if g]
    clicks = clean[1:] if static_first else clean
    if not clicks:
        return False
    try:
        sld = slide._element
        for old in sld.findall(f"{{{_P}}}timing"):
            sld.remove(old)
        tn = 3
        pars = []
        for g in clicks:
            xml, tn = _click_par(g, tn)
            pars.append(xml)

        timing_xml = (
            f'<p:timing xmlns:p="{_P}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
            f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>{"".join(pars)}</p:childTnLst></p:cTn>'
            f'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
            f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
            f'</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'
        )
        _insert_before_successors(sld, etree.fromstring(timing_xml), ("extLst",))
        return True
    except Exception:
        return False


def strip_all_timing(prs) -> None:
    """Remove every <p:timing> — the safety net if validation fails."""
    for slide in prs.slides:
        el = slide._element
        for t in el.findall(f"{{{_P}}}timing"):
            el.remove(t)


__all__ = ["animations_enabled", "set_transition", "apply_click_builds", "merge_groups", "strip_all_timing"]
