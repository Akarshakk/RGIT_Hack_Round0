"""Generate synthetic Indian bank statements + ground truth for one persona.

Persona: 24yo in Mumbai, salary Rs 65,000, Jun-Sep 2026. Seeded, so output is reproducible.
Run: python scripts/make_sample.py
"""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

OUT = Path(__file__).resolve().parent.parent / "data" / "samples"
PDF_PASSWORD = "kharcha123"
OPENING_BALANCE = 40000
MONTHS = [(2026, 6), (2026, 7), (2026, 8), (2026, 9)]

# category -> bucket; P2 reuses this taxonomy
TAXONOMY = {
    "Income": "Income", "Rent": "Need", "Groceries": "Need", "Utilities & Bills": "Need",
    "EMI & Loans": "Need", "Transport": "Need", "Fees & Charges": "Need",
    "Food & Dining": "Want", "Shopping": "Want", "Subscriptions": "Want",
    "Entertainment": "Want", "Investments": "Savings",
    "Cash Withdrawal": "Transfer", "Transfers": "Transfer", "Other": "Want",
}

rng = random.Random(42)
rows = []  # dicts: date, narr (slash format), amount (+credit/-debit), category, merchant


def ref():
    return "".join(str(rng.randint(0, 9)) for _ in range(12))


def add(d, narr, amount, category, merchant, **extra):
    rows.append(dict(date=d, narr=narr, amount=amount, category=category, merchant=merchant, **extra))


def upi(d, vpa, note, amount, category, merchant, **extra):
    add(d, f"UPI/P2M/{ref()}/{vpa}/{note}", -amount, category, merchant, **extra)


FRIENDS = [("rahul.sharma@okicici", "Rahul Sharma"), ("priya.n@oksbi", "Priya Nair"), ("amit.k@ybl", "Amit Kulkarni")]

for y, m in MONTHS:
    D = lambda day: date(y, m, day)
    mon = f"{D(1):%b} {y}".upper()
    add(D(1), f"NEFT CR:HDFC0000123:ACME TECH PVT LTD:SALARY {mon}:N{ref()}", 65000, "Income", "acme tech")
    add(D(2), f"IMPS/{ref()}/RAMESH PATIL/RENT {mon}", -18000, "Rent", "ramesh patil")
    add(D(3), f"NACH/DR/BAJAJ FINSERV LTD/EMI {ref()[:8]}", -6500, "EMI & Loans", "bajaj finserv")
    add(D(4), f"NACH/DR/GROWW MF SIP/{ref()[:8]}", -5000, "Investments", "groww sip")
    upi(D(5), "netflix@icici", "Autopay", 649, "Subscriptions", "netflix", subscription=True)
    upi(D(6), "spotify@axisbank", "Autopay", 119, "Subscriptions", "spotify", subscription=True)
    upi(D(7), "hotstar@ybl", "Autopay", 299, "Subscriptions", "hotstar", subscription=True)
    upi(D(10), "cultfit@ybl", "Gym membership", 1499, "Subscriptions", "cultfit gym", subscription=True, unused=True)
    upi(D(12), "jio@ybl", "Recharge", 299, "Utilities & Bills", "jio")
    upi(D(15), "adanielectricity@icici", "Electricity bill", rng.randint(1200, 1800), "Utilities & Bills", "adani electricity")

    # weekend food delivery (the "leak")
    d = D(1)
    while d.month == m:
        if d.weekday() >= 5:
            for _ in range(rng.choice([1, 2])):
                vpa, name = rng.choice([("swiggy@ybl", "swiggy"), ("zomato@icici", "zomato")])
                upi(d, vpa, f"Order {rng.randint(100, 999)}", rng.randint(280, 520), "Food & Dining", name)
        d += timedelta(days=1)
    for _ in range(2):  # a couple of weekday orders and cafes too
        upi(D(rng.randint(1, 28)), "starbucks@hdfcbank", "Cafe", rng.randint(250, 480), "Food & Dining", "starbucks")

    for _ in range(4):
        vpa, name = rng.choice([("blinkit@paytm", "blinkit"), ("zepto@okaxis", "zepto")])
        upi(D(rng.randint(1, 28)), vpa, "Grocery", rng.randint(350, 900), "Groceries", name)
    for _ in range(9):
        vpa, name = rng.choice([("uber@axisbank", "uber"), ("rapido@ybl", "rapido")])
        upi(D(rng.randint(1, 28)), vpa, "Ride", rng.randint(90, 260), "Transport", name)
    for _ in range(rng.choice([1, 2])):
        upi(D(rng.randint(1, 28)), "amazon@apl", "Order", rng.randint(500, 1800), "Shopping", "amazon")
    for dd in (rng.randint(8, 12), rng.randint(20, 25)):
        add(D(dd), f"ATM WDL/NFS/{ref()}/MUMBAI ANDHERI W", -2000, "Cash Withdrawal", "atm")
    for _ in range(3):
        vpa, name = rng.choice(FRIENDS)
        add(D(rng.randint(1, 28)), f"UPI/P2A/{ref()}/{vpa}/Split", -rng.randint(300, 1200), "Transfers", name)

