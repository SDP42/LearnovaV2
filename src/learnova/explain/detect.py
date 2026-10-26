"""Find a solvable problem in slide text and solve it; or turn a slide's own worked steps into an explainer."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from learnova.explain.model import Explainer, Step
from learnova.explain.solvers import SOLVERS, pretty


def _candidates(text: str) -> List[str]:
    """Whole text first (grammars, systems), then each line, each sentence, and neighbouring line pairs."""
    text = (text or "").replace("\r", "")
    lines = [l.strip(" -•\t") for l in text.split("\n") if l.strip()]
    sents = [s.strip() for l in lines for s in re.split(r"(?<=[.?!])\s+(?=[A-Z0-9])", l) if s.strip()]
    out = [text.strip()]
    out += [f"{a} ; {b}" for a, b in zip(lines, lines[1:]) if "=" in a and "=" in b]
    out += lines + sents
    seen, uniq = set(), []
    for c in out:
        if c and c not in seen and len(c) <= 4000:
            seen.add(c)
            uniq.append(c)
    return uniq


def solve_text(text: str) -> Optional[Explainer]:
    """The first solver that recognises ``text`` (one problem). None when nothing matches."""
    for cand in _candidates(text):
        for solver in SOLVERS:
            try:
                ex = solver(cand)
            except Exception:
                ex = None
            if ex and len(ex.steps) >= 3:
                return ex
    return None


def from_worked(data: Dict[str, Any]) -> Optional[Explainer]:
    """A slide's own worked example (problem + step/reason rows) as an explainer, with plain-language lead-ins."""
    rows = [r for r in (data.get("rows") or []) if str(r.get("step", "")).strip()]
    problem = str(data.get("problem", "")).strip()
    if len(rows) < 2 or not problem:
        return None
    verbs = {"expand": "Multiply out the brackets so every term stands alone.", "simplify": "Tidy the expression: combine like terms.", "factorise": "Rewrite as a product of brackets.",
             "solve": "Work out the unknown.", "substitute": "Replace the letter by its value.", "divide": "Do the same division to both sides.", "multiply": "Multiply both sides by the same number.",
             "add": "Add the same amount to both sides.", "subtract": "Subtract the same amount from both sides.", "differentiate": "Apply the rule term by term.", "integrate": "Apply the reverse rule term by term.",
             "evaluate": "Put the numbers in and calculate.", "check": "Substitute the answer back to make sure it works."}
    steps = [Step("Read the problem", [problem], "Before calculating, say in your own words what is being asked and what is already known.", "")]
    for i, r in enumerate(rows, 1):
        reason = str(r.get("reason", "")).strip()
        first = (reason or str(r["step"])).split()[0].lower().strip(":,")
        steps.append(Step(reason[:1].upper() + reason[1:] if reason else f"Step {i}", [str(r["step"])], verbs.get(first, "Follow the working line by line: each line is the one above it, changed in one small way."), ""))
    return Explainer("worked example", problem, steps, str(rows[-1]["step"]), [], "rules")


def find_and_solve(title: str, text: str, worked: Optional[Dict[str, Any]] = None) -> Optional[Explainer]:
    """Computed solution if the text holds a problem we can solve; else the slide's own worked steps; else None."""
    ex = solve_text(f"{text}")
    if ex:
        return ex
    if worked:
        return from_worked(worked)
    return None
