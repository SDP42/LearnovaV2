"""
Equations as real mathematics, not text.

Slide text writes equations in a linear form ("J(w,b) = (1/2m) Σ (h(x) - y)^2", "x_i^2", "sqrt(a+b)", "dJ/dw"). This module parses
that form into a small tree and writes it out twice:

* **OMML** (Office Math Markup Language) — the equation object Word and PowerPoint use, so the PPTX shows a native, editable
  equation with stacked fractions, raised powers and big operators;
* **MathML** — the web standard that browsers render natively, for the web deck.

The parser is tolerant: anything it does not understand stays as plain symbols, so the worst case is the original text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Union
from xml.sax.saxutils import escape

GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "eta": "η", "theta": "θ", "lambda": "λ", "mu": "μ",
         "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω", "Delta": "Δ", "Sigma": "Σ",
         "Theta": "Θ", "Lambda": "Λ", "Pi": "Π", "Omega": "Ω", "nabla": "∇", "partial": "∂", "infinity": "∞", "inf": "∞"}
FUNCS = {"log", "ln", "exp", "sin", "cos", "tan", "max", "min", "argmax", "argmin", "lim", "det", "softmax", "sigmoid", "sign", "mod", "var", "cov"}
NARY = {"Σ": "∑", "∑": "∑", "∏": "∏", "∫": "∫", "∮": "∮"}
OPS = {":=": "≔", "<=": "≤", ">=": "≥", "!=": "≠", "->": "→", "<->": "⇌", "<=>": "⇔", "=>": "⇒", "*": "·", "+-": "±", "~=": "≈"}
_TOKEN = re.compile(r"\s*(:=|<->|<=>|<=|>=|!=|->|=>|\+-|~=|\d+(?:\.\d+)?|[A-Za-z]+|[α-ωΑ-Ω∂∇∞]|[√∑Σ∏∫∮]|\S)")


@dataclass
class Node:
    kind: str                                  # mi | mn | mo | row | sup | sub | subsup | frac | sqrt | fence | nary
    text: str = ""
    kids: List["Node"] = field(default_factory=list)
    open: str = "("
    close: str = ")"


def _tok(s: str) -> List[str]:
    out, pos = [], 0
    s = s.replace("−", "-").replace("–", "-").replace("×", "×")
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m:
            break
        out.append(m.group(1))
        pos = m.end()
    return out


class _P:
    def __init__(self, toks: List[str]):
        self.t, self.i = toks, 0

    def peek(self) -> Optional[str]:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> str:
        self.i += 1
        return self.t[self.i - 1]

    def row(self, stop: Optional[str] = None) -> Node:
        items: List[Node] = []
        while self.peek() is not None and self.peek() != stop:
            if self.peek() in ")]}" and stop is None:
                items.append(Node("mo", self.take()))
                continue
            items.append(self.postfix(self.primary()))
        return Node("row", kids=_fractions(_nary(items)))

    def primary(self) -> Node:
        t = self.take()
        pairs = {"(": ")", "[": "]", "{": "}", "|": "|"}
        if t in "([{":
            inner = self.row(pairs[t])
            if self.peek() == pairs[t]:
                self.take()
            return inner if t == "{" else Node("fence", kids=[inner], open=t, close=pairs[t])
        if t in ("√",) or t.lower() == "sqrt":
            arg = self.postfix(self.primary()) if self.peek() is not None else Node("row")
            if arg.kind == "fence":
                arg = arg.kids[0]
            return Node("sqrt", kids=[arg])
        if t in NARY:
            return Node("nary", NARY[t], kids=[Node("row"), Node("row"), Node("row")])
        if re.fullmatch(r"\d+(?:\.\d+)?", t):
            return Node("mn", t)
        if t in GREEK:
            return Node("mi", GREEK[t])
        if re.fullmatch(r"[A-Za-z]+", t):
            if t in FUNCS or len(t) > 2 and t.lower() not in {"hb"}:
                return Node("mi", t, open="fn")          # upright: a function or word
            if len(t) == 2 and t[0] in "d∂" and t[1].isalpha():
                return Node("row", kids=[Node("mi", t[0], open="fn"), Node("mi", t[1])])     # dx, dJ
            return Node("row", kids=[Node("mi", c) for c in t]) if len(t) > 1 else Node("mi", t)
        if re.fullmatch(r"[α-ωΑ-Ω∂∇∞]", t):
            return Node("mi", t)
        return Node("mo", OPS.get(t, t))

    def postfix(self, base: Node) -> Node:
        while self.peek() in ("^", "_"):
            op = self.take()
            if self.peek() is None:
                break
            arg = self.primary()
            if arg.kind == "fence" and arg.open == "(":
                arg = arg.kids[0]                           # x^(n+1) → x^{n+1}
            if base.kind == "nary":
                base.kids[0 if op == "_" else 1] = arg
                continue
            if op == "^":
                base = Node("subsup", kids=[base.kids[0], base.kids[1], arg]) if base.kind == "sub" else Node("sup", kids=[base, arg])
            else:
                base = Node("subsup", kids=[base.kids[0], arg, base.kids[1]]) if base.kind == "sup" else Node("sub", kids=[base, arg])
        return base


def _nary(items: List[Node]) -> List[Node]:
    """Σ with its limits takes the next item as its body (Word's n-ary layout)."""
    out: List[Node] = []
    i = 0
    while i < len(items):
        n = items[i]
        if n.kind == "nary" and i + 1 < len(items):
            n.kids[2] = items[i + 1]
            out.append(n)
            i += 2
            continue
        out.append(n)
        i += 1
    return out


def _calls(items: List[Node]) -> List[Node]:
    """f(x), P(A|B): a name directly followed by brackets is one unit (so a fraction takes the whole call)."""
    out: List[Node] = []
    for n in items:
        if n.kind == "fence" and n.open == "(" and out and out[-1].kind == "mi":
            out[-1] = Node("row", kids=[out[-1], n])
            continue
        out.append(n)
    return out


def _fractions(items: List[Node]) -> List[Node]:
    """a/b → stacked fraction; brackets around a whole numerator or denominator are dropped, as Word does."""
    items = _calls(items)
    out: List[Node] = []
    i = 0
    while i < len(items):
        if items[i].kind == "mo" and items[i].text == "/" and out and i + 1 < len(items):
            num, den = out.pop(), items[i + 1]
            num = num.kids[0] if num.kind == "fence" and num.open == "(" else num
            den = den.kids[0] if den.kind == "fence" and den.open == "(" else den
            out.append(Node("frac", kids=[num, den]))
            i += 2
            continue
        out.append(items[i])
        i += 1
    return out


def parse(text: str) -> Node:
    return _P(_tok(text)).row()


def looks_like_equation(text: str) -> bool:
    t = (text or "").strip()
    return 0 < len(t) <= 160 and bool(re.search(r"[=≤≥≈∝]|\^|_|√|Σ|∑|∫|\b(?:sqrt|log|exp)\(", t)) and len(re.findall(r"[A-Za-z]{4,}", t)) <= 4


# ── MathML ──────────────────────────────────────────────────────────────────
def _ml(n: Node) -> str:
    k = n.kind
    if k == "mi":
        return f'<mi mathvariant="normal">{escape(n.text)}</mi>' if n.open == "fn" else f"<mi>{escape(n.text)}</mi>"
    if k in ("mn", "mo"):
        return f"<{k}>{escape(n.text)}</{k}>"
    if k == "row":
        return "<mrow>" + "".join(_ml(c) for c in n.kids) + "</mrow>"
    if k == "sup":
        return f"<msup>{_ml(n.kids[0])}{_ml(n.kids[1])}</msup>"
    if k == "sub":
        return f"<msub>{_ml(n.kids[0])}{_ml(n.kids[1])}</msub>"
    if k == "subsup":
        return f"<msubsup>{_ml(n.kids[0])}{_ml(n.kids[1])}{_ml(n.kids[2])}</msubsup>"
    if k == "frac":
        return f"<mfrac>{_ml(n.kids[0])}{_ml(n.kids[1])}</mfrac>"
    if k == "sqrt":
        return f"<msqrt>{_ml(n.kids[0])}</msqrt>"
    if k == "fence":
        return f'<mrow><mo>{escape(n.open)}</mo>{_ml(n.kids[0])}<mo>{escape(n.close)}</mo></mrow>'
    if k == "nary":
        sub, sup, body = n.kids
        op = f'<mo largeop="true">{n.text}</mo>'
        lim = (f"<munderover>{op}{_ml(sub)}{_ml(sup)}</munderover>" if sup.kids or sup.kind != "row" else
               f"<munder>{op}{_ml(sub)}</munder>" if sub.kids or sub.kind != "row" else op)
        return f"<mrow>{lim}{_ml(body)}</mrow>"
    return ""


def to_mathml(text: str, display: bool = True) -> str:
    return (f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="{"block" if display else "inline"}">'
            f"{_ml(parse(text))}</math>")


# ── OMML (Office Math) ──────────────────────────────────────────────────────
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _r(text: str, size: int, color: str, upright: bool = False) -> str:
    return (f'<m:r>{"<m:rPr><m:sty m:val=\"p\"/></m:rPr>" if upright else ""}'
            f'<a:rPr lang="en-US" sz="{size}" i="{0 if upright else 1}" dirty="0"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="Cambria Math"/></a:rPr><m:t>{escape(text)}</m:t></m:r>')


def _om(n: Node, sz: int, col: str) -> str:
    k = n.kind
    if k == "mi":
        return _r(n.text, sz, col, upright=n.open == "fn")
    if k in ("mn", "mo"):
        return _r(n.text, sz, col, upright=True)
    if k == "row":
        return "".join(_om(c, sz, col) for c in n.kids)
    e = lambda x: f"<m:e>{_om(x, sz, col)}</m:e>"       # noqa: E731
    if k == "sup":
        return f"<m:sSup>{e(n.kids[0])}<m:sup>{_om(n.kids[1], sz, col)}</m:sup></m:sSup>"
    if k == "sub":
        return f"<m:sSub>{e(n.kids[0])}<m:sub>{_om(n.kids[1], sz, col)}</m:sub></m:sSub>"
    if k == "subsup":
        return f"<m:sSubSup>{e(n.kids[0])}<m:sub>{_om(n.kids[1], sz, col)}</m:sub><m:sup>{_om(n.kids[2], sz, col)}</m:sup></m:sSubSup>"
    if k == "frac":
        return f"<m:f><m:num>{_om(n.kids[0], sz, col)}</m:num><m:den>{_om(n.kids[1], sz, col)}</m:den></m:f>"
    if k == "sqrt":
        return f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>{e(n.kids[0])}</m:rad>'
    if k == "fence":
        return f'<m:d><m:dPr><m:begChr m:val="{escape(n.open)}"/><m:endChr m:val="{escape(n.close)}"/></m:dPr>{e(n.kids[0])}</m:d>'
    if k == "nary":
        sub, sup, body = n.kids
        hide = (("" if (sub.kids or sub.kind != "row") else '<m:subHide m:val="1"/>') +
                ("" if (sup.kids or sup.kind != "row") else '<m:supHide m:val="1"/>'))
        return (f'<m:nary><m:naryPr><m:chr m:val="{n.text}"/><m:limLoc m:val="undOvr"/>{hide}</m:naryPr>'
                f"<m:sub>{_om(sub, sz, col)}</m:sub><m:sup>{_om(sup, sz, col)}</m:sup>{e(body)}</m:nary>")
    return ""


def to_omml_paragraph(text: str, size_pt: float, color_hex: str, fallback: str = "", align: str = "ctr") -> str:
    """An <a:p> holding a native PowerPoint equation (with a plain-text fallback for viewers that cannot draw Office Math)."""
    sz = int(round(size_pt * 100))
    col = color_hex.lstrip("#").upper()
    body = _om(parse(text), sz, col)
    fb = escape(fallback or text)
    return (f'<a:p xmlns:a="{_A}"><a:pPr algn="{align}"/>'
            '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
            '<mc:Choice xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" Requires="a14">'
            f'<a14:m><m:oMathPara xmlns:m="{_M}"><m:oMathParaPr><m:jc m:val="centerGroup"/></m:oMathParaPr>'
            f"<m:oMath>{body}</m:oMath></m:oMathPara></a14:m></mc:Choice>"
            f'<mc:Fallback><a:r><a:rPr lang="en-US" sz="{sz}"><a:solidFill><a:srgbClr val="{col}"/></a:solidFill>'
            f'<a:latin typeface="Cambria Math"/></a:rPr><a:t>{fb}</a:t></a:r></mc:Fallback></mc:AlternateContent>'
            f'<a:endParaRPr lang="en-US" sz="{sz}"/></a:p>')


# ── pretty text (fallback) ──────────────────────────────────────────────────
_SUP = str.maketrans("0123456789+-=()niTt", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵀᵗ")
_SUB = str.maketrans("0123456789+-=()aeiojkmnrstux", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑᵢₒⱼₖₘₙᵣₛₜᵤₓ")


def _plain(n: Node) -> str:
    k = n.kind
    if k in ("mi", "mn"):
        return n.text
    if k == "mo":
        return f" {n.text} " if n.text in "=≤≥≈≠+→⇌" else n.text
    if k == "row":
        return "".join(_plain(c) for c in n.kids)
    if k in ("sup", "sub"):
        inner = _plain(n.kids[1])
        tab = _SUP if k == "sup" else _SUB
        conv = inner.translate(tab)
        ok = all(ch not in inner for ch in set(inner) - set(tab and ("0123456789+-=()niTt" if k == "sup" else "0123456789+-=()aeiojkmnrstux")))
        return _plain(n.kids[0]) + (conv if ok else ("^" if k == "sup" else "_") + f"({inner})")
    if k == "subsup":
        return _plain(Node("sup", kids=[Node("sub", kids=n.kids[:2]), n.kids[2]]))
    if k == "frac":
        a, b = _plain(n.kids[0]), _plain(n.kids[1])
        wrap = lambda x: f"({x})" if re.search(r"[\s+\-−=]", x) else x      # noqa: E731
        return f"{wrap(a)}/{wrap(b)}"
    if k == "sqrt":
        return f"√({_plain(n.kids[0])})"
    if k == "fence":
        return f"{n.open}{_plain(n.kids[0])}{n.close}"
    if k == "nary":
        sub, sup, body = (_plain(x) for x in n.kids)
        sub, sup = sub.replace(" ", ""), sup.replace(" ", "")
        lo = sub.translate(_SUB) if sub and all(c in "0123456789+-=()aeiojkmnrstux" for c in sub) else (f"_({sub})" if sub else "")
        hi = sup.translate(_SUP) if sup and all(c in "0123456789+-=()niTt" for c in sup) else (f"^({sup})" if sup else "")
        return f"{n.text}{lo}{hi} {body}"
    return ""


def pretty(text: str) -> str:
    """Readable plain text for viewers without equation support: x^2 → x², x_i → xᵢ, Greek names → letters."""
    try:
        return re.sub(r"\s{2,}", " ", _plain(parse(text))).strip()
    except Exception:
        return text


_LATEX_SYM = {r"\times": "×", r"\cdot": "·", r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←", r"\approx": "≈", r"\leq": "≤",
              r"\le": "≤", r"\geq": "≥", r"\ge": "≥", r"\neq": "≠", r"\pm": "±", r"\rightleftharpoons": "⇌", r"\infty": "∞", r"\sum": "Σ",
              r"\Delta": "Δ", r"\degree": "°", r"\circ": "°", r"\%": "%", r"\,": " ", r"\;": " ", r"\ ": " "}


def delatex(text: str) -> str:
    """LaTeX a model slipped into plain slide text → readable text: \\text{tonnes N}_2 → tonnes N₂, \\times → ×, \\frac{a}{b} → a/b."""
    t = str(text or "")
    if "\\" not in t and "$" not in t:
        return t
    t = t.replace("$", "")
    for _ in range(3):
        t = re.sub(r"\\(?:text|mathrm|mathbf|textbf|mathit|operatorname)\{([^{}]*)\}", r"\1", t)
        t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", t)
        t = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", t)
    for k in sorted(_LATEX_SYM, key=len, reverse=True):
        t = t.replace(k, _LATEX_SYM[k])
    t = re.sub(r"\\(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|rho|sigma|tau|phi|omega)\b", lambda m: GREEK[m.group(1)], t)
    t = re.sub(r"_\{?(\d+)\}?", lambda m: m.group(1).translate(_SUB), t)
    t = re.sub(r"\^\{?(\d+)\}?", lambda m: m.group(1).translate(_SUP), t)
    t = re.sub(r"\\[A-Za-z]+", "", t).replace("{", "").replace("}", "")
    return re.sub(r"\s{2,}", " ", t).strip()


__all__ = ["delatex", "parse", "to_mathml", "to_omml_paragraph", "pretty", "looks_like_equation"]
