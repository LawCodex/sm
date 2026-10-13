#!/usr/bin/env python3
"""Convert the San Marino documents cached by sm_fetch.py into Markdown.

PDF text is extracted with pypdf; PDFs without a text layer (scanned) are OCRed with
pdftoppm + tesseract (Italian model, tessdata in _raw/sm/tessdata or $TESSDATA_DIR).
"""
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from collections import Counter

from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sm_textutil  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RAW = os.path.abspath(os.environ.get("SM_RAW", os.path.join(REPO, "..", "_raw", "sm")))
RETRIEVED = os.environ.get("SM_RETRIEVED", datetime.date.today().isoformat())
BASE = "https://www.consigliograndeegenerale.sm"
OCR = os.environ.get("SM_OCR", "1") == "1"

KIND_DIR = [
    (r"revisione\s+costitu", "leggi-costituzionali", "constitutional_act"),
    (r"legge\s+costituzionale", "leggi-costituzionali", "constitutional_act"),
    (r"legge\s+qualificata", "leggi-qualificate", "qualified_act"),
    (r"decreto\s*[-–]?\s*legg", "decreti-legge", "decree_law"),
    (r"decreto\s*[-–]?\s*del[ae]g", "decreti-delegati", "delegated_decree"),
    (r"regolamento", "regolamenti", "regulation"),
    (r"statuto", "statuti", "statute"),
    (r"legge", "leggi", "act"),
]


def slugify(s, maxlen=80):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen].rstrip("-") or "testo"


def pdf_pages(data):
    """Text of each page: poppler's pdftotext when available (better word spacing), else pypdf."""
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-enc", "UTF-8", "-", "-"], input=data, capture_output=True)
        if r.returncode == 0:
            pages = r.stdout.decode("utf-8", "replace").split("\f")
            if pages and not pages[-1].strip():
                pages.pop()
            return pages
    try:
        r = PdfReader(io.BytesIO(data))
        return [p.extract_text() or "" for p in r.pages]
    except Exception as e:  # noqa: BLE001
        print("PDF error", e, file=sys.stderr)
        return None


def ocr(data, key):
    cache = os.path.join(RAW, "ocr", key + ".json")
    if os.path.exists(cache):
        return json.load(open(cache))
    if not OCR:
        return None
    tess = os.environ.get("TESSDATA_DIR", os.path.join(RAW, "tessdata"))
    work = os.path.join(RAW, "ocr", key)
    os.makedirs(work, exist_ok=True)
    pdf = os.path.join(work, "in.pdf")
    open(pdf, "wb").write(data)
    try:
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", pdf, os.path.join(work, "p")], check=True,
                       capture_output=True, timeout=1800)
    except Exception as e:  # noqa: BLE001
        print("pdftoppm failed", key, e, file=sys.stderr)
        shutil.rmtree(work)
        return None
    pages = []
    imgs = sorted((n for n in os.listdir(work) if n.endswith(".png")), key=lambda n: int(re.sub(r"\D", "", n) or 0))
    for img in imgs:
        r = subprocess.run(["tesseract", "--tessdata-dir", tess, os.path.join(work, img), "-", "-l", "ita"],
                           capture_output=True, text=True)
        pages.append(r.stdout)
    shutil.rmtree(work)
    json.dump(pages, open(cache, "w"))
    return pages


def doc_text(path, key, prefer_senza_note=True):
    """Return (pages, ocr_used, inner_name) for a cached download (pdf, zip of pdf, doc)."""
    data = open(path, "rb").read()
    hdr = open(path + ".hdr").read() if os.path.exists(path + ".hdr") else ""
    inner = None
    if data[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(data))
        names = [n for n in z.namelist() if not n.endswith("/")]
        pdfs = [n for n in names if n.lower().endswith(".pdf")]
        if pdfs:
            pick = None
            if prefer_senza_note:
                pick = next((n for n in pdfs if "senza note" in n.lower()), None)
            pick = pick or sorted(pdfs, key=len)[0]
            data, inner = z.read(pick), pick
        elif names:
            data, inner = z.read(names[0]), names[0]
    if data[:4] == b"%PDF":
        pages = pdf_pages(data)
        if pages is None:
            return None, False, inner
        if sum(len(p.strip()) for p in pages) < 40 * max(1, len(pages)):
            o = ocr(data, key)
            if o:
                return o, True, inner
        return pages, False, inner
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" or (inner or hdr).lower().endswith((".doc", ".rtf", '.doc"')):
        # legacy Word document: convert with macOS textutil if available
        tmp = os.path.join(RAW, "tmp_" + key + ".doc")
        open(tmp, "wb").write(data)
        try:
            r = subprocess.run(["textutil", "-convert", "txt", "-stdout", tmp], capture_output=True, text=True)
            return [r.stdout], False, inner
        except FileNotFoundError:
            return None, False, inner
        finally:
            os.remove(tmp)
    return None, False, inner


