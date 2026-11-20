# sbm

2026 Ocak–Kasım Kasko ve Trafik üretimini şirket, ay ve plaka ili bazında inceleyen Streamlit uygulaması. Her iki CSV proje içindedir. Açılışta Trafik ve QUICK seçilidir.

## GitHub ve Streamlit

1. GitHub üzerinde `sbm` adlı bir depo oluşturun. ZIP içeriğini çıkarıp `app.py`, `engine.py`, `requirements.txt`, `.streamlit/` ve `data/` depo kökünde olacak şekilde yükleyin. Ham CSV dosyaları da depoya girer. Deponun görünürlüğünü paylaşım amacınıza göre seçin.
2. Streamlit Community Cloud üzerinde yeni uygulama oluşturun. GitHub deponuzu, yüklediğiniz dalı ve giriş dosyası olarak `app.py` seçin. Python 3.11 kullanabilirsiniz.
3. Uygulamayı başlatıp oluşan adresi paylaşın. Uygulama açılırken veri yükleme veya harici servis anahtarı gerektirmez.

## Yerelde çalıştırma

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Veriyi okurken

Her dosya 29.999 veri satırı içerir. Dosyaların sektörün tüm üretimini ne ölçüde kapsadığı bilinmiyor. Pazar paylarının paydası dosyada gözlenen prim toplamıdır. Seçilen il ve branş paydanın kapsamını belirler. Kasım ayının kapanış tarihi bulunmuyor. Kaynaktaki yuvarlanmış paylar toplanmaz.

Büyük hareket için başlangıç eşiği 3 yüzde puandır. Örneğin %10'dan %14'e hareket 4 puanlık artıştır. İstikrar listesi başlangıçta en yüksek ve en düşük aylık pay arasında en fazla 1 puan olan şirketleri gösterir. İki eşik de ekrandan değiştirilebilir.

Şirketlerin HP ve frekans değerleri her branşta şirket bazında tekrarlanır. Temmuz sonrasında teknik sonuçlarda değişim çıkarımı yapılamaz. Teknik gösterge tablosuyla üretim tablosu bu nedenle farklı dönem ayrıntısı taşır.
