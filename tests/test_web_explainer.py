"""The web deck embeds each solved problem as an inline interactive page; a stray </script> would dump JavaScript onto the slide."""
from html.parser import HTMLParser

from learnova.parsers.markdown_converter import from_typed_text
from learnova.pipeline.orchestrator import PipelineConfig, generate

_MD = """# Algebra

## Solving a linear equation
Solve 3x + 5 = 20. We want the value of x that makes both sides equal.

## Averages
Find the mean of 4, 8, 15, 16, 23, 42. Add them up and divide by how many there are.
"""


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def _deck():
    return generate(from_typed_text(_MD, "algebra"), PipelineConfig(enable_enhancement=False, enable_vision_ocr=False, enable_quizzes=False))


def test_no_script_source_leaks_onto_the_page():
    html = _deck().html_bytes.decode("utf-8")
    vt = _VisibleText()
    vt.feed(html)
    shown = " ".join(vt.text)
    assert "document.getElementById" not in shown and "function lv" not in shown and "addEventListener" not in shown


def test_embedded_explainer_is_escaped_once_and_unescaped_by_the_overlay():
    html = _deck().html_bytes.decode("utf-8")
    assert "lvExplain" in html
    assert "split('<\\\\/script>')" in html          # JS source: a literal backslash before the slash
    holder = html.split('type="text/plain"', 1)[1].split("</script>", 1)[0]
    assert "<\\/script>" in holder and "</script>" not in holder
