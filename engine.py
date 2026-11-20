import json
from zipfile import ZipFile

import pandas as pd
from collections import defaultdict
from pathlib import Path
from statistics import median

MONTHS = "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()
DATA = Path(__file__).parent / "data"


SNAPSHOT = Path(__file__).parent / "kokpit.zip"


def metadata():
    with ZipFile(SNAPSHOT) as archive:
        return json.loads(archive.read("meta.json"))


def read_branch(branch, vehicles, persons):
    with ZipFile(SNAPSHOT) as archive, archive.open(f"{branch}.csv") as stream:
        parts = []
        keys = ["ay", "şirket", "il"]
        for chunk in pd.read_csv(stream, chunksize=100000, keep_default_na=False):
            selection = chunk[chunk["araç"].isin(vehicles) & chunk["tür"].isin(persons)]
            parts.append(selection.groupby(keys)[["kuruş", "adet"]].sum())
    sums = pd.concat(parts).groupby(level=keys).sum().reset_index()
    sums["prim"] = sums.pop("kuruş") / 100
    return list(sums[keys + ["prim", "adet"]].itertuples(index=False, name=None))


def aggregate(rows, start, end, region):
    groups = defaultdict(lambda: [0, 0])
    totals = defaultdict(lambda: [0, 0])
    cities = defaultdict(lambda: [0, 0])
    for m, c, city, premium, count, *_ in rows:
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
    hs = [h for h, _ in risks.values() if h is not None]
    fs = [f for _, f in risks.values() if f is not None]
    return (hp, freq, 1 + sum(h > hp for h in hs) if hp is not None else None,
            median(hs) if hs else None, median(fs) if fs else None)
