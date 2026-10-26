"""
Solvers that *compute* the answer and write the reasoning a beginner needs, step by step.

Every number in a step comes from the calculation itself (SymPy / exact fractions), never from a language model, so a
step can be trusted. Each solver returns ``None`` when the text is not the kind of problem it handles.
"""

from __future__ import annotations

import itertools
import math
import re
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

import sympy as sp
from sympy.parsing.sympy_parser import convert_xor, implicit_multiplication_application, parse_expr, standard_transformations

from learnova.explain.model import Explainer, Step

_TRANS = standard_transformations + (implicit_multiplication_application, convert_xor)


# ── formatting ────────────────────────────────────────────────────────────────
def _norm_text(t: str) -> str:
    return (t.replace("×", "*").replace("·", "*").replace("−", "-").replace("–", "-").replace("÷", "/").replace("²", "^2").replace("³", "^3")
             .replace("√", "sqrt").replace("π", "pi").replace(" ", " "))


def pretty(e) -> str:
    """Human-looking algebra: 3x + 5, x^2 − 4, 1/2."""
    s = sp.sstr(e, order="lex") if not isinstance(e, str) else e
    s = s.replace("**", "^").replace("sqrt(", "√(")
    s = re.sub(r"(?<=\d)\*(?=[a-zA-Z(])", "", s)
    s = re.sub(r"(?<=[a-zA-Z)])\*(?=[a-zA-Z(])", "", s)
    s = s.replace("*", "×").replace(" - ", " − ")
    s = re.sub(r"(?<![\w)])-(?=[\w(])", "−", s)
    return s


def num(v) -> str:
    """An exact number: 3, 3/4, 0.75 (when the fraction is a clean decimal)."""
    v = sp.nsimplify(v) if not isinstance(v, sp.Basic) else v
    if v.is_Integer:
        return str(int(v))
    if v.is_Rational:
        p, q = v.p, v.q
        d = sp.Rational(p, q)
        f = float(d)
        if len(str(f).split(".")[-1]) <= 3 and abs(f * 1000 - round(f * 1000)) < 1e-9:
            return f"{f:g}"
        return f"{p}/{q}"
    return pretty(v)


def mark(s: str) -> str:
    return f"[[{s}]]"


def _parse(s: str):
    return parse_expr(_norm_text(s).replace("^", "**"), transformations=_TRANS, evaluate=True)


def _sign_add(c) -> Tuple[str, str]:
    return ("add", num(-c)) if c < 0 else ("subtract", num(c))


def extract_equation(text: str) -> Optional[str]:
    """The "lhs = rhs" part of a sentence like "Solve 3x + 5 = 20 for x" (one equals sign, algebra only)."""
    t = _norm_text(text)
    if t.count("=") != 1:
        return None
    left, right = t.split("=")
    left = re.sub(r"^(?:\s*[A-Za-z]{2,}[:,]?\s+)+(?=[-+(\d]|[a-zA-Z]\s*[-+*/=^]|[a-zA-Z]$)", "", left)
    left = re.sub(r"^[^\d(a-zA-Z-+]+", "", left).strip()
    right = re.split(r"[.;,?]|\s+(?=[A-Za-z]{3,}\b)", right.strip(), 1)[0].strip()
    if not left or not right or re.search(r"[A-Za-z]{2,}", left.replace("sqrt", "").replace("pi", "")) or re.search(r"[A-Za-z]{2,}", right.replace("sqrt", "").replace("pi", "")):
        return None
    return f"{left} = {right}"


