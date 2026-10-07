"""CSV / XLSX / PDF bank statement -> normalized DataFrame.

Columns: date (datetime), narration (str), amount (float, +credit/-debit), balance (float|NaN), source (str).
"""
import csv
import io
import re

import pandas as pd

SYN = {
    "date": {"date", "txn date", "transaction date", "tran date", "posting date", "value dt", "value date"},
    "narration": {"narration", "description", "particulars", "remarks", "details", "transaction remarks"},
    "debit": {"withdrawal", "withdrawal amt", "debit", "debit amount", "dr", "withdrawals"},
    "credit": {"deposit", "deposit amt", "credit", "credit amount", "cr", "deposits"},
    "amount": {"amount", "txn amount", "transaction amount"},
    "flag": {"dr/cr", "cr/dr", "type", "txn type", "debit/credit"},
    "balance": {"balance", "closing balance", "running balance", "available balance"},
}
SUMMARY_ROW = re.compile(r"opening balance|closing balance|total|b/f|c/f", re.I)


class NeedsMapping(Exception):
    """Columns could not be auto-detected; UI should ask the user to pick them."""

    def __init__(self, columns):
        super().__init__("Could not detect statement columns")
        self.columns = columns


def _norm(c):
    return re.sub(r"\s+", " ", str(c or "")).strip().lower().rstrip(".")


def _read_rows(data, name, password):
    n = name.lower()
    if n.endswith(".pdf"):
        import pdfplumber
        from pdfminer.pdfdocument import PDFPasswordIncorrect
        try:
            with pdfplumber.open(io.BytesIO(data), password=password) as pdf:
                return [[(c or "").replace("\n", " ") for c in row] for pg in pdf.pages for t in pg.extract_tables() for row in t]
        except Exception as e:  # pdfminer wraps the password error in PdfminerException
            if isinstance(e, PDFPasswordIncorrect) or isinstance(getattr(e, "args", [None])[0], PDFPasswordIncorrect):
                raise ValueError("This PDF is password-protected. Enter the correct password.") from e
            raise
    if n.endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(io.BytesIO(data), header=None, dtype=str).fillna("").values.tolist()
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))


def _find_header(rows):
    """Index of the first row (in the top 30) holding both a date and a narration synonym, else None."""
    for i, r in enumerate(rows[:30]):
        cells = {_norm(c) for c in r}
        if cells & SYN["date"] and cells & SYN["narration"]:
            return i
    return None


def _col(header, key):
    for i, c in enumerate(header):
        if _norm(c) in SYN[key]:
            return i


def _num(s):
    """'₹1,234.50 Dr' -> (1234.5, 'dr'); blank -> (0.0, None)."""
    s = str(s or "")
    m = re.search(r"\b(dr|cr)\b\.?\s*$", s.strip(), re.I)
    s = re.sub(r"[^\d.\-]", "", s.replace("Rs.", ""))
    try:
        return float(s), (m.group(1).lower() if m else None)
    except ValueError:
        return 0.0, None


def load_statement(file_bytes, filename, password=None, mapping=None):
    """mapping (from the UI after NeedsMapping): {"date": col, "narration": col, "amount": col}."""
    rows = [r for r in _read_rows(file_bytes, filename, password) if any(str(c).strip() for c in r)]
    h = _find_header(rows)
    if h is None:
        # best guess at the header: first row with 3+ filled cells
        h = next((i for i, r in enumerate(rows[:30]) if sum(bool(str(c).strip()) for c in r) >= 3), None)
        if h is None:
            raise NeedsMapping([])
        if not mapping:
            raise NeedsMapping([str(c).strip() for c in rows[h] if str(c).strip()])
    header = rows[h]
    if mapping:
        idx = {k: next(i for i, c in enumerate(header) if str(c).strip() == v) for k, v in mapping.items()}
        d, n, a, dr, cr, fl = idx["date"], idx["narration"], idx.get("amount"), None, None, None
        bal = _col(header, "balance")
    else:
        d, n, a, dr, cr, fl, bal = (_col(header, k) for k in ("date", "narration", "amount", "debit", "credit", "flag", "balance"))
        if a is None and dr is None and cr is None:
            raise NeedsMapping([str(c).strip() for c in header if str(c).strip()])

    width = len(header)
    cell = lambda r, i: r[i] if i is not None and i < len(r) else ""
    recs = []
    for r in rows[h + 1:]:
        r = list(r) + [""] * (width - len(r))
        if _norm(cell(r, d)) in SYN["date"]:  # header repeated on each PDF page
            continue
        if a is not None:
            v, suffix = _num(cell(r, a))
            flag = _norm(cell(r, fl))[:1] if fl is not None else (suffix or "")[:1]
            amt = -v if flag == "d" else v
        else:
            amt = _num(cell(r, cr))[0] - _num(cell(r, dr))[0]
        recs.append((cell(r, d), str(cell(r, n)).strip(), amt, _num(cell(r, bal))[0] if cell(r, bal) else float("nan")))

    df = pd.DataFrame(recs, columns=["date", "narration", "amount", "balance"])
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce", format="mixed")
    df = df[df["date"].notna() & ~df["narration"].str.contains(SUMMARY_ROW)]  # drops footers, totals, blanks
    df = df.drop_duplicates()  # balance is part of the key, so legit same-day repeats survive
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    df["source"] = filename
    return df
