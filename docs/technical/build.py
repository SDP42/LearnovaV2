"""Builds the technical architecture document (PDF via XeLaTeX, DOCX via the report's reference template), on the letterhead.

    /opt/anaconda3/bin/python docs/technical/build.py
"""
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "report"))
import build as report  # noqa: E402  (reuses PANDOC, PATH setup and letterhead_docx)

SRC = ["meta.yaml", "architecture.md"]
PDF, DOCX = "Learnova_Technical_Architecture.pdf", "Learnova_Technical_Architecture.docx"


def main():
    subprocess.run([report.PANDOC, *SRC, "-o", PDF, "--pdf-engine=xelatex", "--top-level-division=section"], cwd=HERE, check=True)
    subprocess.run([report.PANDOC, *SRC, "-o", DOCX, f"--reference-doc={HERE.parent / 'report' / 'reference.docx'}", "--toc",
                    "--number-sections"], cwd=HERE, check=True)
    report.letterhead_docx(HERE / DOCX)
    print("built", PDF, DOCX)


if __name__ == "__main__":
    main()