# ── linear equation ──────────────────────────────────────────────────────────
def solve_linear(text: str) -> Optional[Explainer]:
    eq = extract_equation(text)
    if eq is None:
        return None
    lhs_s, rhs_s = eq.split("=")
    try:
        L, R = _parse(lhs_s), _parse(rhs_s)
    except Exception:
        return None
    syms = sorted((L.free_symbols | R.free_symbols), key=str)
    if len(syms) != 1:
        return None
    x = syms[0]
    Le, Re = sp.expand(L), sp.expand(R)
    if sp.degree(sp.Poly(sp.expand(Le - Re), x)) != 1:
        return None
    a1, b1, a2, b2 = Le.coeff(x, 1), Le.coeff(x, 0), Re.coeff(x, 1), Re.coeff(x, 0)
    steps: List[Step] = [Step("Write down the equation", [f"{pretty(L)} = {pretty(R)}"],
                              f"We want the value of {x} that makes both sides equal. Think of the equals sign as a balanced scale: whatever we do to one side, we must do to the other so it stays balanced.",
                              f"Goal: get {x} on its own on one side.")]
    cl, cr = Le, Re
    if str(sp.expand(L)) != str(L) or str(sp.expand(R)) != str(R):
        steps.append(Step("Expand the brackets", [f"{pretty(Le)} = {pretty(Re)}"], "Multiply each term inside the brackets by the number outside, so every term stands on its own.", "Brackets first."))
    if a2 != 0:
        verb = "Subtract" if a2 > 0 else "Add"
        term = pretty(abs(a2) * x)
        cl, cr = sp.expand(cl - a2 * x), sp.expand(cr - a2 * x)
        steps.append(Step(f"{verb} {term} {'from' if a2 > 0 else 'to'} both sides", [f"{pretty(Le)} {mark('− ' + term if a2 > 0 else '+ ' + term)} = {pretty(Re)} {mark('− ' + term if a2 > 0 else '+ ' + term)}", f"{pretty(cl)} = {pretty(cr)}"],
                          f"We move every {x} term to the left so that only numbers remain on the right. Doing the same thing on both sides keeps the scale balanced.", "Collect the unknowns on one side."))
    k = cl.coeff(x, 0)
    if k != 0:
        verb, amt = _sign_add(k)
        newl, newr = sp.expand(cl - k), sp.expand(cr - k)
        steps.append(Step(f"{verb.capitalize()} {amt} {'from' if verb == 'subtract' else 'to'} both sides", [f"{pretty(cl)} {mark(('− ' + num(k)) if k > 0 else ('+ ' + num(-k)))} = {pretty(cr)} {mark(('− ' + num(k)) if k > 0 else ('+ ' + num(-k)))}", f"{pretty(newl)} = {pretty(newr)}"],
                          f"The {num(k)} on the left is in the way, so we do the opposite operation ({'subtract' if k > 0 else 'add'}) on both sides. That cancels it.", "Undo addition with subtraction, and subtraction with addition."))
        cl, cr = newl, newr
    coef = cl.coeff(x, 1)
    if coef == 0:
        ans = "no solution" if cr != 0 else "every number is a solution"
        steps.append(Step("Look at what is left", [f"0 = {pretty(cr)}"], f"All the {x} terms cancelled. Since 0 = {pretty(cr)} is {'false' if cr != 0 else 'always true'}, there is {ans}.", ""))
        return Explainer("linear equation", f"{lhs_s.strip()} = {rhs_s.strip()}", steps, ans.capitalize())
    if coef != 1:
        steps.append(Step(f"Divide both sides by {num(coef)}", [f"{pretty(cl)} = {pretty(cr)}", f"{pretty(cl)} {mark('÷ ' + num(coef))} = {pretty(cr)} {mark('÷ ' + num(coef))}", f"{x} = {num(sp.nsimplify(cr / coef))}"],
                          f"{x} is being multiplied by {num(coef)}. The opposite of multiplying is dividing, so we divide both sides by {num(coef)}.", "Undo multiplication with division."))
    sol = sp.nsimplify(cr / coef)
    steps.append(Step("Check the answer", [f"{pretty(L).replace(str(x), '(' + num(sol) + ')')} = {num(sp.nsimplify(L.subs(x, sol)))}", f"{pretty(R).replace(str(x), '(' + num(sol) + ')')} = {num(sp.nsimplify(R.subs(x, sol)))}",
                                           f"Both sides equal {num(sp.nsimplify(L.subs(x, sol)))} ✓"],
                      f"Put {x} = {num(sol)} back into the original equation. If both sides match, the answer is right.", "Always check by substituting."))
    return Explainer("linear equation", f"{lhs_s.strip()} = {rhs_s.strip()}", steps, f"{x} = {num(sol)}",
                     ["Keep the equation balanced: do the same to both sides.", "Undo each operation with its opposite.", "Check by substituting your answer back in."])


# ── quadratic ────────────────────────────────────────────────────────────────
def solve_quadratic(text: str) -> Optional[Explainer]:
    eq = extract_equation(text)
    if eq is None:
        return None
    lhs_s, rhs_s = eq.split("=")
    try:
        L, R = _parse(lhs_s), _parse(rhs_s)
    except Exception:
        return None
    syms = sorted((L.free_symbols | R.free_symbols), key=str)
    if len(syms) != 1:
        return None
    x = syms[0]
    poly = sp.Poly(sp.expand(L - R), x)
    if poly.degree() != 2:
        return None
    a, b, c = (sp.nsimplify(poly.coeff_monomial(x ** k)) for k in (2, 1, 0))
    std = sp.expand(L - R)
    steps = [Step("Write it in standard form", [f"{pretty(L)} = {pretty(R)}", f"{pretty(std)} = 0"],
                  "A quadratic equation has an x² term. First move everything to one side so the other side is 0. Then read off the numbers a, b and c from ax² + bx + c = 0.", f"Here a = {num(a)}, b = {num(b)}, c = {num(c)}.")]
    disc = b * b - 4 * a * c
    steps.append(Step("Work out the discriminant", [f"Δ = b² − 4ac", f"Δ = ({num(b)})² − 4({num(a)})({num(c)})", f"Δ = {num(disc)}"],
                      "The discriminant tells us how many real answers to expect before we spend time solving: positive means two answers, zero means one, negative means none.", ""))
    if disc < 0:
        steps.append(Step("Decide", [f"Δ = {num(disc)} < 0"], "The discriminant is negative, so the square root in the formula would be of a negative number. There are no real solutions.", ""))
        return Explainer("quadratic equation", f"{lhs_s.strip()} = {rhs_s.strip()}", steps, "No real solutions")
    r = sp.sqrt(disc)
    if disc.is_Rational and sp.sqrt(disc).is_Rational and a.is_Integer and b.is_Integer and c.is_Integer:
        f = sp.factor(std)
        steps.append(Step("Factorise", [f"{pretty(std)} = 0", f"{pretty(f)} = 0"],
                          "Because the discriminant is a perfect square, the expression splits into two brackets. Look for two numbers that multiply to a×c and add to b — they give the brackets.", "Factorising turns one hard equation into two easy ones."))
        steps.append(Step("Use the zero-product rule", [f"{pretty(f)} = 0", "A × B = 0  means  A = 0  or  B = 0"],
                          "If two things multiply to give zero, at least one of them must be zero. So set each bracket equal to zero.", ""))
    sols = sorted(sp.solve(sp.Eq(std, 0), x), key=lambda v: float(v))
    steps.append(Step("Use the quadratic formula", [f"{x} = (−b ± √Δ) / 2a", f"{x} = (−({num(b)}) ± √{num(disc)}) / (2×{num(a)})", f"{x} = ({num(-b)} ± {pretty(r)}) / {num(2 * a)}"],
                      "The formula always works, even when factorising is hard. The ± means we get one answer with + and another with −.", "x = (−b ± √(b² − 4ac)) / 2a"))
    out = []
    for sgn, sol in zip(("+", "−"), (sp.nsimplify((-b + r) / (2 * a)), sp.nsimplify((-b - r) / (2 * a)))):
        out.append(f"{x} = ({num(-b)} {sgn} {pretty(r)}) / {num(2 * a)} = {num(sol)}")
    steps.append(Step("Find both answers", out, "Calculate once with + and once with −.", ""))
    ans = " or ".join(f"{x} = {num(s)}" for s in sols)
    if any(not s.is_Rational for s in sols):
        ans += "  (≈ " + " or ≈ ".join(f"{float(s):.3f}" for s in sols) + ")"
    steps.append(Step("Check", [f"{pretty(std).replace(str(x), '(' + num(s) + ')')} = {num(sp.nsimplify(std.subs(x, s)))} ✓" for s in sols],
                      "Substitute each answer back into the equation; it should give 0.", ""))
    return Explainer("quadratic equation", f"{lhs_s.strip()} = {rhs_s.strip()}", steps, ans,
                     ["Move everything to one side so the other is 0.", "The discriminant predicts how many answers there are.", "Check each answer by substituting."])


