"""Builds the project report (PDF via XeLaTeX, DOCX via the reference template), both on the department letterhead.

    /opt/anaconda3/bin/python docs/report/build.py      # needs pandoc, xelatex and docs/report/letterhead.jpeg
"""
import pathlib
import subprocess

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

HERE = pathlib.Path(__file__).resolve().parent
SRC = ["meta.yaml", "ch1.md", "ch2.md", "ch3.md"]
PDF, DOCX = "Learnova_Project_Report.pdf", "Learnova_Project_Report.docx"


def page_field(par):
    r = par.add_run()
    r.font.name, r.font.size = "Times New Roman", Pt(11)
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), kind)
            r._element.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = txt
            r._element.append(it)


def letterhead_docx(path):
    d = Document(path)
    for sec in d.sections:
        sec.is_linked_to_previous = False
        sec.different_first_page_header_footer = False
        hdr = sec.header
        for p in list(hdr.paragraphs):
            p._element.getparent().remove(p._element)
        hp = hdr.add_paragraph()
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        hp.paragraph_format.space_after = Pt(0)
        hp.add_run().add_picture(str(HERE / "letterhead.jpeg"), width=Inches(6.27))
        dp = hdr.add_paragraph()
        dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        dp.paragraph_format.space_after = Pt(6)
        r = dp.add_run("Department of Artificial Intelligence (AI) and Data Science")
        r.bold, r.font.name, r.font.size = True, "Times New Roman", Pt(12)
        sec.header_distance = Inches(0.35)
        sec.top_margin = Inches(1.65)
        ftr = sec.footer
        fp = ftr.paragraphs[0] if ftr.paragraphs else ftr.add_paragraph()
        for r in list(fp.runs):
            r._element.getparent().remove(r._element)
        fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        page_field(fp)
    d.save(path)


def main():
    subprocess.run(["pandoc", *SRC, "-o", PDF, "--pdf-engine=xelatex", "--top-level-division=section"], cwd=HERE, check=True)
    subprocess.run(["pandoc", *SRC, "-o", DOCX, "--reference-doc=reference.docx", "--toc", "--number-sections"], cwd=HERE, check=True)
    letterhead_docx(HERE / DOCX)
    print("built", PDF, DOCX)


if __name__ == "__main__":
    main()
