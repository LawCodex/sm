#!/usr/bin/env python3
"""Fetch San Marino legislation from the Consiglio Grande e Generale web site.

1. "Testi coordinati" (consolidated texts with recognitive value, art. 82 Legge 189/2015):
   category pages -> document ZIPs (PDF inside).
2. "Archivio leggi, decreti e regolamenti": listing by document type -> PDF of each act.
Everything is cached under _raw/sm/.
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import html as htmlmod

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
BASE = "https://www.consigliograndeegenerale.sm"
ARCH = BASE + "/on-line/home/archivio-leggi-decreti-e-regolamenti.html"
RAW = os.path.abspath(os.environ.get("SM_RAW", os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "sm")))
HDRS = {"User-Agent": UA}
DELAY = 1.0


def get(url, params=None, tries=5):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=HDRS, timeout=180)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
            print("HTTP", r.status_code, url, file=sys.stderr)
        except requests.RequestException as e:
            print("ERR", e, url, file=sys.stderr)
        time.sleep(10 * (i + 1))
    return None


def dec(r):
    try:
        return r.content.decode("utf-8")
    except UnicodeDecodeError:
        return r.content.decode("cp1252", "replace")


def list_archive(tipo):
    out = []
    page = 1
    while True:
        params = {"P0_path": "/home/tomcat/indicizzazione/indexleggi", "P0_paginazione": "100",
                  "P0_pagina": str(page), "P0_orderBy": "index_lucene,data_ordered,numero",
                  "P0_order": "asc,desc,desc", "P0_operatorMustBe": "yes", "P0_tipo": tipo}
        t = dec(get(ARCH, params))
        m = re.search(r"Risultati trovati: <small>(\d+)</small> - Pagina <small>(\d+)</small> di <small>(\d+)<", t)
        cards = re.split(r'<div id="card_', t)[1:]
        for c in cards:
            cid = c.split('"')[0]
            h3 = re.search(r"<h3>(.*?)</h3>", c, re.S)
            doc = re.search(r'href="(/on-line/home/archivio-leggi-decreti-e-regolamenti/documento\d+\.html)"', c)
            info = re.search(r'<div class="fl">(.*?)numero\s*<a>([^<]*)</a>\s*del\s*(\d\d/\d\d/\d{4})', c, re.S)
            scheda = re.search(r'href="(/on-line/home/archivio-leggi-decreti-e-regolamenti/scheda\d+\.html)"', c)
            out.append({
                "card": cid,
                "title": htmlmod.unescape(re.sub(r"<[^>]+>", "", h3.group(1))).strip() if h3 else "",
                "doc": doc.group(1) if doc else None,
                "kind": htmlmod.unescape(re.sub(r"<[^>]+>|\s+", " ", info.group(1))).replace("\xa0", " ").strip() if info else None,
                "number": info.group(2).strip() if info else None,
                "date": info.group(3) if info else None,
                "scheda": scheda.group(1) if scheda else None,
                "coordinati": "TESTI COORDINATI" in c,
            })
        print(tipo, page, m and m.group(3), len(out), file=sys.stderr, flush=True)
        if not m or int(m.group(2)) >= int(m.group(3)):
            return out
        page += 1
        time.sleep(DELAY)


def list_coordinati():
    t = dec(get(BASE + "/on-line/home/testi-coordinati.html"))
    cats = sorted(set(re.findall(r'href="(/on-line/home/testi-coordinati/docCat\.(\d+)\.1\.150\.20\.html)"', t)))
    out = []
    for url, cid in cats:
        time.sleep(DELAY)
        c = dec(get(BASE + url))
        h2 = re.search(r"<h2>Testi Coordinati.*?<br/><br/>(.*?)</h2>", c, re.S)
        cat = htmlmod.unescape(h2.group(1)).strip() if h2 else cid
        for row in re.findall(r'<td id="bordosx" class="testocelle">(.*?)</td>.*?href="(/on-line/documento(\d+)\.html)"', c, re.S):
            out.append({"category": cat, "category_id": cid,
                        "title": htmlmod.unescape(re.sub(r"<[^>]+>", " ", row[0])).strip(),
                        "url": row[1], "id": row[2]})
        print("cat", cat, len(out), file=sys.stderr, flush=True)
    return out


def main():
    os.makedirs(os.path.join(RAW, "coord"), exist_ok=True)
    os.makedirs(os.path.join(RAW, "acts"), exist_ok=True)
    fc = os.path.join(RAW, "coordinati.json")
    if not os.path.exists(fc):
        json.dump(list_coordinati(), open(fc, "w"), ensure_ascii=False, indent=0)
    fa = os.path.join(RAW, "archive.json")
    if not os.path.exists(fa):
        acts = []
        for tipo in ("+Legge", "+Decreto", "+Regolamento", "+Statuto"):
            acts += list_archive(tipo)
        json.dump(acts, open(fa, "w"), ensure_ascii=False, indent=0)
    coord = json.load(open(fc))
    for it in coord:
        f = os.path.join(RAW, "coord", it["id"] + ".bin")
        if os.path.exists(f):
            continue
        r = get(BASE + it["url"])
        if r is not None:
            open(f + ".hdr", "w").write(r.headers.get("Content-Disposition", ""))
            open(f, "wb").write(r.content)
        time.sleep(DELAY)
    print("coordinati done", file=sys.stderr, flush=True)
    acts = json.load(open(fa))
    sel, seen = [], set()
    for a in acts:
        if a["doc"] and want(a) and a["doc"] not in seen:
            seen.add(a["doc"])
            sel.append(a)
    print(len(sel), "acts to fetch", file=sys.stderr, flush=True)

    def fetch_act(a):
        did = re.search(r"documento(\d+)", a["doc"]).group(1)
        f = os.path.join(RAW, "acts", did + ".bin")
        if os.path.exists(f):
            return
        r = get(BASE + a["doc"])
        if r is not None:
            open(f + ".hdr", "w").write(r.headers.get("Content-Disposition", ""))
            open(f, "wb").write(r.content)
        time.sleep(DELAY)

    with cf.ThreadPoolExecutor(3) as ex:
        for n, _ in enumerate(ex.map(fetch_act, sel)):
            if n % 100 == 0:
                print("acts", n, len(sel), file=sys.stderr, flush=True)

    # consolidated texts referenced from the acts' detail pages but missing from the category pages
    found = coordinati_from_schede(acts)
    known = {c["id"] for c in coord}
    extra = [{"category": "", "category_id": "", "title": t, "url": f"/on-line/documento{d}.html", "id": d}
             for d, t in sorted(found.items()) if d not in known]
    print(len(found), "consolidated texts referenced,", len(extra), "not in category pages", file=sys.stderr)
    json.dump(extra, open(os.path.join(RAW, "coordinati_extra.json"), "w"), ensure_ascii=False, indent=0)
    for it in extra:
        f = os.path.join(RAW, "coord", it["id"] + ".bin")
        if os.path.exists(f):
            continue
        r = get(BASE + it["url"])
        if r is not None:
            open(f + ".hdr", "w").write(r.headers.get("Content-Disposition", ""))
            open(f, "wb").write(r.content)
        time.sleep(DELAY)
    print("all done", file=sys.stderr, flush=True)


def coordinati_from_schede(acts):
    """The "Testi coordinati" category pages do not list every consolidated text: collect the
    links found on the detail page (scheda) of every act flagged "(TESTI COORDINATI)"."""
    os.makedirs(os.path.join(RAW, "schede"), exist_ok=True)
    schede = sorted({a["scheda"] for a in acts if a.get("coordinati") and a.get("scheda")})
    print(len(schede), "schede to read", file=sys.stderr, flush=True)

    def one(url):
        f = os.path.join(RAW, "schede", re.search(r"scheda(\d+)", url).group(1) + ".html")
        if not os.path.exists(f):
            r = get(BASE + url)
            if r is None:
                return
            open(f, "w").write(dec(r))
            time.sleep(DELAY)

    with cf.ThreadPoolExecutor(3) as ex:
        list(ex.map(one, schede))
    found = {}
    for fn in os.listdir(os.path.join(RAW, "schede")):
        t = open(os.path.join(RAW, "schede", fn)).read()
        for title, did in re.findall(r'<a alt="[^"]*" title="([^"]*)" href="documento(\d+)\.html"', t):
            found.setdefault(did, htmlmod.unescape(title).strip())
    return found


def want(a):
    k = (a.get("kind") or "").lower()
    # primary legislation and regulations; skip errata, verbali, notifiche, ordinanze,
    # decreti reggenziali / consiliari (mostly appointments and administrative acts)
    return bool(re.search(r"legg[ea]|decreto\s*[-–]?\s*del[ae]g|regolamento|statuto", k)) \
        and "errata" not in k and "reggenzial" not in k and "consi" not in k


if __name__ == "__main__":
    main()