# ── system of two linear equations ──────────────────────────────────────────
def solve_system(text: str) -> Optional[Explainer]:
    eqs = [e.strip() for e in re.split(r"[;\n]|\band\b|,(?=\s*[-+0-9a-z]+\s*[xy])", _norm_text(text)) if "=" in e]
    if len(eqs) != 2:
        return None
    try:
        x, y = sp.symbols("x y")
        rows = []
        for e in eqs:
            l, r = e.split("=")
            ex = sp.expand(_parse(l) - _parse(r))
            if ex.free_symbols - {x, y} or sp.Poly(ex, x, y).total_degree() != 1:
                return None
            rows.append((sp.nsimplify(ex.coeff(x, 1)), sp.nsimplify(ex.coeff(y, 1)), sp.nsimplify(-ex.coeff(x, 0).subs(y, 0))))
    except Exception:
        return None
    (a1, b1, c1), (a2, b2, c2) = rows
    if a1 * b2 - a2 * b1 == 0:
        return None

    def eq_s(a, b, c, mult=None):
        parts = []
        if a != 0:
            parts.append(f"{num(a) if a != 1 else ''}x" if a != -1 else "−x")
        if b != 0:
            sign = "+" if b > 0 else "−"
            parts.append(f"{sign if parts else ('−' if b < 0 else '')} {num(abs(b)) if abs(b) != 1 else ''}y".strip())
        return f"{' '.join(parts)} = {num(c)}"

    steps = [Step("Label the equations", [f"(1)  {eq_s(a1, b1, c1)}", f"(2)  {eq_s(a2, b2, c2)}"],
                  "We have two unknowns, x and y, so we need both equations. The plan: make one unknown disappear (eliminate it), solve for the other, then go back for the first.", "Elimination: add or subtract the equations to remove one letter.")]
    lcm = sp.ilcm(abs(int(b1)) or 1, abs(int(b2)) or 1) if b1.is_Integer and b2.is_Integer and b1 != 0 and b2 != 0 else None
    if lcm:
        m1, m2 = lcm // abs(int(b1)), lcm // abs(int(b2))
        A1, B1, C1, A2, B2, C2 = a1 * m1, b1 * m1, c1 * m1, a2 * m2, b2 * m2, c2 * m2
        if m1 != 1 or m2 != 1:
            steps.append(Step("Make the y-numbers match", [f"(1) × {m1}:  {eq_s(A1, B1, C1)}", f"(2) × {m2}:  {eq_s(A2, B2, C2)}"],
                              f"Multiply each equation so that y has the same number (ignoring sign) in both: {abs(int(B1))}.", "Multiply every term, including the number on the right."))
        same = (B1 > 0) == (B2 > 0)
        if same:
            dx, dc, op = A1 - A2, C1 - C2, "Subtract (2) from (1)"
        else:
            dx, dc, op = A1 + A2, C1 + C2, "Add the equations"
        steps.append(Step(f"{op} to remove y", [f"{eq_s(A1, B1, C1)}", f"{eq_s(A2, B2, C2)}", f"{'−' if same else '+'}" + "  ──────", f"{num(dx)}x = {num(dc)}"],
                          f"The y terms {'are equal, so subtracting' if same else 'are opposites, so adding'} cancels them completely. Now only x is left.", ""))
    det = a1 * b2 - a2 * b1
    xs, ys = sp.nsimplify((c1 * b2 - c2 * b1) / det), sp.nsimplify((a1 * c2 - a2 * c1) / det)
    steps.append(Step("Solve for x", [f"x = {num(xs)}"], "Divide both sides by the number in front of x.", ""))
    steps.append(Step("Find y by substitution", [f"Put x = {num(xs)} into (1):", f"{num(a1)}({num(xs)}) + {num(b1)}y = {num(c1)}", f"y = {num(ys)}"],
                      "Now that we know x, put it back into either original equation. That leaves one unknown, y.", ""))
    steps.append(Step("Check in both equations", [f"(1) {num(a1 * xs + b1 * ys)} = {num(c1)} ✓", f"(2) {num(a2 * xs + b2 * ys)} = {num(c2)} ✓"],
                      "A correct pair (x, y) must satisfy both equations.", ""))
    return Explainer("pair of linear equations", " ; ".join(eqs), steps, f"x = {num(xs)}, y = {num(ys)}",
                     ["Make one unknown disappear by adding or subtracting.", "Substitute back to find the other.", "Check in both equations."])


