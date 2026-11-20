import altair as alt
import pandas as pd
import streamlit as st

from engine import MONTHS, aggregate, changes, read_branch, risk_summary, stable

st.set_page_config(page_title="sbm · Üretim analizi", layout="wide")


def fmt(x, digits=2):
    if pd.isna(x):
        return "—"
    return f"{x:,.{digits}f}".translate(str.maketrans(",.", ".,"))


def pct(x):
    return "—" if pd.isna(x) else "%" + fmt(x)


@st.cache_data
def load_portfolio(branch):
    return read_branch(branch)


def table(records, labels):
    df = pd.DataFrame(records)
    if df.empty:
        st.info("Seçimde bu koşulu karşılayan kayıt yok.")
        return
    df = df[list(labels)].rename(columns=labels)
    formats = {}
    for col in df.select_dtypes("number"):
        if "%" in col:
            formats[col] = pct
        elif "puan" in col.lower():
            formats[col] = lambda x, signed=col != "Bant (puan)": ("+" if signed and x > 0 else "") + fmt(x)
        elif "TL" in col:
            formats[col] = lambda x, digits=2 if col.startswith("Ortalama prim") else 0: fmt(x, digits)
        else:
            formats[col] = lambda x: fmt(x, 0)
    st.dataframe(df.style.format(formats, na_rep="—"), hide_index=True, width="stretch",
                 height=min(760, 38 + 35 * len(df)))


st.sidebar.title("sbm")
branch = st.sidebar.radio("Branş", ["Trafik", "Kasko"], horizontal=True)
raw, risks = load_portfolio(branch)
vehicles = sorted({r[5] for r in raw})
persons = sorted({r[6] for r in raw})
vehicle = st.sidebar.multiselect("Araç grubu", vehicles, default=[v for v in ["OTOMOBİL", "KAMYONET"] if v in vehicles])
person = st.sidebar.multiselect("Sigortalı türü", persons, default=[v for v in persons if "GERÇEK" in v])
rows = [r for r in raw if r[5] in vehicle and r[6] in person]
if not rows:
    st.info("Bu araç grubu ve sigortalı türü seçiminde kayıt yok.")
    st.stop()
