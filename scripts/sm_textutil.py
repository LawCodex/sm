"""Turn text extracted from PDFs (Italian legislation) into Markdown paragraphs/headings."""
import re

STRUCT = [
    ("parte", r"PARTE|Parte"),
    ("libro", r"LIBRO|Libro"),
    ("titolo", r"TITOLO|Titolo"),
    ("capo", r"CAPO|Capo|CAPITOLO|Capitolo"),
    ("sezione", r"SEZIONE|Sezione"),
]
NUM = r"(?:[IVXLCDM]+|\d+|[A-Z]|PRIMO|PRIMA|SECONDO|SECONDA|TERZO|TERZA|UNICO|UNICA|PRELIMINARE|I\s?BIS)\b"
STRUCT_RE = [(k, re.compile(r"^(?:%s)\s+%s.{0,150}$" % (p, NUM))) for k, p in STRUCT]
ART_RE = re.compile(r"^(?:Art\.|ART\.|Articolo|ARTICOLO)\s*\d+[\s\-]*(?:[a-z]{0,10})?\.?(?:\s*[-–]\s*.{0,150})?$|"
                    r"^(?:Articolo|ARTICOLO|Art\.)\s+(?:unico|UNICO)\.?$")
TOC_RE = re.compile(r"\.{6,}\s*\d+\s*$")
PAGENUM_RE = re.compile(r"^\s*(?:-\s*)?\d{1,4}(?:\s*-)?\s*$|^\s*(?:pag\.|Pag\.|pagina)\s*\d+(?:\s*(?:di|/)\s*\d+)?\s*$")
LIST_RE = re.compile(r"^(?:[a-z]{1,3}\)|\d+[\.\)]|[-–•▪·]\s|\([a-z0-9]{1,3}\))")
END_RE = re.compile(r"[.;:!?»\"”)]\s*$")


def clean_lines(text):
    lines = []
    for ln in text.replace("\r", "\n").split("\n"):
        ln = ln.replace("\xa0", " ").replace("\t", " ")
        ln = re.sub(r"[ ]{2,}", " ", ln).strip()
        if TOC_RE.search(ln) or re.fullmatch(r"\d", ln):
            continue
        lines.append(ln)
    return lines


def pages_to_lines(pages):
    out = []
    for p in pages:
        ls = clean_lines(p)
        # drop page numbers at the top/bottom of the page
        while ls and (not ls[0] or PAGENUM_RE.match(ls[0])):
            ls.pop(0)
        while ls and (not ls[-1] or PAGENUM_RE.match(ls[-1])):
            ls.pop()
        out += ls + [""]
    return out


def classify(ln):
    if len(ln) <= 160:
        if ART_RE.match(ln):
            return "art"
        for k, rx in STRUCT_RE:
            if rx.match(ln):
                return k
    return None


def to_markdown(pages):
    lines = pages_to_lines(pages)
    nonempty = [len(l) for l in lines if l]
    if not nonempty:
        return ""
    width = sorted(nonempty)[int(len(nonempty) * 0.9)]
    kinds_present = []
    for l in lines:
        k = classify(l)
        if k and k != "art" and k not in kinds_present:
            kinds_present.append(k)
    order = [k for k, _ in STRUCT if k in kinds_present]
    level = {k: min(6, 2 + i) for i, k in enumerate(order)}
    art_level = min(6, 2 + len(order))
    blocks = []
    cur = []

    def flush():
        if cur:
            t = " ".join(cur)
            t = re.sub(r"\s{2,}", " ", t).strip()
            t = re.sub(r"^(\d+)\.(\s)", r"\1\\.\2", t)
            t = re.sub(r"^([#>+*])", r"\\\1", t)
            t = re.sub(r"^-(\s)", r"\\-\1", t)
            if t:
                blocks.append(t)
            cur.clear()

    prev = ""
    pending = None
    for ln in lines:
        if not ln:
            if not pending:
                flush()
                prev = ""
            continue
        if re.fullmatch(r"\d{1,3}\.|[a-z]\)", ln):
            # comma number alone on its line: attach it to the following text
            flush()
            pending = ln
            continue
        if pending:
            ln = pending + " " + ln
            pending = None
            flush()
        k = classify(ln)
        if k:
            flush()
            lvl = art_level if k == "art" else level.get(k, 2)
            blocks.append("#" * lvl + " " + ln)
            prev = ""
            continue
        if cur:
            if END_RE.search(prev) and (ln[:1].isupper() or LIST_RE.match(ln) or ln[:1] in "«\"“("):
                flush()
            elif LIST_RE.match(ln) and len(prev) < width * 0.85:
                flush()
            elif len(prev) < width * 0.6 and ln[:1].isupper() and END_RE.search(prev):
                flush()
        cur.append(ln)
        prev = ln
    flush()
    return "\n\n".join(blocks)
