"""Second demo persona in an Axis-style layout, to show nothing is tied to the main sample.

Ananya, 29, Bengaluru, ₹1,10,000 salary, Jul–Sep 2026: shopping-heavy, weekday lunch delivery, cabs, a car EMI,
three subscriptions (none a gym), friends who pay her back, a one-off ₹74,900 phone, and a few merchants that are not in
merchants.json so the LLM tier gets exercised. Run: python scripts/make_persona2.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(29)
OUT = Path(__file__).resolve().parent.parent / "data" / "samples" / "axis_style_bengaluru.csv"
ref = lambda: str(random.randint(10**11, 10**12 - 1))
rows = []  # (date, narration, debit, credit)


def upi(d, name, vpa, note, amt):
    rows.append((d, f"UPI/P2M/{ref()}/{name}/{vpa}/{note}", amt, 0))


for m in (7, 8, 9):
    first = date(2026, m, 1)
    rows.append((first, f"NEFT/INFY{ref()[:8]}/INFOSYS LIMITED/SALARY {first:%b %Y}".upper(), 0, 110000))
    rows.append((first + timedelta(days=1), f"IMPS/{ref()}/NOBROKER RENT/RENT {first:%b}".upper(), 32000, 0))
    rows.append((first + timedelta(days=4), f"NACH/DR/HDFC BANK CAR LOAN/EMI {ref()[:8]}", 14200, 0))
    rows.append((first + timedelta(days=5), f"NACH/DR/ZERODHA COIN SIP/{ref()[:8]}", 10000, 0))
    upi(first + timedelta(days=6), "NETFLIX", "netflix@icici", "Autopay", 649)
    upi(first + timedelta(days=7), "PRIME VIDEO", "primevideo@apl", "Autopay", 299)
    upi(first + timedelta(days=8), "YOUTUBE", "youtube@okaxis", "Premium", 149)
    upi(first + timedelta(days=14), "BESCOM", "bescom@ybl", "Electricity", random.randint(900, 1600))
    upi(first + timedelta(days=15), "ACT FIBERNET", "actfibernet@ybl", "Broadband", 1179)
    d = first
    while d.month == m:
        wd = d.weekday()
        if wd < 5 and random.random() < 0.55:
            upi(d, "SWIGGY", "swiggy@ybl", "Lunch", random.randint(180, 420))
        if random.random() < 0.45:
            upi(d, "UBER", "uber@axisbank", "Ride", random.randint(150, 520))
        if wd == 5 and random.random() < 0.8:
            upi(d, "BIGBASKET", "bigbasket@ybl", "Grocery", random.randint(1400, 2800))
        if random.random() < 0.18:
            name, vpa = random.choice([("MYNTRA", "myntra@ybl"), ("AMAZON", "amazon@apl"), ("NYKAA", "nykaa@paytm"), ("URBANIC", "urbanic@ybl")])
            upi(d, name, vpa, "Order", random.randint(900, 4800))
        if random.random() < 0.06:
            upi(d, "THIRD WAVE COFFEE", "thirdwavecoffee@ybl", "Cafe", random.randint(250, 600))
        if random.random() < 0.05:
            upi(d, "URBAN COMPANY", "urbancompany@ybl", "Home service", random.randint(500, 1500))
        d += timedelta(days=1)
    for friend, vpa in (("KARAN M", "karan.m@okhdfcbank"), ("SNEHA R", "sneha.r@oksbi")):
        out = random.randint(600, 2200)
        rows.append((first + timedelta(days=random.randint(9, 20)), f"UPI/P2A/{ref()}/{friend}/{vpa}/Dinner split", out, 0))
        rows.append((first + timedelta(days=random.randint(21, 27)), f"UPI/P2A/{ref()}/{friend}/{vpa}/Paid back", 0, round(out * random.uniform(0.4, 1.0))))
    rows.append((first + timedelta(days=10), f"ATM-WDL/{ref()}/KORAMANGALA BLR", 3000, 0))
upi(date(2026, 8, 22), "APPLE INDIA", "appleindia@hdfcbank", "iPhone", 74900)

rows.sort(key=lambda r: r[0])
bal = 85000.0
with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Axis Bank Ltd. Statement of Account"])
    w.writerow(["Customer: ANANYA S", "Account No: XXXXXXXX7710", "Period: 01-07-2026 to 30-09-2026"])
    w.writerow([])
    w.writerow(["Tran Date", "CHQNO", "PARTICULARS", "DR", "CR", "BAL", "SOL"])
    for d, narr, dr, cr in rows:
        bal += cr - dr
        w.writerow([d.strftime("%d-%m-%Y"), "", narr, f"{dr:.2f}" if dr else "", f"{cr:.2f}" if cr else "", f"{bal:.2f}", "4521"])
print("wrote", OUT, len(rows), "rows, closing balance", round(bal))