months = sorted({r[0] for r in rows})
cities = sorted({r[2] for r in rows})
region = st.sidebar.selectbox("Plaka ili", ["Tümü", "İSTANBUL", "İstanbul dışı"] + [c for c in cities if c != "İSTANBUL"])
st.title(f"{branch} · Üretim ve pazar payı")
st.caption(" · ".join(vehicle) + "  /  " + " · ".join(person) + f"  /  Plaka ili: {region}")
annual, details = st.tabs(["Şirket özeti", "Tablolar ve detaylar"])
with annual:
    st.subheader("Yıl içinde hangi şirket ne yaptı?")
    first_month, last_month = min(r[0] for r in raw), max(r[0] for r in raw)
    annual_panel, _, annual_geo = aggregate(rows, first_month, last_month, region)
    st.caption(f"2026 · {MONTHS[first_month-1]}–{MONTHS[last_month-1]} · Şirketler, ardışık iki ay arasındaki en büyük mutlak prim payı değişimine göre sıralanır. Payın paydası o ay seçili portföyde gözlenen toplam primdir.")
    if last_month == 11:
        st.caption("Kasım kapanışı doğrulanmadı. HP ve frekans branşta şirket başına tek değerdir. Aylık seyirleri kaynakta yer almıyor.")
    histories = {}
    for r in annual_panel:
        histories.setdefault(r["şirket"], []).append(r)
    movements = {name: changes(history) for name, history in histories.items()}
    order = sorted(histories, key=lambda name: (-max((abs(a["fark"]) for a in movements[name]), default=-1), name))
    if not order:
        st.info("Bu portföyde üretim kaydı yok.")
    active_names = [name for name in order if any(abs(move["fark"]) > 3 for move in movements[name])]
    st.write(f"**{len(order)} şirketin {len(active_names)} tanesinde** en az bir ayda 3 yüzde puanını aşan pay değişimi görüldü." if order else "")
    if active_names:
        st.write("Bu eşiği aşan şirketler hareket büyüklüğüne göre " + ", ".join(active_names) + ".")
    for name in order:
        history = histories[name]
        valid = [r for r in history if r["pay"] is not None]
        moves = movements[name]
        st.markdown(f"### {name}")
        if valid:
            peak = max(valid, key=lambda r: r["pay"])
            low = min(valid, key=lambda r: r["pay"])
            last = valid[-1]
            def observation(r):
                return f"{MONTHS[r['ay']-1]} ayında {pct(r['pay'])}"
            if len(valid) == last_month-first_month+1 and len(valid) >= 3 and peak["pay"]-low["pay"] <= 1:
                st.write(f"Payı dönem boyunca {pct(low['pay'])} ile {pct(peak['pay'])} arasında kaldı. Aylık ortalaması {pct(sum(r['pay'] for r in valid)/len(valid))}.")
            elif len(valid) > 1:
                st.write(f"İlk gözlenen pay {observation(valid[0])}. En yüksek pay {observation(peak)}, en düşük pay {observation(low)}. Son gözlenen pay {observation(last)}.")
            else:
                st.write(f"Tek gözlenen pay {observation(last)}.")
        notable = sorted([a for a in moves if abs(a["fark"]) > 3], key=lambda a: MONTHS.index(a["ay"]))
        if moves:
            events = notable or moves[:1]
            notes = []
            for move in events:
                verb = "yükseldi" if move["fark"] > 0 else "geriledi" if move["fark"] < 0 else "sabit kaldı"
                notes.append(f"{move['önceki_ay']} → {move['ay']} döneminde {pct(move['önceki_pay'])} → {pct(move['pay'])} ({fmt(abs(move['fark']))} puan) {verb}")
            st.write(("**3 puanı aşan hareketler**  " if notable else "**En büyük aylık hareket**  ") + ". ".join(notes) + ".")
        else:
            st.write("Aydan aya değişim hesaplamak için ardışık iki ayda karşılaştırılabilir pay bulunmuyor.")
        if moves:
            largest = moves[0]
            by_id = {r["ay"]: r for r in history}
            current = MONTHS.index(largest["ay"]) + 1
            before, after = by_id[current-1], by_id[current]
            st.write(f"En büyük pay hareketinin yaşandığı iki ayda yazılan prim {fmt(before['prim']/1e6)} milyon TL'den {fmt(after['prim']/1e6)} milyon TL'ye geldi.")
        if name in risks:
            hp, freq, rank, _, mf = risk_summary(risks, name)
            relative = "altında" if freq < mf else "üzerinde" if freq > mf else "aynı düzeyde"
            st.write(f"Branş genelinde frekansı {pct(freq)}, medyan ({pct(mf)}) ile karşılaştırıldığında {relative}. HP {pct(hp)} ile {len(risks)} şirket arasında yüksekten düşüğe {rank}. sırada.")
        cities_for_company = [(city, value[0]) for (company, city), value in annual_geo.items() if company == name]
        total = sum(premium for _, premium in cities_for_company)
        if total > 0 and len(cities_for_company) > 1:
            city, premium = max(cities_for_company, key=lambda item: item[1])
            st.caption(f"En fazla prim yazdığı il {city}. Seçili portföydeki şirket priminin {pct(100*premium/total)} kadarı bu ilden geldi.")
        by_month = {r["ay"]: r["pay"] for r in valid}
        st.caption(" · ".join(f"{MONTHS[m-1]} {pct(by_month.get(m))}" for m in range(first_month,last_month+1)))
        monthly_premium = pd.DataFrame(history).set_index("ay")["prim"].reindex(range(1, 13))
        chart_data = pd.DataFrame({
            "Ay": MONTHS,
            "Milyon TL": monthly_premium.to_numpy() / 1e6,
            "Prim": [fmt(value, 0) + " TL" if pd.notna(value) else "Veri yok" for value in monthly_premium],
        })
        premium_chart = alt.Chart(chart_data, title="Aylık yazılan prim").mark_bar().encode(
            x=alt.X("Ay:O", title=None, sort=MONTHS, scale=alt.Scale(domain=MONTHS),
                    axis=alt.Axis(labelAngle=-35, labelOverlap=False)),
            y=alt.Y("Milyon TL:Q", title="Milyon TL", axis=alt.Axis(
                labelExpr='replace(replace(replace(format(datum.value, ",.2~f"), /,/g, "~"), ".", ","), /~/g, ".")')),
            tooltip=["Ay:N", alt.Tooltip("Prim:N", title="Yazılan prim")],
        ).properties(height=170)
        st.altair_chart(premium_chart, width="stretch", key=f"prim_{name}")
        missing = [MONTHS[m-1] for m in monthly_premium.index[monthly_premium.isna()]]
        if missing:
            st.caption("Prim kaydı bulunmayan aylar: " + ", ".join(missing))
        st.divider()