def front(meta):
    fm = ["---"]
    for k, v in meta.items():
        if isinstance(v, bool):
            fm.append(f"{k}: {'true' if v else 'false'}")
        elif k in ("type", "jurisdiction", "language", "status", "date", "retrieved", "last_amended"):
            fm.append(f"{k}: {v}")
        else:
            fm.append(f"{k}: " + json.dumps(v, ensure_ascii=False))
    fm.append("---")
    return "\n".join(fm)


MONTHS = {m: i + 1 for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
                                          "agosto", "settembre", "ottobre", "novembre", "dicembre"])}


def it_date(s):
    m = re.search(r"(\d{1,2})(?:°)?\s+([a-zA-Z]+)\s+(\d{4})", s or "")
    if m and m.group(2).lower() in MONTHS:
        try:
            return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


MONTH_NAMES = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
               "ottobre", "novembre", "dicembre"]


def make_title(raw, kind, number, date, body):
    """Archive titles of older acts are often only a (truncated) subject: rebuild
    "<Tipo> <d> <mese> <yyyy> n.<N> - <oggetto>" from the record and, if needed, the document."""
    raw = raw.strip()
    if re.match(r"(?i)(legge|decreto|regolamento|statuto)\b.*\bn\.?\s*\d+", raw) and len(raw) > 30:
        return raw
    k = re.sub(r"(?i)\s*ordinaria|\s*orginaria", "", kind or "").strip() or "Atto"
    k = k[:1].upper() + k[1:]
    head = k
    if date:
        y, m, d = date.split("-")
        head += f" {int(d)} {MONTH_NAMES[int(m) - 1]} {y}"
    if number and number != "0":
        head += f" n.{number}"
    subj = re.sub(r"(?i)^(legge|decreto(\s*-\s*legge)?|regolamento)\s*", "", raw).strip(" -–")
    fragment = (len(subj) < 15 or re.match(r"(?i)^(\d|n\.?\s*\d|" + "|".join(MONTH_NAMES) + r")\b", subj)
                or subj[:1].islower() and len(subj) < 40)
    if fragment and body:
        for blk in body.split("\n\n")[:8]:
            t = blk.strip().lstrip("#").strip()
            if (20 <= len(t) <= 400 and not re.match(r"(?i)(legge|decreto|regolamento|n\.\s*\d|noi capitani|il consiglio|\*)", t)):
                subj = t
                break
    subj = re.split(r"\s+(?:Noi Capitani Reggenti|Il Consiglio Grande e Generale)", subj)[0].strip()
    subj = subj[:1].upper() + subj[1:] if subj else ""
    return f"{head} - {subj}" if subj else head


