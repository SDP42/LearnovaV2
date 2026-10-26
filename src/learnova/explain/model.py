"""Data model for a worked, explained solution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Step:
    title: str                                   # "Subtract 5 from both sides"
    math: List[str] = field(default_factory=list)   # lines of working; [[…]] marks what just changed
    explain: str = ""                            # beginner-level reasoning, plain sentences
    tip: str = ""                                # the rule or habit behind the step ("Do the same to both sides")
    grid: Optional[List[List[str]]] = None       # a table state (e.g. a CYK chart)
    focus: List[Tuple[int, int]] = field(default_factory=list)   # grid cells to light up

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "math": self.math, "explain": self.explain, "tip": self.tip, "grid": self.grid, "focus": [list(f) for f in self.focus]}


@dataclass
class Explainer:
    kind: str                                    # "linear equation", "Bayes' rule", …
    problem: str
    steps: List[Step]
    answer: str
    recap: List[str] = field(default_factory=list)
    source: str = "rules"                        # "rules" (exact, computed) | "llm" (written by a model)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "problem": self.problem, "answer": self.answer, "recap": self.recap, "source": self.source,
                "steps": [s.to_dict() for s in self.steps]}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Explainer":
        steps = [Step(s.get("title", ""), list(s.get("math") or []), s.get("explain", ""), s.get("tip", ""), s.get("grid"),
                      [tuple(f) for f in s.get("focus") or []]) for s in d.get("steps") or []]
        return Explainer(d.get("kind", "problem"), d.get("problem", ""), steps, d.get("answer", ""), list(d.get("recap") or []), d.get("source", "rules"))
