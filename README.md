# LawCodex — San Marino (sm)

Legislation of the Republic of San Marino as Markdown (Italian), from the official web site of
the **Consiglio Grande e Generale** (Segreteria Istituzionale) — https://www.consigliograndeegenerale.sm.

Retrieved: **2026-10-13**.

## Coverage

**5,280 Markdown files** in two collections:

### 1. Consolidated texts — `testi-coordinati/` (65 files)

The *Testi coordinati* published by the Segreteria Istituzionale: consolidated texts and
collections ("raccolte coordinate") of the main laws in force, including the **Declaration of
Citizens' Rights and Fundamental Principles** (Legge 8 luglio 1974 n.59, San Marino's
constitutional charter), the Criminal Code, the Code of Criminal Procedure, the judicial system,
company law, tax law, labour law, etc. They have *valore ricognitivo* (art. 82 Legge 22 dicembre
2015 n.189) — they are official working consolidations, not the legally binding source.
Sub-directories follow the subject categories of the site; texts that are only linked from the
archive records of the acts (not listed on a category page) are in
`testi-coordinati/altri-testi-coordinati/`. `last_amended` = the "aggiornato al" date.

### 2. Acts as published — archive of laws, decrees and regulations (5,215 files)

Every act of the following kinds in the *Archivio leggi, decreti e regolamenti*, from the 19th
century to October 2026, **as originally published** (not consolidated; `status: unknown`,
`consolidated: false`; `has_consolidated_text: true` when a *testo coordinato* exists):

| Directory | Kind | Files |
|---|---|---|
| `costituzione/` | Legge 8 luglio 1974 n.59 — Dichiarazione dei diritti dei cittadini e dei principi fondamentali dell'ordinamento sammarinese (original text; see `testi-coordinati/` for the consolidated version) | 1 |
| `leggi-costituzionali/<year>/` | Leggi costituzionali / di revisione costituzionale | 19 |
| `leggi-qualificate/<year>/` | Leggi qualificate | 38 |
| `leggi/<year>/` | Leggi (ordinarie) | 1,966 |
| `decreti-legge/<year>/` | Decreti-legge | 440 |
| `decreti-delegati/<year>/` | Decreti delegati | 2,374 |
| `regolamenti/<year>/` | Regolamenti | 365 |
| `statuti/<year>/` | Statuti | 12 |

Files are named `<date>-n<number>.md`; acts whose archive record has no real date (placeholder
`01/01/1200`) are dated from the text when possible, otherwise filed under `senza-data/`.

### Not covered

- *Decreti* (plain), *Decreti reggenziali* and *Decreti consiliari* (≈ 5,400 records: mostly
  appointments, ratifications, stamp/coin issues and other administrative acts), *Ordinanze*,
  *Notifiche*, *Verbali* and *Errata corrige* — skipped as mass-volume secondary acts.
- Repeal/in-force status of the archived acts (not provided by the source).
- The *Bollettino Ufficiale* (http://www.bollettinoufficiale.sm), which is the authentic
  publication.
- Download failures: 4 consolidated texts linked from archive records return HTTP 403
  (documento17087539 licenze, 17087540 società 2018, 17101400 commercio, 17101403 start-up —
  apparently withdrawn older versions) and 1 act returns HTTP 500 (documento17016732, *la
  sospensione della esecuzione delle sentenze penali di condanna*).

## Text extraction

The site serves PDFs (the *testi coordinati* as ZIP files containing a PDF with and one without
footnotes; the version *senza note* is used). Text is extracted with poppler's `pdftotext`;
the few scanned PDFs without a text layer (2) were OCRed with `tesseract` (Italian model) and
are flagged `ocr: true`. Line breaks are re-joined into paragraphs and *Parte / Titolo / Capo /
Sezione / Art.* lines become Markdown headings; page numbers and tables of contents with dot
leaders are dropped. Extraction artefacts (occasional split words, table layout lost) remain.

## Sources

- https://www.consigliograndeegenerale.sm/on-line/home/testi-coordinati.html (category pages
  `docCat.*.html` → `documento<ID>.html` ZIP/PDF) and the detail pages (`scheda<ID>.html`) of
  every act flagged *TESTI COORDINATI*.
- https://www.consigliograndeegenerale.sm/on-line/home/archivio-leggi-decreti-e-regolamenti.html
  (search by type: *Legge*, *Decreto*, *Regolamento*, *Statuto*; 100 results per page) →
  `documento<ID>.html` (PDF).
- robots.txt is not available on the site (HTTP 403); requests were made at ≤ 3 concurrent
  connections with 1 s delay and a LawCodex User-Agent. The site notes that the documents «non
  hanno carattere di autenticità».

## Licence / copyright

San Marino copyright law (Legge 25 gennaio 1991 n.8, *Tutela del diritto d'autore*, art. 98
lett. f) allows free reproduction, even in full, of «atti dello Stato o delle Pubbliche
Amministrazioni». For authentic texts refer to the Segreteria Istituzionale / Bollettino Ufficiale.

## Regenerate

```sh
pip install -r scripts/requirements.txt
python scripts/sm_fetch.py      # lists + downloads into ../_raw/sm/ (cached; slow site, several hours)
python scripts/sm_convert.py    # write Markdown (needs poppler; tesseract + ita.traineddata for OCR)
```