def main():
    stats, problems = Counter(), []
    # ---- testi coordinati
    out = os.path.join(REPO, "testi-coordinati")
    if os.path.isdir(out):
        shutil.rmtree(out)
    coord = json.load(open(os.path.join(RAW, "coordinati.json")))
    extra_f = os.path.join(RAW, "coordinati_extra.json")
    if os.path.exists(extra_f):
        coord += json.load(open(extra_f))
    used = set()
    for it in coord:
        f = os.path.join(RAW, "coord", it["id"] + ".bin")
        if not os.path.exists(f):
            problems.append(("coord-missing", it["title"]))
            continue
        pages, used_ocr, inner = doc_text(f, "c" + it["id"])
        if not pages:
            problems.append(("coord-notext", it["title"]))
            continue
        body = sm_textutil.to_markdown(pages)
        title = re.sub(r"\s+", " ", it["title"]).strip()
        upd = re.search(r"aggiornat[oa]\s+(?:al(?:l')?|a)\s+([^)]+)\)", title)
        meta = {"title": title, "identifier": "documento" + it["id"], "type": "consolidated_text",
                "jurisdiction": "sm", "language": "it"}
        d = it_date(upd.group(1)) if upd else None
        if d:
            meta["last_amended"] = d
        meta["status"] = "in_force"
        meta["category"] = (it["category"] if not re.fullmatch(r"\d+", it["category"]) else "X - Turismo") or \
            "(linked from the archive record of an act, not listed in a category page)"
        meta["note"] = ("Testo coordinato con valore ricognitivo (art. 82 Legge 22 dicembre 2015 n.189); "
                        "non costituisce fonte normativa.")
        if used_ocr:
            meta["ocr"] = True
        meta["source"] = BASE + it["url"]
        if inner:
            meta["source_file"] = os.path.basename(inner)
        meta["retrieved"] = RETRIEVED
        category = it["category"] or "Altri testi coordinati"
        if re.fullmatch(r"\d+", category):
            # category pages without a sub-heading (e.g. the top-level "X - TURISMO" area)
            category = "Turismo" if "turismo" in title.lower() else "Altro"
        cat = slugify(re.sub(r"^\d+\s*-\s*", "", category), 60)
        name = slugify(re.sub(r"\(aggiornat.*$", "", title), 90)
        while f"{cat}/{name}" in used:
            name += "-" + it["id"]
        used.add(f"{cat}/{name}")
        fp = os.path.join(out, cat, name + ".md")
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, "w", encoding="utf-8").write(front(meta) + f"\n\n# {title}\n\n{body}\n")
        stats["testi-coordinati"] += 1
    # ---- archive (acts as published)
    for d in [x[1] for x in KIND_DIR] + ["costituzione"]:
        p = os.path.join(REPO, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
    acts = json.load(open(os.path.join(RAW, "archive.json")))
    sys.path.insert(0, HERE)
    from sm_fetch import want  # noqa: E402
    seen = set()
    used = set()
    for a in acts:
        if not a.get("doc") or not want(a) or a["doc"] in seen:
            continue
        seen.add(a["doc"])
        did = re.search(r"documento(\d+)", a["doc"]).group(1)
        f = os.path.join(RAW, "acts", did + ".bin")
        if not os.path.exists(f):
            problems.append(("act-missing", a["title"]))
            continue
        kind = a.get("kind") or ""
        title = re.sub(r"\s+", " ", a["title"]).strip()
        top, typ = "leggi", "act"
        for rx, dd, tt in KIND_DIR:
            if re.search(rx, kind, re.I) or (not kind and re.search(rx, title, re.I)):
                top, typ = dd, tt
                break
        if a.get("number") == "59" and a.get("date") == "08/07/1974":
            typ = "constitution"  # Dichiarazione dei diritti dei cittadini e dei principi fondamentali
        pages, used_ocr, inner = doc_text(f, "a" + did, prefer_senza_note=False)
        if not pages or not "".join(pages).strip():
            problems.append(("act-notext", title))
            body = "*No text could be extracted from the official document; see the source link.*"
        else:
            body = sm_textutil.to_markdown(pages)
        date = it_date(a.get("date"))
        if date and date < "1600":
            # placeholder dates (01/01/1200) in the archive: take the date from the document itself
            date = it_date(" ".join(pages or [])[:600]) if pages else None
            if date and date < "1600":
                date = None
        title = make_title(title, kind, a.get("number"), date, body)
        meta = {"title": title}
        if a.get("number"):
            meta["identifier"] = f"{kind or top} n. {a['number']}".strip()
        meta["type"] = typ
        meta["jurisdiction"] = "sm"
        meta["language"] = "it"
        if date:
            meta["date"] = date
        meta["status"] = "unknown"
        meta["consolidated"] = False
        if a.get("coordinati"):
            meta["has_consolidated_text"] = True
        if used_ocr:
            meta["ocr"] = True
        meta["source"] = BASE + a["doc"]
        if a.get("scheda"):
            meta["source_details"] = BASE + a["scheda"]
        meta["retrieved"] = RETRIEVED
        year = date[:4] if date else "senza-data"
        if typ == "constitution":
            top = "costituzione"
        name = f"{date or 'senza-data'}-n{slugify(a.get('number') or '', 20)}" if a.get("number") else f"{date}-{slugify(title, 60)}"
        base, k = name, 2
        while f"{top}/{year}/{name}" in used:
            name = f"{base}-{k}"
            k += 1
        used.add(f"{top}/{year}/{name}")
        fp = os.path.join(REPO, top, year, name + ".md")
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, "w", encoding="utf-8").write(front(meta) + f"\n\n# {title}\n\n{body}\n")
        stats[top] += 1
        if used_ocr:
            stats["ocr"] += 1
    print(dict(stats), file=sys.stderr)
    print("problems", len(problems), Counter(p[0] for p in problems), problems[:30], file=sys.stderr)
    json.dump(problems, open(os.path.join(RAW, "convert_problems.json"), "w"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