# ── percentages, ratios, interest ───────────────────────────────────────────
def _first_numbers(text: str, n: int) -> List[float]:
    vals = [float(v.replace(",", "")) for v in re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?", text)]
    return vals[:n]


def solve_percent(text: str) -> Optional[Explainer]:
    t = _norm_text(text)
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*\$?(\d[\d,]*(?:\.\d+)?)", t, re.I)
    if m and re.search(r"\b(what is|find|calculate|compute|how much)\b", t, re.I):
        p, base = Fraction(m.group(1)), Fraction(m.group(2).replace(",", ""))
        res = p / 100 * base
        return Explainer("percentage", text.strip(), [
            Step("Understand “percent”", [f"{m.group(1)}% = {m.group(1)}/100 = {float(p / 100):g}"], "“Percent” means “out of 100”. So 15% is 15 out of every 100, which is the decimal 0.15.", "Percent ÷ 100 = decimal."),
            Step("Turn “of” into multiplication", [f"{m.group(1)}% of {m.group(2)} = {float(p / 100):g} × {m.group(2)}"], "In maths, “of” means multiply.", ""),
            Step("Multiply", [f"{float(p / 100):g} × {m.group(2)} = {mark(f'{float(res):g}')}"], "Do the multiplication carefully.", "")],
            f"{float(res):g}", ["Percent means per hundred.", "“of” means multiply."])
    m = re.search(r"(increase|decrease|raise|reduce|discount|mark(?:ed)? up)\w*\D{0,25}?(\d+(?:\.\d+)?)\s*%.*?\$?(\d[\d,]*(?:\.\d+)?)|\$?(\d[\d,]*(?:\.\d+)?)\D{0,25}?(increase|decrease|discount)\w*.*?(\d+(?:\.\d+)?)\s*%", t, re.I)
    if m:
        g = m.groups()
        verb, p, base = (g[0], g[1], g[2]) if g[0] else (g[4], g[5], g[3])
        up = bool(re.match(r"increase|raise|mark", verb, re.I))
        p, base = Fraction(p), Fraction(base.replace(",", ""))
        change = p / 100 * base
        res = base + change if up else base - change
        return Explainer("percentage change", text.strip(), [
            Step("Find the amount of the change", [f"{float(p):g}% of {float(base):g} = {float(p / 100):g} × {float(base):g} = {mark(f'{float(change):g}')}"], f"First find {float(p):g}% of the starting amount. That is how much it {'goes up' if up else 'goes down'} by.", "Percent of the ORIGINAL amount."),
            Step(f"{'Add' if up else 'Subtract'} it", [f"{float(base):g} {'+' if up else '−'} {float(change):g} = {mark(f'{float(res):g}')}"], f"{'Increase means add' if up else 'Decrease means subtract'} the change to the original.", "")],
            f"{float(res):g}", ["Find the percent of the original.", "Then add (increase) or subtract (decrease)."])
    return None


def solve_interest(text: str) -> Optional[Explainer]:
    t = _norm_text(text)
    if not re.search(r"interest", t, re.I):
        return None
    pm = re.search(r"(?:principal|invest\w*|deposit\w*|loan\w*|borrow\w*|of)\D{0,12}\$?(\d[\d,]*(?:\.\d+)?)", t, re.I) or re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)", t)
    rm = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
    tm = re.search(r"(\d+(?:\.\d+)?)\s*(year|yr|month)", t, re.I)
    if not (pm and rm and tm):
        return None
    P, r, T = float(pm.group(1).replace(",", "")), float(rm.group(1)), float(tm.group(1)) / (12 if tm.group(2).lower().startswith("month") else 1)
    if re.search(r"compound", t, re.I):
        A = P * (1 + r / 100) ** T
        return Explainer("compound interest", text.strip(), [
            Step("Write the formula", ["A = P(1 + r)ᵗ"], "With compound interest you earn interest on the interest. P is the starting amount, r the yearly rate as a decimal, t the number of years.", "A = P(1 + r)^t"),
            Step("Convert the rate", [f"r = {r:g}% = {r / 100:g}"], "Divide the percentage by 100 to get a decimal.", ""),
            Step("Substitute", [f"A = {P:g}(1 + {r / 100:g})^{T:g}", f"A = {P:g} × {(1 + r / 100):g}^{T:g}"], "Replace the letters with the numbers from the problem.", ""),
            Step("Calculate", [f"A = {P:g} × {(1 + r / 100) ** T:.4f} = {mark(f'{A:,.2f}')}", f"Interest earned = {A:,.2f} − {P:,.2f} = {A - P:,.2f}"], "Work out the power first, then multiply.", "")],
            f"{A:,.2f}", ["Compound interest grows faster than simple interest."])
    I = P * r / 100 * T
    return Explainer("simple interest", text.strip(), [
        Step("Write the formula", ["I = P × r × t"], "Simple interest is earned only on the starting amount. P is the principal, r the yearly rate (as a decimal), t the time in years.", "I = P r t"),
        Step("Convert the rate", [f"r = {r:g}% = {r / 100:g}"], "Divide the percentage by 100.", ""),
        Step("Substitute", [f"I = {P:g} × {r / 100:g} × {T:g}"], "Replace the letters with the numbers.", ""),
        Step("Calculate", [f"I = {mark(f'{I:,.2f}')}", f"Total = {P:,.2f} + {I:,.2f} = {P + I:,.2f}"], "Multiply the three numbers. Add the interest to the principal to get the total.", "")],
        f"Interest {I:,.2f}; total {P + I:,.2f}", ["Convert percent to decimal first.", "Simple interest: I = P r t."])


