import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

MONTHS = "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()
DATA = Path(__file__).parent / "data"


def read_branch(branch):
    with (DATA / f"{branch}.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = []
        risks = defaultdict(set)
        for r in csv.DictReader(f):
            company = r["Sirket Adı"]
            month = MONTHS.index(r["Ay"]) + 1
            rows.append((month, company, r["Plaka İl"], int(r["Yazılan Poliçe Primi"]), int(r["Yazılan Poliçe Adedi"])))
            risks[company].add(tuple(float(r[k].strip("%").replace(",", ".")) for k in ("HP", "Freq")))
    return rows, {c: next(iter(v)) for c, v in risks.items() if len(v) == 1}


def aggregate(rows, start, end, region):
    groups = defaultdict(lambda: [0, 0])
    totals = defaultdict(lambda: [0, 0])
    cities = defaultdict(lambda: [0, 0])
    for m, c, city, premium, count in rows:
        if not start <= m <= end:
            continue
        if region == "İstanbul dışı" and city == "İSTANBUL":
            continue
        if region not in ("Tümü", "İstanbul dışı") and city != region:
            continue
        for group in (groups[m, c], totals[m], cities[c, city]):
            group[0] += premium
            group[1] += count
    panel = []
    for (m, c), (p, n) in sorted(groups.items()):
        total, count = totals[m]
        panel.append(dict(ay=m, şirket=c, prim=p, adet=n, pay=100*p/total if total else None,
                          adet_payı=100*n/count if count else None, ortalama=p/n if n else None))
    return panel, totals, cities


def changes(panel):
    previous = {}
    result = []
    for row in panel:
        c = row["şirket"]
        last = previous.get(c)
        if last and last["ay"] + 1 == row["ay"] and None not in (last["pay"], row["pay"]):
            result.append(dict(şirket=c, önceki_ay=MONTHS[last["ay"]-1], ay=MONTHS[row["ay"]-1],
                               önceki_pay=last["pay"], pay=row["pay"], fark=row["pay"]-last["pay"]))
        previous[c] = row
    return sorted(result, key=lambda x: -abs(x["fark"]))


def stable(panel, months, width):
    result = []
    for c in sorted({r["şirket"] for r in panel}):
        values = [r["pay"] for r in panel if r["şirket"] == c and r["pay"] is not None]
        if len(values) == months and months >= 3 and max(values)-min(values) <= width:
            result.append(dict(şirket=c, en_düşük=min(values), en_yüksek=max(values),
                               ortalama=sum(values)/months, bant=max(values)-min(values)))
    return sorted(result, key=lambda x: -x["ortalama"])


def risk_summary(risks, company):
    hp, freq = risks[company]
    return (hp, freq, 1+sum(h > hp for h, _ in risks.values()),
            median(h for h, _ in risks.values()), median(f for _, f in risks.values()))
