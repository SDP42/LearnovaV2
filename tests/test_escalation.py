from learnova.ai import escalation as esc


def test_titles_that_state_a_point_stay_offline():
    assert esc.title_is_weak("Linear Regression")
    assert esc.title_is_weak("Advantages (2/3)")
    assert not esc.title_is_weak("Gradient descent minimises the cost by stepping against the gradient")


def test_ocr_noise_escalates_but_clean_text_does_not():
    assert esc.ocr_is_weak("1 M=0 1 ee) M=1 t t Q 0 0 fe)")
    assert not esc.ocr_is_weak("The green curve is the true function which is not a polynomial")


def test_modes(monkeypatch):
    monkeypatch.setenv("LEARNOVA_AI_MODE", "auto")
    assert esc.should_escalate("x", True) and not esc.should_escalate("x", False)
    monkeypatch.setenv("LEARNOVA_AI_MODE", "always")
    assert esc.should_escalate("x", False)
    monkeypatch.setenv("LEARNOVA_AI_MODE", "off")
    assert not esc.should_escalate("x", True)


def test_mechanism_slides_need_a_drawing_generic_ones_do_not():
    assert esc.diagram_needed("Steps in the plant", "First the gases are compressed, then passed over a catalyst, finally cooled.")
    assert not esc.diagram_needed("Why it matters", "Fertiliser feeds half of the world population and supports farming in many countries.")


def test_lab_needs_model_only_without_structure():
    assert esc.offline_lab_ok([{"head": "a", "body": "x"}] * 3, "process")
    assert not esc.offline_lab_ok([{"head": "a", "body": ""}] * 2, "process")
