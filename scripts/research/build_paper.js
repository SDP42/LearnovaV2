/* Build the Learnova research paper as a formatted .docx from the Markdown source. */
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  PageNumber, Footer, convertInchesToTwip,
} = require("docx");

const SRC = process.argv[2];
const OUT = process.argv[3];
const md = fs.readFileSync(SRC, "utf8").replace(/\r\n/g, "\n").split("\n");

const FONT = "Georgia";
const MONO = "Consolas";
const ACCENT = "1A1A1A";
const BULLET = "•";

function runs(text, base = {}) {
  text = text.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  const out = [];
  const re = /(\*\*[^*]+?\*\*|`[^`]+`|\*(?!\*)[^*\n]+?\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(...runs(tok.slice(2, -2), { ...base, bold: true }));
    else if (tok.startsWith("`")) out.push(new TextRun({ text: tok.slice(1, -1).trim(), font: MONO, size: 19, bold: base.bold, italics: base.italics }));
    else out.push(...runs(tok.slice(1, -1), { ...base, italics: true }));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out.length ? out : [new TextRun({ text: "", font: FONT })];
}

function para(opts) {
  return new Paragraph({ spacing: { after: 120, line: 300 }, alignment: AlignmentType.JUSTIFIED, ...opts });
}

const children = [];
let i = 0;
let sawTitle = false;
let sawSection = false;

const isItem = (s) => /^([-*] |\d+\.\s)/.test(s);
function gobble() {
  let body = md[i].replace(/^([-*] |\d+\.\s+)/, "").trim();
  i++;
  while (i < md.length && md[i].trim() !== "" && !isItem(md[i]) &&
         !/^(#{1,3} |>|\||```|---+\s*$)/.test(md[i])) { body += " " + md[i].trim(); i++; }
  return body;
}

while (i < md.length) {
  let line = md[i];

  if (line.trimStart().startsWith("```")) {
    i++;
    const code = [];
    while (i < md.length && !md[i].trimStart().startsWith("```")) { code.push(md[i]); i++; }
    i++;
    children.push(new Paragraph({
      spacing: { before: 80, after: 160 },
      shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
      border: { left: { style: BorderStyle.SINGLE, size: 12, color: "C8C8C8", space: 6 } },
      children: code.flatMap((c, k) => {
        const r = [new TextRun({ text: c || " ", font: MONO, size: 18 })];
        return k < code.length - 1 ? [...r, new TextRun({ break: 1 })] : r;
      }),
    }));
    continue;
  }

  if (line.startsWith("|") && md[i + 1] && /^\|[\s:|-]+\|$/.test(md[i + 1].trim())) {
    const rows = [];
    while (i < md.length && md[i].startsWith("|")) { rows.push(md[i]); i++; }
    const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
    const header = cells(rows[0]);
    const body = rows.slice(2).map(cells);
    const ncol = header.length;
    const totalW = convertInchesToTwip(6.5);
    const colW = Math.floor(totalW / ncol);
    const mkRow = (arr, head) => new TableRow({
      tableHeader: head,
      children: arr.map((txt) => new TableCell({
        width: { size: colW, type: WidthType.DXA },
        margins: { top: 60, bottom: 60, left: 90, right: 90 },
        shading: head ? { type: ShadingType.CLEAR, fill: "E8E8E8" } : undefined,
        children: [new Paragraph({ spacing: { after: 0, line: 260 }, children: runs(txt, head ? { bold: true } : {}) })],
      })),
    });
    children.push(new Table({
      width: { size: totalW, type: WidthType.DXA },
      columnWidths: Array(ncol).fill(colW),
      rows: [mkRow(header, true), ...body.map((b) => mkRow(b, false))],
    }));
    children.push(new Paragraph({ spacing: { after: 140 }, children: [] }));
    continue;
  }

  if (line.startsWith("# ")) {
    const t = line.slice(2).trim();
    if (!sawTitle) {
      sawTitle = true;
      children.push(new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 240, after: 220 },
        children: [new TextRun({ text: t, bold: true, size: 34, font: FONT, color: ACCENT })],
      }));
    } else {
      sawSection = true;
      children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 340, after: 140 }, children: runs(t) }));
    }
    i++; continue;
  }
  if (line.startsWith("## ")) {
    sawSection = true;
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 130 }, children: runs(line.slice(3).trim()) }));
    i++; continue;
  }
  if (line.startsWith("### ")) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 110 }, children: runs(line.slice(4).trim()) }));
    i++; continue;
  }

  if (/^---+\s*$/.test(line.trim())) {
    children.push(new Paragraph({ spacing: { before: 40, after: 40 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC" } }, children: [] }));
    i++; continue;
  }

  if (line.startsWith("> ")) {
    const q = [];
    while (i < md.length && md[i].startsWith(">")) { q.push(md[i].replace(/^>\s?/, "")); i++; }
    children.push(new Paragraph({
      spacing: { before: 100, after: 150 }, indent: { left: 360 },
      border: { left: { style: BorderStyle.SINGLE, size: 18, color: "999999", space: 10 } },
      children: runs(q.join(" "), { italics: true }),
    }));
    continue;
  }

  if (/^[-*] /.test(line)) {
    while (i < md.length && /^[-*] /.test(md[i])) {
      children.push(para({
        alignment: AlignmentType.LEFT, spacing: { after: 70, line: 290 },
        indent: { left: 360, hanging: 260 },
        children: [new TextRun({ text: BULLET + "  ", font: FONT }), ...runs(gobble())],
      }));
    }
    continue;
  }
  if (/^\d+\.\s/.test(line)) {
    let n = 1;
    while (i < md.length && /^\d+\.\s/.test(md[i])) {
      children.push(para({
        alignment: AlignmentType.LEFT, spacing: { after: 70, line: 290 },
        indent: { left: 380, hanging: 300 },
        children: [new TextRun({ text: n + ".  ", font: FONT }), ...runs(gobble())],
      }));
      n++;
    }
    continue;
  }

  if (line.trim() === "") { i++; continue; }

  if (!sawSection && /^\*.*\*$/.test(line.trim())) {
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 90 }, children: runs(line.trim()) }));
    i++; continue;
  }

  const buf = [line];
  i++;
  while (i < md.length && md[i].trim() !== "" && !/^(#{1,3} |[-*] |\d+\.\s|>|\||```|---+\s*$)/.test(md[i])) { buf.push(md[i]); i++; }
  children.push(para({ children: runs(buf.join(" ")) }));
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 26, bold: true, color: ACCENT } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 23, bold: true, color: "333333" } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: convertInchesToTwip(8.5), height: convertInchesToTwip(11) },
        margin: { top: convertInchesToTwip(1), bottom: convertInchesToTwip(1), left: convertInchesToTwip(1), right: convertInchesToTwip(1) },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: ["Learnova research track   ", PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length, "bytes"); });