# ── statistics ───────────────────────────────────────────────────────────────
def solve_stats(text: str) -> Optional[Explainer]:
    t = _norm_text(text)
    kind = re.search(r"\b(mean|average|median|mode|range|standard deviation)\b", t, re.I)
    if not kind:
        return None
    nums = [float(v) for v in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", t.split(":")[-1] if ":" in t else t)]
    if len(nums) < 3:
        return None
    k = kind.group(1).lower()
    data = nums
    ds = ", ".join(f"{v:g}" for v in data)
    if k in ("mean", "average"):
        s = sum(data)
        return Explainer("mean", text.strip(), [
            Step("List the numbers", [ds], "The mean (average) is what each value would be if everything were shared out equally.", ""),
            Step("Add them up", [" + ".join(f"{v:g}" for v in data) + f" = {mark(f'{s:g}')}"], "Add every value together to get the total.", ""),
            Step("Count the values", [f"There are {len(data)} values"], "We need to know how many numbers we added.", ""),
            Step("Divide the total by the count", [f"{s:g} ÷ {len(data)} = {mark(f'{s / len(data):.4g}')}"], "Share the total equally among all the values.", "Mean = sum ÷ count")],
            f"{s / len(data):.4g}", ["Mean = total ÷ number of values."])
    if k == "median":
        srt = sorted(data)
        n = len(srt)
        mid = n // 2
        med = srt[mid] if n % 2 else (srt[mid - 1] + srt[mid]) / 2
        return Explainer("median", text.strip(), [
            Step("Put the numbers in order", [ds, "↓", ", ".join(f"{v:g}" for v in srt)], "The median is the middle value, so the list must be sorted from smallest to largest first.", "Always sort before finding the median."),
            Step("Find the middle", [f"{n} values → the middle position is {mid + 1}" if n % 2 else f"{n} values → the middle is between positions {mid} and {mid + 1}"],
                 "With an odd number of values there is one middle value. With an even number there are two, and we take their average." , ""),
            Step("Read the median", [f"Median = {mark(f'{med:g}')}"], "That is our middle value.", "")], f"{med:g}", ["Sort first.", "Odd count: middle value. Even count: average the two middle values."])
    if k == "mode":
        from collections import Counter

        c = Counter(data)
        top = max(c.values())
        modes = sorted(v for v, n in c.items() if n == top)
        return Explainer("mode", text.strip(), [
            Step("Count how often each value appears", [", ".join(f"{v:g}: {n}×" for v, n in sorted(c.items()))], "The mode is the value that appears most often.", ""),
            Step("Pick the most frequent", [f"Mode = {mark(', '.join(f'{m:g}' for m in modes))}  (appears {top}×)"], "Choose the value with the highest count. If several tie, they are all modes.", "")], ", ".join(f"{m:g}" for m in modes), [])
    if k == "range":
        return Explainer("range", text.strip(), [
            Step("Find the largest and smallest", [f"Largest = {max(data):g}", f"Smallest = {min(data):g}"], "The range tells us how spread out the data is.", ""),
            Step("Subtract", [f"Range = {max(data):g} − {min(data):g} = {mark(f'{max(data) - min(data):g}')}"], "Largest minus smallest.", "")], f"{max(data) - min(data):g}", [])
    mean = sum(data) / len(data)
    sq = [(v - mean) ** 2 for v in data]
    var = sum(sq) / len(data)
    return Explainer("standard deviation", text.strip(), [
        Step("Find the mean", [f"({' + '.join(f'{v:g}' for v in data)}) ÷ {len(data)} = {mean:.4g}"], "Standard deviation measures how far values typically sit from the mean, so we start with the mean.", ""),
        Step("Subtract the mean and square", [f"({v:g} − {mean:.4g})² = {s:.4g}" for v, s in zip(data, sq)], "Find each value's distance from the mean, then square it so negatives do not cancel positives.", ""),
        Step("Average the squares", [f"Variance = {sum(sq):.4g} ÷ {len(data)} = {var:.4g}"], "The average of those squared distances is the variance.", ""),
        Step("Take the square root", [f"σ = √{var:.4g} = {mark(f'{math.sqrt(var):.4g}')}"], "Square root brings the units back to the same as the data.", "")], f"{math.sqrt(var):.4g}", [])


# ── probability and Bayes ───────────────────────────────────────────────────
def solve_probability(text: str) -> Optional[Explainer]:
    t = _norm_text(text)
    if not re.search(r"\bprobabilit\w*|\bchance\b|\blikely\b", t, re.I):
        return None
    groups = [(int(n), w.lower()) for n, w in re.findall(r"(\d+)\s+([a-z]+)", t) if w.lower() not in {"balls", "ball", "cards", "marbles", "of", "in", "and", "red"} or w.lower() == "red"]
    pairs = [(int(n), w.lower()) for n, w in re.findall(r"(\d+)\s+([A-Za-z]+)", t)]
    items = [(n, w) for n, w in pairs if w.lower() not in {"times", "percent", "out", "in", "of", "years", "year"}]
    if len(items) < 2:
        return None
    m = re.search(r"(?:probability|chance)[^.?]*?\b(?:of|that)\b[^.?]*?\b([a-z]+)\b[^.?]*?[?.]?$", t.strip(), re.I)
    words = [w for _, w in items]
    target = None
    for w in reversed(re.findall(r"[a-z]+", t.lower())):
        if w in words:
            target = w
            break
    if target is None:
        return None
    total = sum(n for n, _ in items)
    fav = sum(n for n, w in items if w == target)
    fr = Fraction(fav, total)
    return Explainer("probability", text.strip(), [
        Step("Count everything", [" + ".join(f"{n} {w}" for n, w in items) + f" = {mark(str(total))} in total"], "Probability compares the outcomes we want with all the outcomes that could happen. So first count all of them.", ""),
        Step("Count the outcomes we want", [f"{target}: {mark(str(fav))}"], f"We want “{target}”, so we only count those.", ""),
        Step("Write the probability", [f"P({target}) = favourable ÷ total = {fav}/{total}"], "Probability = (number of favourable outcomes) ÷ (total number of outcomes).", "P = wanted ÷ total"),
        Step("Simplify", [f"{fav}/{total} = {mark(f'{fr.numerator}/{fr.denominator}')} ≈ {float(fr):.3f} = {float(fr) * 100:.1f}%"], "Divide top and bottom by the same number until you cannot any more. A probability is always between 0 and 1.", "")],
        f"{fr.numerator}/{fr.denominator} ({float(fr) * 100:.1f}%)", ["Probability = wanted ÷ total, always between 0 and 1."])


def solve_bayes(text: str) -> Optional[Explainer]:
    t = _norm_text(text)
    vals: Dict[str, float] = {}
    for m in re.finditer(r"P\(\s*([^)|]+?)\s*(?:\|\s*([^)]+?))?\s*\)\s*=\s*(\d*\.?\d+)", t):
        key = m.group(1).strip() + (f"|{m.group(2).strip()}" if m.group(2) else "")
        vals[key] = float(m.group(3))
    q = re.search(r"P\(\s*([^)|]+?)\s*\|\s*([^)]+?)\s*\)\s*(?:=\s*\?|\?|is\b|$|\.|,)", t.split("find")[-1] if "find" in t.lower() else t)
    if len(vals) < 3:
        return None
    keys = list(vals)
    cand = [(k, v) for k, v in vals.items() if "|" in k]
    if not cand:
        return None
    # likelihood P(B|A), prior P(A), evidence P(B): the unknown is the posterior P(A|B)
    for lk, lv in cand:
        b, a = lk.split("|")
        if a in vals and b in vals and f"{a}|{b}" not in vals:
            post = lv * vals[a] / vals[b]
            lead = [
                Step("Write Bayes' rule", [f"P({a}|{b}) = P({b}|{a}) × P({a}) / P({b})"], f"We know how likely {b} is when {a} is true, and we want to turn that around: how likely is {a} once we have seen {b}? Bayes' rule does exactly that.", "Posterior = likelihood × prior ÷ evidence"),
                Step("Name each part", [f"P({b}|{a}) = {vals[lk]:g}   ← likelihood", f"P({a}) = {vals[a]:g}   ← prior (before seeing {b})", f"P({b}) = {vals[b]:g}   ← evidence (how common {b} is overall)"], "Match each number in the problem to its role in the rule.", ""),
                Step("Substitute", [f"P({a}|{b}) = ({vals[lk]:g} × {vals[a]:g}) / {vals[b]:g}"], "Replace each symbol by its number.", ""),
                Step("Multiply the top", [f"{vals[lk]:g} × {vals[a]:g} = {mark(f'{vals[lk] * vals[a]:.6g}')}"], "Do the multiplication in the numerator first.", ""),
                Step("Divide", [f"{vals[lk] * vals[a]:.6g} ÷ {vals[b]:g} = {mark(f'{post:.4g}')}"], "Then divide by the evidence.", ""),
                Step("Say what it means", [f"P({a}|{b}) ≈ {post * 100:.1f}%"], f"Once {b} is observed, the chance of {a} rises from {vals[a] * 100:.0f}% (the prior) to {post * 100:.1f}% (the posterior).", "Evidence updates belief.")]
            return Explainer("Bayes' rule", text.strip(), lead, f"P({a}|{b}) = {post:.4g}", ["Bayes' rule turns P(B|A) into P(A|B).", "Posterior = likelihood × prior ÷ evidence."])
    return None


# ── calculus (power rule) ───────────────────────────────────────────────────
def solve_derivative(text: str) -> Optional[Explainer]:
    m = re.search(r"(?:differentiate|derivative of|d/dx|find the derivative of)\s*[:\s]*\(?\s*([^?\n]+?)\)?\s*(?:with respect to x)?\s*[?.]?$", _norm_text(text).strip(), re.I)
    if not m:
        return None
    try:
        x = sp.symbols("x")
        f = _parse(m.group(1).strip().rstrip("."))
        if f.free_symbols - {x}:
            return None
        terms = sp.Add.make_args(sp.expand(f))
    except Exception:
        return None
    steps = [Step("Write the function", [f"f(x) = {pretty(f)}"], "To differentiate a sum, differentiate each term on its own and add the results.", "d/dx is linear: handle one term at a time.")]
    pieces = []
    for tm in terms:
        c, p = tm.as_coeff_exponent(x)
        if p == 0:
            steps.append(Step(f"Differentiate {pretty(tm)}", [f"d/dx ({pretty(tm)}) = 0"], "A plain number does not change as x changes, so its rate of change is 0.", "The derivative of a constant is 0."))
            pieces.append(sp.Integer(0))
        else:
            new = sp.simplify(c * p * x ** (p - 1))
            steps.append(Step(f"Differentiate {pretty(tm)}", [f"{pretty(tm)} → bring the power down and reduce it by 1", f"{num(c)}·{num(p)}·x^({num(p)} − 1) = {mark(pretty(new))}"],
                              f"The power rule: multiply by the exponent ({num(p)}), then lower the exponent by 1.", "d/dx (xⁿ) = n·xⁿ⁻¹"))
            pieces.append(new)
    res = sp.expand(sum(pieces))
    steps.append(Step("Add the pieces", [f"f′(x) = {mark(pretty(res))}"], "Put the differentiated terms back together.", ""))
    return Explainer("derivative", text.strip(), steps, f"f′(x) = {pretty(res)}", ["Power rule: n·xⁿ⁻¹.", "Constants vanish."])


def solve_integral(text: str) -> Optional[Explainer]:
    m = re.search(r"(?:integrate|integral of|∫)\s*[:\s]*\(?\s*([^?\n]+?)\)?\s*(?:dx)?\s*[?.]?$", _norm_text(text).strip(), re.I)
    if not m:
        return None
    try:
        x = sp.symbols("x")
        f = _parse(m.group(1).strip().rstrip(".").replace("dx", ""))
        if f.free_symbols - {x}:
            return None
        terms = sp.Add.make_args(sp.expand(f))
    except Exception:
        return None
    steps = [Step("Write the integral", [f"∫ {pretty(f)} dx"], "Integration is the reverse of differentiation. We integrate each term separately.", "")]
    pieces = []
    for tm in terms:
        c, p = tm.as_coeff_exponent(x)
        new = c * x ** (p + 1) / (p + 1) if p != -1 else c * sp.log(x)
        steps.append(Step(f"Integrate {pretty(tm)}", [f"{pretty(tm)} → raise the power by 1, then divide by the new power", f"{num(c)}·x^({num(p)} + 1)/({num(p)} + 1) = {mark(pretty(sp.simplify(new)))}"],
                          "Reverse power rule: add 1 to the exponent, then divide by that new exponent.", "∫ xⁿ dx = xⁿ⁺¹/(n+1) + C"))
        pieces.append(new)
    res = sp.expand(sum(pieces))
    steps.append(Step("Add the constant", [f"= {mark(pretty(res))} + C"], "Because the derivative of any constant is 0, an indefinite integral always carries “+ C”.", "Never forget + C."))
    return Explainer("integral", text.strip(), steps, f"{pretty(res)} + C", ["Reverse power rule.", "Add + C."])


# ── geometry ────────────────────────────────────────────────────────────────
def solve_geometry(text: str) -> Optional[Explainer]:
    t = _norm_text(text)
    if re.search(r"hypotenuse|right[- ]angled? triangle|pythagoras", t, re.I):
        nums = _first_numbers(t, 2)
        if len(nums) == 2:
            a, b = nums
            c = math.hypot(a, b)
            return Explainer("Pythagoras", text.strip(), [
                Step("Write the theorem", ["a² + b² = c²"], "In a right-angled triangle, the square of the longest side (the hypotenuse c) equals the sum of the squares of the other two sides.", "c is opposite the right angle."),
                Step("Substitute", [f"{a:g}² + {b:g}² = c²"], "Put in the two known sides.", ""),
                Step("Square and add", [f"{a * a:g} + {b * b:g} = {mark(f'{a * a + b * b:g}')}"], "Square each number, then add.", ""),
                Step("Take the square root", [f"c = √{a * a + b * b:g} = {mark(f'{c:.4g}')}"], "To undo the square, take the square root.", "")], f"c = {c:.4g}", [])
    m = re.search(r"circle.*?radius\D{0,8}(\d+(?:\.\d+)?)|radius\D{0,8}(\d+(?:\.\d+)?).*?circle", t, re.I)
    if m:
        r = float(m.group(1) or m.group(2))
        what = "circumference" if re.search(r"circumference|perimeter", t, re.I) else "area"
        if what == "area":
            return Explainer("area of a circle", text.strip(), [
                Step("Write the formula", ["A = πr²"], "The area of a circle is π times the radius squared.", "π ≈ 3.14159"),
                Step("Substitute", [f"A = π × {r:g}²"], "Replace r by the radius.", ""),
                Step("Square the radius", [f"A = π × {r * r:g}"], "Square first, then multiply by π.", ""),
                Step("Multiply", [f"A = {mark(f'{math.pi * r * r:.4g}')}"], "Use π ≈ 3.14159.", "")], f"{math.pi * r * r:.4g}", [])
        return Explainer("circumference", text.strip(), [
            Step("Write the formula", ["C = 2πr"], "The distance around a circle is 2 times π times the radius.", ""),
            Step("Substitute and multiply", [f"C = 2 × π × {r:g} = {mark(f'{2 * math.pi * r:.4g}')}"], "Multiply the numbers together.", "")], f"{2 * math.pi * r:.4g}", [])
    m = re.search(r"(?:rectangle|room|field|garden).*?(\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)", t, re.I)
    if m and re.search(r"\barea\b", t, re.I):
        l, w = float(m.group(1)), float(m.group(2))
        return Explainer("area of a rectangle", text.strip(), [
            Step("Write the formula", ["A = length × width"], "Area counts how many unit squares fit inside.", ""),
            Step("Multiply", [f"A = {l:g} × {w:g} = {mark(f'{l * w:g}')}"], "Multiply the two sides.", "")], f"{l * w:g}", [])
    return None


# ── speed / distance / time ─────────────────────────────────────────────────
def solve_speed(text: str) -> Optional[Explainer]:
    t = _norm_text(text)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(km|miles?|m|metres|meters)\b.*?(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|min|seconds?|s)\b", t, re.I)
    if not m or not re.search(r"\b(speed|how fast|average speed)\b", t, re.I):
        return None
    d, u, tm, tu = float(m.group(1)), m.group(2), float(m.group(3)), m.group(4)
    sp_ = d / tm
    return Explainer("speed", text.strip(), [
        Step("Write the formula", ["speed = distance ÷ time"], "Speed tells us how much distance is covered in one unit of time.", "S = D ÷ T"),
        Step("Substitute", [f"speed = {d:g} {u} ÷ {tm:g} {tu}"], "Put in the distance and the time.", ""),
        Step("Divide", [f"{d:g} ÷ {tm:g} = {mark(f'{sp_:.4g}')} {u} per {tu.rstrip('s')}"], "Divide distance by time. The unit is distance-unit per time-unit.", "")], f"{sp_:.4g} {u}/{tu.rstrip('s')}", [])


# ── CYK parsing (syntax analysis) ───────────────────────────────────────────
def solve_cyk(text: str) -> Optional[Explainer]:
    rules = re.findall(r"([A-Z][A-Za-z0-9']*)\s*(?:→|->|::=)\s*([^\n;|]+(?:\|[^\n;]+)*)", text)
    if len(rules) < 4:
        return None
    gram: Dict[Tuple[str, ...], List[str]] = {}
    for lhs, rhs in rules:
        rhs = re.split(r"\.\s|\.$|\bsentence\b|\bstring\b|\binput\b", rhs, 1, flags=re.I)[0]
        for alt in rhs.split("|"):
            sym = tuple(s.strip("'\"") if s.strip("'\"") != s else s for s in alt.split())
            if 1 <= len(sym) <= 2:
                gram.setdefault(sym, []).append(lhs)
    sm = re.search(r"(?:sentence|string|input)\s*[:\-]?\s*[\"“']?([a-z][a-z ]{3,60})[\"”']?", text, re.I)
    if not sm:
        return None
    words = sm.group(1).lower().split()
    if not (2 <= len(words) <= 7):
        return None
    n = len(words)
    chart: List[List[set]] = [[set() for _ in range(n)] for _ in range(n)]
    for i, w in enumerate(words):
        for (rhs, lhss) in gram.items():
            if len(rhs) == 1 and rhs[0].lower() == w:
                chart[i][i].update(lhss)
    if not any(chart[i][i] for i in range(n)):
        return None

    def grid(upto: int = -1) -> List[List[str]]:
        g = [[""] * n for _ in range(n)]
        for i in range(n):
            for j in range(i, n):
                g[i][j] = ", ".join(sorted(chart[i][j])) or "·"
        return g

    steps = [Step("Set up the chart", [f"Sentence: {' '.join(words)}", f"{len(gram)} grammar rules (each right-hand side has one or two symbols)"],
                  "The CYK algorithm fills a triangular table. Cell (i, j) will hold every symbol that can produce the words from position i to j. Start with the shortest pieces — single words — and build up.", "Chomsky normal form: every rule is A → B C or A → word.", grid(), [])]
    steps[0].grid = [[w for w in words], [""] * n]
    steps[0].focus = []
    steps.append(Step("Fill the diagonal: one word at a time", [f"“{words[i]}” → {', '.join(sorted(chart[i][i])) or 'nothing'}" for i in range(n)], "For each word, look for rules A → word. These are the building blocks.", "", [[", ".join(sorted(chart[i][j])) if i == j else "" for j in range(n)] for i in range(n)], [(i, i) for i in range(n)]))
    for span in range(2, n + 1):
        for i in range(0, n - span + 1):
            j = i + span - 1
            notes = []
            for k in range(i, j):
                for b in chart[i][k]:
                    for c in chart[k + 1][j]:
                        for lhs in gram.get((b, c), []):
                            chart[i][j].add(lhs)
                            notes.append(f"{lhs} → {b} {c}  (split after word {k + 1})")
            gmid = [[(", ".join(sorted(chart[a][b])) or "·") if (b - a + 1) <= span and (a + span - 1 >= b or True) and chart[a][b] else "" for b in range(n)] for a in range(n)]
            steps.append(Step(f"Words {i + 1}–{j + 1}: “{' '.join(words[i:j + 1])}”", notes or ["No rule fits any split"],
                              f"Try every way to cut these {span} words into a left part and a right part. If a rule A → B C exists where B covers the left part and C the right, then A covers the whole stretch.", "", gmid, [(i, j)]))
    top = chart[0][n - 1]
    ok = "S" in top
    steps.append(Step("Read the answer", [f"Cell (1, {n}) = {', '.join(sorted(top)) or 'empty'}", "S is there → the sentence is grammatical ✓" if ok else "S is missing → the grammar cannot generate this sentence"],
                      "If the start symbol S sits in the top cell, the whole sentence can be derived from the grammar.", "", [[(", ".join(sorted(chart[a][b])) if chart[a][b] else "") for b in range(n)] for a in range(n)], [(0, n - 1)]))
    return Explainer("CYK parsing", f"Parse “{' '.join(words)}” with the given grammar", steps, "Accepted: S derives the sentence" if ok else "Rejected: no parse", ["Fill by span length, shortest first.", "Check every split point.", "Accept if S is in the top cell."])


SOLVERS = [solve_cyk, solve_bayes, solve_system, solve_quadratic, solve_linear, solve_derivative, solve_integral, solve_interest, solve_percent, solve_stats, solve_probability, solve_geometry, solve_speed]
