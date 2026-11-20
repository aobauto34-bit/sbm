# SBM üretim raporu

Kasko ve trafik üretimi YTD tablosundan okunur. Varsayılan portföy otomobil, kamyonet ve gerçek kişilerdir. Şirket düzeyindeki yıllık HP ve frekans, dört teknik Excel dosyasından gelir.

## Aynı tablolarla güncelleme

Arşivi bir klasöre çıkarın. YTD CSV dosyasıyla aynı döneme ait iki risk adedi ve dört teknik gösterge dosyasını birlikte kullanın.

```sh
python -m pip install -r requirements.txt
python import_kokpit.py Kokpit
python -m streamlit run app.py
```

İçe aktarma raporun kullandığı `kokpit.zip` dosyasını üretir. Yeni sürümü uygulama deposunda aynı konuma yükleyin. Paket her iki branş hazır olduğunda tek işlemde yenilenir.

Ad eşleştirmesi tüm il ve araç gruplarının branş toplamıyla yapılır. İsimli referansta yazılan prim varsa tekil prim eşleşmesi, yalnızca risk adedi varsa sıfırdan farklı tekil adet eşleşmesi aranır. 2026 için önceki isimli CSV dosyalarındaki il, ay, araç, kişi, basamak, adet ve tam TL'ye yuvarlanmış prim de kontrol edilir. En az üç ayrı tekil kaydın aynı şirketi göstermesi gerekir. Sonuç uygulamadaki **Şirket adı eşleştirmeleri** tablosunda görülebilir. Çözülemeyen kodlar prim ve adet toplamlarına dahildir.

Primler kuruş hassasiyetinde toplanır. Pazar payında payda seçili ay, il ve portföyün toplam primidir. HP ve frekans oranları araç ve il filtrelerinden bağımsızdır.
