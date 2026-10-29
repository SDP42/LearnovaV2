from learnova.rendering.family_blocks import render_family_block
from learnova.visuals.engine import decide


def test_branching_procedure_is_a_flowchart_with_a_loop():
    d = decide("Gradient descent procedure", "First, initialise w and b. Next, compute the predictions. Then compute the gradient. "
               "Update w and b. If the cost is still decreasing, go back to step 2; otherwise stop and return w and b.")
    assert d.family == "FLOWCHART"
    kinds = [n["kind"] for n in d.data["nodes"]]
    assert kinds[0] == "start" and kinds[-1] == "end" and "decision" in kinds
    dec = next(n for n in d.data["nodes"] if n["kind"] == "decision")
    assert dec["side"] == "Yes" and dec["back"] == 2


def test_else_branch_gets_a_side_box():
    d = decide("Checking a login", "First, read the username and password. If the password matches, open the dashboard; "
               "otherwise show an error message. Finally, log the attempt.")
    dec = next(n for n in d.data["nodes"] if n["kind"] == "decision")
    assert dec["side_text"] == "Show an error message"


def test_a_conditional_fact_is_not_a_decision():
    d = decide("How a vaccine works", "A weakened germ is introduced. The immune system recognises it. White blood cells make "
               "antibodies. Memory cells are created. If the real germ arrives later, the body responds quickly.")
    assert d.family != "FLOWCHART"


def test_web_flowchart_is_svg():
    from types import SimpleNamespace as NS

    d = decide("Checking a login", "First, read the password. If it matches, open the dashboard; otherwise show an error. Finally, log it.")
    theme = NS(primary_hex="#1D4ED8", accent_hex="#F59E0B", text_hex="#111827", card_bg_hex="#FFFFFF", subtext_hex="#6B7280",
               on_primary_hex="#FFFFFF")
    html = render_family_block("FLOWCHART", d.data, theme)
    assert html and "<svg" in html and "<polygon" in html
