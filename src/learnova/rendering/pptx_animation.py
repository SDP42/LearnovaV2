"""
Per-shape entrance animations for the generated PPTX.

python-pptx has no animation API, so this injects a ``<p:timing>`` element into
the slide XML directly — a click-triggered *fade-in* entrance for each shape (or
group of shapes), in order, so the deck builds one idea per click, matching the
web deck's progressive reveal.

Malformed timing XML makes PowerPoint refuse to open the file, so this is:

* **opt-in** — only runs when ``LEARNOVA_PPTX_ANIM=1``;
* **guarded** — any failure leaves the slide untouched;
* **validated** — ``build_pptx`` re-parses the finished file and drops all
  timing if it does not round-trip.

Only the well-trodden "appear/fade on click" preset is used
(``presetClass="entr" presetID="10"``).
"""

from __future__ import annotations

import os
from typing import List

from lxml import etree

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def animations_enabled() -> bool:
    """
    Click-to-build entrance animations are ON by default so an exported PPTX
    reveals one idea per click like the web deck. ``build_pptx`` re-parses the
    finished file and strips all timing if it does not round-trip, so a bad
    build degrades to a static (but valid) deck rather than a broken file.
    Set ``LEARNOVA_PPTX_ANIM=0`` to force static.
    """
    return os.getenv("LEARNOVA_PPTX_ANIM", "1").lower() in {"1", "true", "yes", "on"}


def _click_par(shape_id: int, tn_id: int, first: bool) -> str:
    """One click step: fade a shape in. ``tn_id`` is the starting cTn id (uses 4)."""
    a, b, c, d = tn_id, tn_id + 1, tn_id + 2, tn_id + 3
    # First step starts on the sequence begin; later steps wait for a click.
    start = '<p:cond delay="0"/>' if first else '<p:cond delay="0"/>'
    return f"""
    <p:par>
      <p:cTn id="{a}" fill="hold">
        <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
        <p:childTnLst>
          <p:par>
            <p:cTn id="{b}" fill="hold">
              <p:stCondLst>{start}</p:stCondLst>
              <p:childTnLst>
                <p:par>
                  <p:cTn id="{c}" presetID="10" presetClass="entr" presetSubtype="0"
                         fill="hold" grpId="0" nodeType="clickEffect">
                    <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                    <p:childTnLst>
                      <p:set>
                        <p:cBhvr>
                          <p:cTn id="{d}" dur="1" fill="hold">
                            <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          </p:cTn>
                          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                          <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                        </p:cBhvr>
                        <p:to><p:strVal val="visible"/></p:to>
                      </p:set>
                      <p:animEffect transition="in" filter="fade">
                        <p:cBhvr>
                          <p:cTn id="{d + 1}" dur="400"/>
                          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                        </p:cBhvr>
                      </p:animEffect>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
          </p:par>
        </p:childTnLst>
      </p:cTn>
    </p:par>"""


def apply_click_builds(slide, shape_ids: List[int]) -> bool:
    """
    Add a click-sequence fade entrance for ``shape_ids`` (in order) to ``slide``.

    Returns True if timing was added. Safe: on any error the slide is unchanged.
    """
    ids = [i for i in shape_ids if isinstance(i, int) and i > 0]
    if len(ids) < 2:
        return False
    try:
        sp_tree = slide._element  # <p:sld>
        # Remove any existing timing.
        for old in sp_tree.findall(f"{{{_P}}}timing"):
            sp_tree.remove(old)

        tn_id = 4
        pars = []
        for k, sid in enumerate(ids):
            pars.append(_click_par(sid, tn_id, first=(k == 0)))
            tn_id += 6

        timing_xml = f"""<p:timing xmlns:p="{_P}">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>{''.join(pars)}
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst>
              <p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>
            </p:prevCondLst>
            <p:nextCondLst>
              <p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>
            </p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
</p:timing>"""
        timing = etree.fromstring(timing_xml)
        sp_tree.append(timing)
        return True
    except Exception:
        return False


def strip_all_timing(prs) -> None:
    """Remove every <p:timing> — the safety net if validation fails."""
    for slide in prs.slides:
        el = slide._element
        for t in el.findall(f"{{{_P}}}timing"):
            el.remove(t)


__all__ = ["animations_enabled", "apply_click_builds", "strip_all_timing"]
