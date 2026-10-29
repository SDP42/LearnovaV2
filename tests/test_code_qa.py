from learnova.visuals.engine import decide


def test_ocr_code_becomes_an_editor_panel_with_notes_and_output():
    d = decide("Impor t numpy", "impor t numpy a s np x_bar = np.mean(df [ 'x' ]) y_bar = np.mean(df [ 'y' ]) "
               "beta1 = num / den 1 39343.0 36187.15 1.3 46205.0 plt.plot(epochs, costs) print(x_bar)")
    assert d.family == "ALGORITHM" and d.data["label"] == "Python code"
    lines = [l["text"] for l in d.data["lines"]]
    assert lines[0] == "import numpy as np" and "beta1 = num / den" in lines
    assert d.data["output"] and d.data["notes"][0]["text"].startswith("Load the numpy library")


def test_training_log_becomes_a_trend_chart():
    d = decide("Page 1", "Epoch 100 | Cost = 9.1 Epoch 200 | Cost = 7.5 Epoch 300 | Cost = 6.2 Epoch 400 | Cost = 5.8 Epoch 500 | Cost = 5.6")
    assert d.family == "CHART_TREND" and len(d.data["points"]) == 5


def test_questions_with_answers_become_flip_cards_not_a_flowchart():
    d = decide("Experiment 4", "What is external fragmentation? Answer: Free memory is split into small scattered blocks. "
               "Which strategy leaves the largest unused gaps? Answer: Worst fit, because it always takes the largest block.")
    assert d.family == "LIST_STRUCTURED" and d.data["flip"] and d.data["cards"][0]["heading"] == "What is external fragmentation?"
