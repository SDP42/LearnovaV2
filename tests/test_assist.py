"""LLM assist: validated, batched, and harmless without a provider."""
from learnova.ai import assist


class FakeRouter:
    available = True

    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def generate(self, prompt, system_prompt=None, **kw):
        self.calls += 1
        return self.reply


def test_no_provider_is_a_noop(monkeypatch):
    monkeypatch.setattr(assist, "llm_available", lambda: False)
    assert assist.refine_visuals([{"id": 0, "title": "t", "text": "x"}]) == {}
    assert assist.polish_takeaways([{"id": 0, "title": "t", "text": "x"}]) == {}
    assert assist.improve_slide("t", ["a"]) is None


def test_refine_validates_and_batches(monkeypatch):
    good = '[{"id":0,"family":"TIMELINE","data":{"events":[{"date":"1990","title":"A"},{"date":"2000","title":"B"},{"date":"2010","title":"C"}]}},' \
           '{"id":1,"family":"TIMELINE","data":{"events":[]}},{"id":2,"family":"NOT_A_FAMILY","data":{"x":1}}]'
    fake = FakeRouter(good)
    monkeypatch.setattr(assist, "get_router", lambda: fake)
    out = assist.refine_visuals([{"id": i, "title": "t", "text": "x"} for i in range(3)])
    assert list(out) == [0] and out[0]["family"] == "TIMELINE"
    assert fake.calls == 1  # one request for the whole batch; invalid answers dropped


def test_takeaways_and_improve(monkeypatch):
    monkeypatch.setattr(assist, "get_router", lambda: FakeRouter('[{"id":3,"takeaway":"Mitosis yields two identical daughter cells."}]'))
    assert assist.polish_takeaways([{"id": 3, "title": "Mitosis", "text": "..."}]) == {3: "Mitosis yields two identical daughter cells."}
    monkeypatch.setattr(assist, "get_router", lambda: FakeRouter('{"title":"T2","bullets":["one","two"]}'))
    assert assist.improve_slide("T", ["a"]) == {"title": "T2", "bullets": ["one", "two"]}
