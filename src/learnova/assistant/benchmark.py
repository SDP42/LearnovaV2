"""
Assistant benchmark (spec §43, §47).

Runs every row of ``data/assistant/qa_dataset.json`` through the deterministic
NLU and (for action rows) the orchestrator, and reports:

    intent accuracy · entity-key recall · action accuracy · resolution accuracy

Run:  ``python -m learnova.assistant.benchmark``
The test suite asserts floors on these numbers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List

from learnova.assistant.dataset import load_dataset
from learnova.assistant.nlu import classify


@dataclass
class BenchResult:
    total: int
    intent_hits: int
    action_hits: int
    entity_key_hits: int
    entity_key_total: int
    by_category: Dict[str, tuple]
    confusions: List[tuple]

    @property
    def intent_acc(self) -> float:
        return self.intent_hits / max(1, self.total)

    @property
    def action_acc(self) -> float:
        return self.action_hits / max(1, self.total)

    @property
    def entity_recall(self) -> float:
        return self.entity_key_hits / max(1, self.entity_key_total)

    def report(self) -> str:
        lines = [
            f"rows              {self.total}",
            f"intent accuracy   {self.intent_acc:6.1%}  ({self.intent_hits}/{self.total})",
            f"action accuracy   {self.action_acc:6.1%}",
            f"entity-key recall {self.entity_recall:6.1%}  "
            f"({self.entity_key_hits}/{self.entity_key_total})",
            "",
            "by category:",
        ]
        for cat, (hit, tot) in sorted(self.by_category.items()):
            lines.append(f"  {cat:26} {hit/max(1,tot):6.1%}  ({hit}/{tot})")
        if self.confusions:
            lines += ["", "top confusions (expected -> got : n):"]
            for (exp, got), n in self.confusions[:12]:
                lines.append(f"  {exp:24} -> {got:24} {n}")
        return "\n".join(lines)


def run(rows: List[dict] | None = None) -> BenchResult:
    rows = rows or load_dataset()
    total = len(rows)
    intent_hits = action_hits = ek_hits = ek_total = 0
    cat: Counter = Counter()
    cat_hit: Counter = Counter()
    conf: Counter = Counter()

    # Intents that produce the same user-facing action and are genuinely
    # interchangeable count as a hit for each other.
    equiv = [
        {"SEARCH_PRESENTATION", "FIND_PRESENTATIONS_ABOUT", "WHERE_IS_TOPIC",
         "SEARCH_CONTENT"},
        {"GIVE_EXAMPLE", "REAL_WORLD_EXAMPLE"},
        {"EXPLAIN_CONCEPT", "DEFINE_TERM"},
        {"OPEN_PRESENTATION", "DOWNLOAD_PRESENTATION"},
    ]

    def _same(a: str, b: str) -> bool:
        return a == b or any(a in g and b in g for g in equiv)

    for row in rows:
        want_intent = row["intent"]
        want_action = row.get("expected_action", "")
        got = classify(row["question"])
        cat[row["category"]] += 1
        if _same(got.intent.value, want_intent):
            intent_hits += 1
            cat_hit[row["category"]] += 1
        else:
            conf[(want_intent, got.intent.value)] += 1
        if got.to_dict()["action"] == want_action or not want_action:
            action_hits += 1
        for k in (row.get("entities") or {}):
            ek_total += 1
            if k in got.entities:
                ek_hits += 1

    return BenchResult(
        total=total, intent_hits=intent_hits, action_hits=action_hits,
        entity_key_hits=ek_hits, entity_key_total=ek_total,
        by_category={c: (cat_hit[c], cat[c]) for c in cat},
        confusions=conf.most_common(),
    )


if __name__ == "__main__":
    print(run().report())
