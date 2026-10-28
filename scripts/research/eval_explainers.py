"""
Held-out benchmark for the step-by-step explainers (used in the research papers).

Problems here are NOT the ones in tests/test_explain.py: new numbers and new wordings. Each expected answer was
worked out by hand. Negatives are ordinary lecture sentences that must be left alone (no false "problem").

    python scripts/research/eval_explainers.py          # table + summary
    python scripts/research/eval_explainers.py --json   # machine-readable
"""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from learnova.explain import solve_text  # noqa: E402

# (problem, expected kind, substring that must appear in the answer)
POSITIVES = [
    ("Solve 5x - 7 = 18", "linear equation", "x = 5"),
    ("Find x if 4x + 9 = x + 21", "linear equation", "x = 4"),
    ("Solve 3(x + 2) = 2x + 10", "linear equation", "x = 4"),
    ("Solve 6x = 42", "linear equation", "x = 7"),
    ("Solve x^2 - 7x + 12 = 0", "quadratic equation", "x = 3 or x = 4"),
    ("Solve x^2 + x - 6 = 0", "quadratic equation", "x = -3 or x = 2"),
    ("Solve 2x^2 - 8 = 0", "quadratic equation", "x = -2 or x = 2"),
    ("x + y = 10 and x - y = 4", "pair of linear equations", "x = 7, y = 3"),
    ("3x + 2y = 16 and x + y = 6", "pair of linear equations", "x = 4, y = 2"),
    ("What is 25% of 80?", "percentage", "20"),
    ("What is 12% of 350?", "percentage", "42"),
    ("Find the mean of 2, 4, 6, 8, 10", "mean", "6"),
    ("Find the mean of 10, 20, 30, 40", "mean", "25"),
    ("Find the median of 8, 2, 6, 4, 10", "median", "6"),
    ("A box has 4 green and 6 yellow balls. What is the probability of drawing a green ball?", "probability", "2/5"),
    ("P(disease)=0.01, P(positive|disease)=0.9, P(positive)=0.05. Find P(disease|positive).", "Bayes' rule", "0.18"),
    ("Invest $2000 at 10% simple interest for 2 years", "simple interest", "2,400"),
    ("A right triangle has legs 6 and 8. Find the hypotenuse.", "Pythagoras", "10"),
    ("A train travels 240 km in 4 hours. What is its speed?", "speed", "60"),
    ("Find the derivative of x^2 + 5x", "derivative", "2x + 5"),
    ("Find the derivative of 4x^3", "derivative", "12x^2"),
    ("Grammar: S -> NP VP; NP -> Det N; VP -> V NP; Det -> a | the; N -> man | ball; V -> kicked. "
     "Sentence: the man kicked a ball", "CYK parsing", "Accepted"),
    ("Grammar: S -> NP VP; NP -> Det N; VP -> V NP; Det -> a | the; N -> man | ball; V -> kicked. "
     "Sentence: ball the kicked man a", "CYK parsing", "Rejected"),
    ("Using a bigram model on the corpus: <s> I like tea </s> <s> I like coffee </s> <s> you like tea </s>. "
     "Compute P(<s> I like tea </s>).", "bigram probability", "4/9"),
    ("Naive Bayes. Training: sport: ball goal team; politics: vote party law; sport: team win goal; "
     "politics: law vote debate. Test: goal team vote", "Naive Bayes", "sport"),
    ("Viterbi for the HMM. States: R, S; Observations: walk shop; Start: R=0.6, S=0.4; Transition: R->R=0.7, "
     "R->S=0.3, S->R=0.4, S->S=0.6; Emission: R:walk=0.1, R:shop=0.4, S:walk=0.6, S:shop=0.3",
     "Viterbi", "S → S"),
]

NEGATIVES = [
    "The Industrial Revolution began in Britain around 1760.",
    "Photosynthesis converts light into chemical energy.",
    "Syntax analysis checks whether a sentence follows the grammar of the language.",
    "A context-free grammar has terminals, non-terminals, productions and a start symbol.",
    "Word sense disambiguation picks the meaning of a word from its context.",
    "Hidden Markov Models are used for part-of-speech tagging.",
    "Morphology studies how words are built from smaller units called morphemes.",
    "Stemming removes suffixes; lemmatization returns the dictionary form.",
    "The parser builds a tree whose root is the start symbol S.",
    "Smoothing gives unseen n-grams a small non-zero probability.",
    "Students should revise the lecture notes before the quiz.",
    "In 2017 the transformer architecture replaced recurrence with attention.",
]


def run():
    rows = []
    for text, kind, ans in POSITIVES:
        t0 = time.perf_counter()
        ex = solve_text(text)
        ms = (time.perf_counter() - t0) * 1000
        got_kind = ex.kind if ex else None
        answer = (ex.answer if ex else "").replace("−", "-")
        rows.append({"problem": text, "want_kind": kind, "got_kind": got_kind, "answer": answer,
                     "detected": ex is not None, "kind_ok": got_kind is not None and kind.lower() in got_kind.lower(),
                     "correct": ex is not None and ans in answer, "steps": len(ex.steps) if ex else 0,
                     "explained": bool(ex) and all(s.title and s.explain for s in ex.steps), "ms": round(ms, 2)})
    false_pos = [t for t in NEGATIVES if solve_text(t) is not None]
    n = len(rows)
    summary = {
        "positives": n,
        "detected": sum(r["detected"] for r in rows),
        "kind_correct": sum(r["kind_ok"] for r in rows),
        "answer_correct": sum(r["correct"] for r in rows),
        "every_step_explained": sum(r["explained"] for r in rows),
        "mean_steps": round(sum(r["steps"] for r in rows) / n, 1),
        "median_ms": sorted(r["ms"] for r in rows)[n // 2],
        "negatives": len(NEGATIVES),
        "false_positives": len(false_pos),
        "false_positive_texts": false_pos,
    }
    return rows, summary


if __name__ == "__main__":
    rows, summary = run()
    if "--json" in sys.argv:
        print(json.dumps({"rows": rows, "summary": summary}, indent=1))
    else:
        for r in rows:
            mark = "ok " if r["correct"] and r["kind_ok"] else "-- "
            print(f"{mark}{r['want_kind']:<26} got={str(r['got_kind']):<26} steps={r['steps']:<3} {r['answer'][:40]}")
        print(json.dumps(summary, indent=1))
