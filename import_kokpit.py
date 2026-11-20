"""Build a validated report snapshot from the seven SBM exports."""
import argparse
import csv
import json
import os
import sys
from uuid import uuid4
from io import TextIOWrapper
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook
from engine import MONTHS

BRANCHES = ("Kasko", "Trafik")


def one(files, pattern):
    found = [p for p in files if pattern in p.name]
    if len(found) != 1:
        raise ValueError(f"{pattern}: beklenen 1 dosya, bulunan {len(found)}")
    return found[0]


def sheet(path):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        return list(book.active.values)
    finally:
        book.close()


def number(value):
    return Decimal(str(value).replace(",", ""))


def percent(value):
    if value is None:
        return None
    if isinstance(value, str) and value.endswith("%"):
        return float(number(value[:-1]))
    return float(number(value) * 100)


def named_examples():
    # The previous published extracts identify individual production rows in 2026.
    examples = defaultdict(set)
    for branch in BRANCHES:
        path = Path(__file__).parent / "data" / f"{branch}.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    key = (2026, branch, *(row[k] for k in ("Ay", "Plaka İl", "Araç Grubu", "Sigortalı Türü", "Tarife Basamak", "Yazılan Poliçe Adedi")), int(row["Yazılan Poliçe Primi"]))
                    examples[key].add(row["Sirket Adı"])
    return examples


def build(source, output):
    files = list(source.rglob("*.xlsx"))
    production = one(source.rglob("*.csv"), "YTD")
    groups = {b: defaultdict(lambda: [0, 0]) for b in BRANCHES}
    amounts, counts, row_counts = Counter(), Counter(), Counter()
    years = set()
    examples = named_examples()
    observed = defaultdict(set)
    with production.open(encoding="utf-16", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        header = next(reader)
        cols = [header.index(k) for k in ("Yıl", "Ay", "Ürün", "Şirket", "Plaka İl", "Araç Grubu", "Sigortalı Türü", "Yazılan Poliçe Adedi", "Yazılan Poliçe Primi", "Tarife Basamak")]
        for row in reader:
            year, month, branch, code, city, vehicle, person, n, p, tariff = (row[i] for i in cols)
            if branch not in groups:
                continue
            years.add(int(year))
            money = number(p or 0) * 100
            if money != int(money):
                raise ValueError(f"Kesirli kuruş: {reader.line_num}")
            sample = (int(year), branch, month, city, vehicle, person, tariff, n, round(money / 100))
            if sample in examples and abs(money) > 10000:
                observed[sample].add(code)
            key = (MONTHS.index(month)+1, *(sys.intern(t) for t in (code, city, vehicle, person)))
            item = groups[branch][key]
            item[0] += int(money)
            item[1] += int(n or 0)
            amounts[branch, code] += int(money)
            counts[branch, code] += int(n or 0)
            row_counts[branch] += 1
    if len(years) != 1:
        raise ValueError(f"Tek takvim yılı bekleniyor: {years}")
    evidence = defaultdict(Counter)
    for key, matched_codes in observed.items():
        if len(matched_codes) == len(examples[key]) == 1:
            evidence[key[1], next(iter(matched_codes))].update(examples[key])
    year = years.pop()
    meta = {"year": year, "branches": {}}
    snapshot = output.with_name(f".{uuid4().hex}.zip")
    try:
        with ZipFile(snapshot, "w", compression=ZIP_DEFLATED, compresslevel=8) as archive:
            for branch in BRANCHES:
                local = [f for f in files if f.name.startswith(branch)]
                reference = sheet(one(local, "Risk Adedi"))
                labels = reference[0]
                premium_col = next((i for i,k in enumerate(labels) if k and "prim" in k.lower() and "%" not in k), None)
                count_col = labels.index("Yazılan Poliçe Risk Adedi")
                values = amounts if premium_col is not None else counts
                index = defaultdict(list)
                for r in reference[1:]:
                    v = r[premium_col if premium_col is not None else count_col]
                    if v is not None:
                        index[number(v) * (100 if premium_col is not None else 1)].append(r[0].strip())
                codes = sorted(c for b,c in counts if b == branch)
                multiplicity = Counter(values[branch,c] for c in codes)
                metrics = {}
                for i,pattern in enumerate(("Prim Oranı", "Frekansı")):
                    records = sheet(one(local, pattern))
                    for name,val,y in records[1:]:
                        if int(y) == year:
                            metrics.setdefault(name.strip(), [None,None])[i] = percent(val)
                def normalize(s):
                    return s.removesuffix(" SİGORTA").strip()
                names, audit = {}, []
                direct = {normalize(c) for c in codes if not c.startswith("DİĞER")}
                for c in codes:
                    val = values[branch,c]
                    candidates = index[val]
                    name = normalize(c)
                    basis = "Kaynak adı"
                    if c.startswith("DİĞER"):
                        if val and multiplicity[val] == 1 and len(candidates) == 1 and normalize(candidates[0]) not in direct:
                            name = normalize(candidates[0])
                            basis = "Prim" if premium_col is not None else "Adet"
                        else:
                            basis = "Eşleşmedi"
                    votes = evidence[branch,c]
                    if len(votes) == 1 and c.startswith("DİĞER"):
                        example_name, hits = next(iter(votes.items()))
                        if hits >= 3 and example_name in {r[0] for r in reference[1:]}:
                            if basis != "Eşleşmedi" and name != example_name:
                                raise ValueError(f"{branch} {c}: prim ve adet eşleşmeleri çelişiyor")
                            if basis == "Eşleşmedi":
                                name = example_name
                                basis = f"Detay prim ve adet ({hits} kayıt)"
                    names[c] = name
                    audit.append([c,name,basis,counts[branch,c],amounts[branch,c]])
                if len(set(names.values())) != len(names):
                    raise ValueError(f"{branch}: çakışan şirket adı")
                metrics = {normalize(k):v for k,v in metrics.items()}
                rows = groups[branch]
                if not rows or sum(v[0] for v in rows.values()) != sum(amounts[branch,c] for c in codes) or sum(v[1] for v in rows.values()) != sum(counts[branch,c] for c in codes):
                    raise ValueError(f"{branch}: toplam kontrolü başarısız")
                with archive.open(f"{branch}.csv","w") as entry, TextIOWrapper(entry, encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["ay","şirket","il","araç","tür","kuruş","adet"])
                    for (month,code,city,vehicle,person),(money,n) in sorted(rows.items()):
                        writer.writerow([month,names[code],city,vehicle,person,money,n])
                meta["branches"][branch] = dict(rows=row_counts[branch],vehicles=sorted({k[3] for k in rows}),persons=sorted({k[4] for k in rows}),months=sorted({k[0] for k in rows}),risks=metrics,audit=audit)
                print(branch, row_counts[branch], Counter(r[2] for r in audit))
            archive.writestr("meta.json",json.dumps(meta,ensure_ascii=False))
        os.replace(snapshot,output)
    finally:
        snapshot.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Çıkartılmış Kokpit klasörü")
    parser.add_argument("--output",type=Path,default=Path(__file__).parent/"kokpit.zip")
    args = parser.parse_args()
    build(args.source,args.output)
