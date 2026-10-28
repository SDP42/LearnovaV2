from lxml import etree

from learnova.visuals.engine import decide
from learnova.visuals.mathfmt import pretty, to_mathml, to_omml_paragraph


def test_equation_becomes_fraction_power_and_sum():
    ml = to_mathml("J(w,b) = (1/2m) Σ_(i=1)^m (h(x_i) - y_i)^2")
    assert "<mfrac>" in ml and "<msup>" in ml and "<munderover>" in ml
    xml = to_omml_paragraph("x = (-b + sqrt(b^2 - 4ac))/(2a)", 24, "#111111")
    root = etree.fromstring(xml)
    assert root.xpath("//*[local-name()='f']") and root.xpath("//*[local-name()='rad']")


def test_plain_fallback_reads_like_maths():
    assert pretty("y = beta_0 + beta_1 x") == "y = β₀ + β₁x"
    assert pretty("dJ/dw = w^2") == "dJ/dw = w²"


def test_pseudocode_is_one_indented_algorithm():
    d = decide("Gradient descent algorithm", "- Initialize w\n- repeat until convergence\n- for each example\n- w := w - alpha g\n"
                                             "- end for\n- until cost stops falling\n- return w")
    assert d.family == "ALGORITHM"
    assert [x["indent"] for x in d.data["lines"]] == [0, 0, 1, 2, 1, 0, 0]


def test_equation_run_keeps_only_equations():
    d = decide("Cost", "- J = (1/2m) Σ (h - y)^2\n- dJ/dw = (1/m) Σ (h - y) x\n- dJ/db = (1/m) Σ (h - y)\n- J = (1/2m) Σ (h - y)^2")
    assert d.family == "ALGORITHM" and len(d.data["lines"]) == 3