# one-offs
upi(date(2026, 8, 18), "croma@hdfcbank", "Electronics", 18999, "Shopping", "croma", anomaly=True)
add(date(2026, 8, 20), f"CHARGES/LATE PAYMENT FEE/CC OUTSTANDING/{ref()[:8]}", -590, "Fees & Charges", "late fee", fee=True)

rows.sort(key=lambda r: r["date"])  # stable: keeps within-day insertion order
bal = OPENING_BALANCE
for i, r in enumerate(rows):
    bal += r["amount"]
    assert bal > 0, r
    r["balance"], r["id"] = bal, i

OUT.mkdir(parents=True, exist_ok=True)
money = lambda v: f"{v:.2f}"

# HDFC-style: metadata lines, then Withdrawal/Deposit columns, summary footer
with open(OUT / "hdfc_style.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["HDFC BANK LTD."])
    w.writerow(["Account Statement"])
    w.writerow(["Account No : XXXXXXXX4821", "Customer : ARJUN MEHTA"])
    w.writerow([f"Statement From : 01/06/2026 To : 30/09/2026"])
    w.writerow([])
    w.writerow(["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
    for r in rows:
        d = f"{r['date']:%d/%m/%y}"
        w.writerow([d, r["narr"], r["narr"].split("/")[2][:12] if r["narr"].startswith("UPI") else "", d,
                    money(-r["amount"]) if r["amount"] < 0 else "", money(r["amount"]) if r["amount"] > 0 else "",
                    money(r["balance"])])
    w.writerow([])
    w.writerow(["STATEMENT SUMMARY"])
    w.writerow(["Opening Balance", "Dr Count", "Cr Count", "Debits", "Credits", "Closing Bal"])
    w.writerow([money(OPENING_BALANCE), sum(r["amount"] < 0 for r in rows), sum(r["amount"] > 0 for r in rows),
                money(-sum(r["amount"] for r in rows if r["amount"] < 0)),
                money(sum(r["amount"] for r in rows if r["amount"] > 0)), money(bal)])

# SBI-style: single Amount + Dr/Cr, hyphen-separated narrations, comma-formatted numbers
with open(OUT / "sbi_style.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Txn Date", "Description", "Amount", "Dr/Cr", "Balance"])
    for r in rows:
        w.writerow([f"{r['date']:%d %b %Y}", r["narr"].replace("/", "-"), f"{abs(r['amount']):,.2f}",
                    "Cr" if r["amount"] > 0 else "Dr", f"{r['balance']:,.2f}"])

# Password-protected PDF with a ruled table (same data as hdfc_style)
styles = getSampleStyleSheet()
cell = styles["BodyText"].clone("cell", fontSize=7, leading=8.5)
data = [["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]]
for r in rows:
    data.append([f"{r['date']:%d/%m/%y}", Paragraph(r["narr"], cell),
                 money(-r["amount"]) if r["amount"] < 0 else "", money(r["amount"]) if r["amount"] > 0 else "",
                 money(r["balance"])])
table = Table(data, colWidths=[50, 270, 70, 70, 75], repeatRows=1)
table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 7),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
SimpleDocTemplate(str(OUT / "statement.pdf"), pagesize=A4, encrypt=StandardEncryption(PDF_PASSWORD, canPrint=1)).build(
    [Paragraph("HDFC BANK LTD. - Account Statement (01/06/2026 to 30/09/2026)", styles["Heading3"]), table])

# Ground truth
by_month = lambda cat: {f"{y}-{m:02d}": -sum(r["amount"] for r in rows
                                             if r["category"] == cat and r["date"].year == y and r["date"].month == m)
                        for y, m in MONTHS}
subs = {}
for r in rows:
    if r.get("subscription"):
        subs.setdefault(r["merchant"], dict(merchant=r["merchant"], monthly=-r["amount"], unused=bool(r.get("unused"))))
anom = next(r for r in rows if r.get("anomaly"))
fee = next(r for r in rows if r.get("fee"))
truth = dict(
    password=PDF_PASSWORD, opening_balance=OPENING_BALANCE, closing_balance=bal, row_count=len(rows),
    total_debit=round(-sum(r["amount"] for r in rows if r["amount"] < 0), 2),
    total_credit=round(sum(r["amount"] for r in rows if r["amount"] > 0), 2),
    taxonomy=TAXONOMY, food_by_month=by_month("Food & Dining"), spend_by_category={
        c: round(-sum(r["amount"] for r in rows if r["category"] == c), 2) for c in TAXONOMY if c != "Income"},
    subscriptions=list(subs.values()), other_recurring=[dict(merchant="jio", monthly=299)],
    anomaly=dict(id=anom["id"], merchant=anom["merchant"], amount=-anom["amount"], date=str(anom["date"])),
    late_fee=dict(id=fee["id"], amount=-fee["amount"], date=str(fee["date"])),
    rows=[dict(id=r["id"], date=str(r["date"]), amount=r["amount"], category=r["category"], merchant=r["merchant"],
               narration=r["narr"]) for r in rows],
)
(OUT / "ground_truth.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False))
print(f"{len(rows)} rows | debit {truth['total_debit']:,.2f} credit {truth['total_credit']:,.2f} closing {bal:,.2f}")