with details:
    start, end = st.sidebar.select_slider("Detay tablolarının dönemi", options=months,
        value=(months[0], months[-1]), format_func=lambda n: MONTHS[n-1]) if len(months) > 1 else (months[0], months[0])
    panel, totals, geography = aggregate(rows, start, end, region)
    st.caption(f"2026  /  {MONTHS[start-1]} – {MONTHS[end-1]}  /  Plaka ili: {region}  ·  Paylar seçilen kapsamdaki dosya üretimine göredir.")
    if end == 11:
        st.caption("Kasım için ay sonu kapanışı doğrulanmadı. Aylık üretim tutarlarını bu kapsamda okuyun.")
    if not panel:
        st.info("Seçilen dönemde ve ilde kayıt yok.")
        st.stop()
    companies = sorted({r["şirket"] for r in panel})
    selected = st.sidebar.selectbox("İncelenen şirket", companies, index=companies.index("QUICK") if "QUICK" in companies else 0)
    focus = [r for r in panel if r["şirket"] == selected]
    alerts = changes(panel)
    p, n = (sum(x[i] for x in totals.values()) for i in (0, 1))
    a, b, c = st.columns(3)
    a.metric("Toplam yazılan prim", fmt(p/1e9) + " mlr TL")
    b.metric("Yazılan poliçe", fmt(n, 0))
    c.metric("Üretim kaydı olan şirket", len(companies))
    summary, overview, market, risk, geo = st.tabs(["Genel özet", "Şirket incelemesi", "Pay hareketleri", "HP ve frekans", "İl dağılımı"])
    # İl payının paydası aynı ayda, aynı ildeki tüm seçili üretimdir.
    frame = pd.DataFrame(rows, columns=["ay","şirket","il","prim","adet","araç","tür"])
    frame = frame[frame.ay.between(start, end)]
    if region == "İstanbul dışı":
        frame = frame[frame.il != "İSTANBUL"]
    elif region != "Tümü":
        frame = frame[frame.il == region]
    monthly = frame.groupby(["il","şirket","ay"], as_index=False).prim.sum()
    denom = monthly.groupby(["il","ay"]).prim.transform("sum")
    monthly["pay"] = 100 * monthly.prim / denom.where(denom != 0)
    period = f"{MONTHS[start-1]} → {MONTHS[end-1]}"
    def endpoints(data, keys):
        indexed = data.set_index(keys + ["ay"]).pay.unstack("ay")
        pair = pd.DataFrame({"ilk": indexed.get(start), "son": indexed.get(end)}, index=indexed.index)
        pair["fark"] = pair.son - pair.ilk if start < end else float("nan")
        return pair

    local = endpoints(monthly, ["il","şirket"]).join(frame.groupby(["il","şirket"]).prim.sum()).reset_index()
    local = local.sort_values("fark", key=lambda x: x.abs(), ascending=False, na_position="last")
    with summary:
        st.subheader("Şirketler bir bakışta")
        st.caption(f"Dönem toplamları ve ilk aydan son aya prim payı değişimi ({period}). Karşılaştırma için iki ayda da kayıt gerekir.")
        company = frame.groupby("şirket")[["prim","adet"]].sum().join(endpoints(pd.DataFrame(panel), ["şirket"]))
        company["dönem"] = 100 * company.prim / p if p else float("nan")
        company = company.sort_values("prim", ascending=False).reset_index()
        leader = company.iloc[0]
        st.write(f"Dönemin en yüksek üretimi {leader['şirket']} şirketinde. Yazılan prim {fmt(leader.prim,0)} TL, seçilen üretimdeki payı {pct(leader['dönem'])}.")
        for sign, title in [(1, "En fazla pay kazanan"), (-1, "En fazla pay kaybeden")]:
            matches = company[company.fark * sign > 0].sort_values("fark", ascending=sign < 0)
            if not matches.empty:
                hit = matches.iloc[0]
                st.write(f"{title} şirket {hit['şirket']} ({fmt(abs(hit.fark))} puan).")
        table(company.to_dict("records"), {"şirket":"Şirket","prim":"Dönem primi (TL)","adet":"Poliçe","dönem":"Dönem payı (%)","ilk":"İlk ay (%)","son":"Son ay (%)","fark":"Değişim (puan)"})
        st.subheader("İllerde şirket hareketleri")
        st.caption(f"{period} · Her şirketin il içindeki prim payı karşılaştırılır. En büyük mutlak değişimler üsttedir.")
        left, right = st.columns(2)
        places = left.multiselect("İlleri seç", sorted(local.il.unique()))
        names = right.multiselect("Şirketleri seç", companies)
        visible = local
        if places:
            visible = visible[visible.il.isin(places)]
        if names:
            visible = visible[visible.şirket.isin(names)]
        table(visible.to_dict("records"), {"il":"Plaka ili","şirket":"Şirket","prim":"Dönem primi (TL)","ilk":"İlk ay (%)","son":"Son ay (%)","fark":"Değişim (puan)"})
    with overview:
        st.subheader(f"{selected} · Dönem görünümü")
        first, last = focus[0], focus[-1]
        st.write(f"{MONTHS[first['ay']-1]} ayında {fmt(first['prim']/1e6)} milyon TL primle payı {pct(first['pay'])}.")
        valid = [r for r in focus if r["pay"] is not None]
        if len(valid) > 1:
            peak = max(valid, key=lambda r: r["pay"])
            low = min(valid, key=lambda r: r["pay"])
            st.write(f"En yüksek pay {MONTHS[peak['ay']-1]} ayında {pct(peak['pay'])}, en düşük pay {MONTHS[low['ay']-1]} ayında {pct(low['pay'])}. "
                     f"Son gözlem olan {MONTHS[last['ay']-1]} ayında üretim {fmt(last['prim']/1e6)} milyon TL, pay {pct(last['pay'])}.")
        swings = [r for r in alerts if r["şirket"] == selected]
        if swings:
            swing = swings[0]
            st.write(f"En büyük aylık hareket {swing['önceki_ay']}–{swing['ay']} döneminde görüldü. "
                     f"Pay {pct(swing['önceki_pay'])} seviyesinden {pct(swing['pay'])} seviyesine geldi ({fmt(swing['fark'])} puan).")
        if selected in risks:
            hp, freq, rank, mh, mf = risk_summary(risks, selected)
            st.info(f"Branş genelinde {selected} için frekans {pct(freq)}, şirket medyanı {pct(mf)}. "
                    f"HP {pct(hp)} ile {len(risks)} şirket içinde yüksekten düşüğe {rank}. sırada. Kaynak bu iki oranı şirket düzeyinde sabit veriyor.")
        compare = st.multiselect("Grafiğe şirket ekle", [c for c in companies if c != selected])
        metric = st.radio("Gösterge", ["Prim payı (%)", "Adet payı (%)", "Yazılan prim (milyon TL)", "Ortalama prim (TL)"], horizontal=True)
        field = {"Prim payı (%)":"pay","Adet payı (%)":"adet_payı","Yazılan prim (milyon TL)":"prim","Ortalama prim (TL)":"ortalama"}[metric]
        points = {(r["şirket"],r["ay"]):r for r in panel}
        chart_rows = []
        for company in [selected] + compare:
            for m in range(start,end+1):
                value = points.get((company,m),{}).get(field)
                chart_rows.append({"Ay":MONTHS[m-1],"Şirket":company,"Değer":value/1e6 if field=="prim" and value is not None else value})
        for row in chart_rows:
            v = row["Değer"]
            row["Gösterim"] = "—" if v is None else pct(v) if field in ("pay", "adet_payı") else fmt(v) + (" milyon TL" if field == "prim" else " TL")
        chart = alt.Chart(pd.DataFrame(chart_rows)).mark_line(point=True).encode(
            x=alt.X("Ay:O",sort=MONTHS[start-1:end],axis=alt.Axis(labelAngle=0)), y=alt.Y("Değer:Q",title=metric,axis=alt.Axis(labelExpr='replace(replace(replace(format(datum.value, ",.2f"), /,/g, "~"), ".", ","), /~/g, ".")')),
            color="Şirket:N", tooltip=["Ay","Şirket",alt.Tooltip("Gösterim:N",title=metric)])
        st.altair_chart(chart, use_container_width=True)
        table([dict(r, ay=MONTHS[r["ay"]-1]) for r in focus], {"ay":"Ay","prim":"Prim (TL)","pay":"Prim payı (%)","adet":"Poliçe","adet_payı":"Adet payı (%)","ortalama":"Ortalama prim (TL)"})
    with market:
        st.subheader("Aydan aya belirgin pay değişimleri")
        threshold = st.number_input("Mutlak değişim eşiği (yüzde puan)", 0.0, 100.0, 3.0, 0.25)
        jumps = [r for r in alerts if abs(r["fark"]) > threshold]
        st.caption(f"{len(jumps)} şirket-ay geçişi eşiği aşıyor. Artı değer pay kazanımını, eksi değer pay kaybını gösterir.")
        table(jumps, {"şirket":"Şirket","önceki_ay":"Önceki ay","ay":"Ay","önceki_pay":"Önceki pay (%)","pay":"Yeni pay (%)","fark":"Değişim (puan)"})
        st.subheader("Payını dar bir bantta koruyan şirketler")
        width = st.number_input("En yüksek ve en düşük pay arasındaki azami fark (puan)",0.0,100.0,1.0,0.25)
        st.caption("En az üç ay ve seçilen her ayda gözlem gerekir. Ortalama, aylık payların aritmetik ortalamasıdır.")
        table(stable(panel,end-start+1,width),{"şirket":"Şirket","ortalama":"Ortalama pay (%)","en_düşük":"En düşük (%)","en_yüksek":"En yüksek (%)","bant":"Bant (puan)"})
    with risk:
        st.subheader(f"{branch} · Şirketlerin HP ve frekans karşılaştırması")
        st.write("Kaynakta şirket başına tek HP ve tek frekans bulunuyor. Sıralama tüm branşı kapsar. HP ve frekans branş ve şirket düzeyindedir. Dönem, il, araç grubu ve sigortalı türü seçimleri bu oranları değiştirmez. Medyan her şirkete eşit ağırlık verir.")
        ranked = []
        for company in sorted(risks,key=lambda c:-risks[c][0]):
            hp, freq, rank, mh, mf = risk_summary(risks,company)
            ranked.append(dict(c=company,rank=rank,hp=hp,f=freq,d=hp-mh,g=freq-mf))
        table(ranked,{"rank":"HP sırası","c":"Şirket","hp":"HP (%)","f":"Frekans (%)","d":"HP medyanından fark (puan)","g":"Frekans medyanından fark (puan)"})
    with geo:
        st.subheader(f"{selected} · Üretimin yoğunlaştığı iller")
        city_totals = {}
        for (_,city),(prem,_) in geography.items():
            city_totals[city] = city_totals.get(city,0) + prem
        portfolio = sum(r["prim"] for r in focus)
        distribution = [dict(il=city,prim=val[0],adet=val[1],agirlik=100*val[0]/portfolio if portfolio else None,
                        pay=100*val[0]/city_totals[city] if city_totals[city] else None)
                        for (company,city),val in geography.items() if company == selected]
        distribution.sort(key=lambda x:-x["prim"])
        if portfolio:
            top = distribution[0]
            st.write(f"{top['il']} en yüksek prim üretilen il. Seçilen portföyün {pct(top['agirlik'])} kadarı bu ilde yazıldı.")
        table(distribution,{"il":"Plaka ili","prim":"Prim (TL)","adet":"Poliçe","agirlik":"Şirket portföyünde (%)","pay":"İl pazarında (%)"})
    with st.expander("Veri kapsamı ve hesaplama"):
        st.write(f"{branch}.csv dosyasında {fmt(len(raw),0)} satır var. Araç ve sigortalı seçiminde {fmt(len(rows),0)} satır kaldı. Yıl bilgisi 2026 olarak tanımlandı. "
                 "Prim payı, şirketin aylık yazılan priminin aynı ay ve coğrafyadaki toplam prime bölünmesiyle hesaplanır. "
                 "Adet payında aynı hesap poliçe adediyle yapılır. Ortalama prim toplam prim / toplam adettir. Negatif prim kayıtları hesaba dahildir. "
                 "Kayıt bulunmayan şirket-ay sıfıra çevrilmez. Pay hareketleri yalnızca ardışık iki takvim ayında gözlem varsa hesaplanır. "
                 "İstanbul dışı, dosyadaki YURTDIŞI dahil İstanbul haricindeki plaka kayıtlarını kapsar. "
                 "Hasar tutarı, kazanılmış prim ve maruziyet bulunmadığından sektörün teknik HP ve frekansı yeniden hesaplanamaz.")
