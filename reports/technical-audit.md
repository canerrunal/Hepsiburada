# Hepsiburada Veri Merkezi Teknik Denetim ve Kapanış Raporu

## Kapsam

Hepsiburada akışı Trendyol’dan bağımsız namespace ile çalışır. Toplama yalnızca herkese açık kategori/listeleme/ürün sayfalarına dayanır; CAPTCHA, oturum, private API veya bot koruması aşma yöntemi kullanılmaz.

## Uygulanan mimari

- Listeleme adapter’ı: `scripts/hb_collect_pw.py`
- Ürün detay adapter’ı: `scripts/hb_detail_pw.py`
- Taxonomy keşfi: `scripts/hb_taxonomy_crawl.py`
- Taxonomy ürün/rank pipeline’ı: `scripts/hb_taxonomy_collect.py`
- Ürün ve kategori üyeliği ayrı NDJSON çıktıları
- 1.000 ürün hedefi ve kaynak yetersizliğinde `INSUFFICIENT_SOURCE`
- Candidate snapshot ve PASS sonrası atomic promote
- Alan kapsamı, duplicate, tarih, detay, stok ve yayın kalite kapısı
- Global lock, process-group timeout ve sinyal temizliği
- Dashboard durum sözleşmesi: `dashboard/status.json`
- Idempotent ingest başlıkları ve kaynak commit bilgisi

## Veri sözleşmesi

Ürün kaydı kimlik, varyant, teklif, satıcı, kategori, sıralama, fiyat, stok, puan, yorum, soru, kampanya, teslimat, kargo, zaman, kaynak ve hata metadata’sını destekler. Kaynak sayfada bulunmayan değerler `null` kalır; kalite raporunda kapsam olarak görünür.

## Kalite ve yayın kuralı

1. Collector candidate üretir.
2. Listing kalite kapısı çalışır.
3. Detay taraması candidate üzerinde çalışır.
4. Final kalite kapısı çalışır.
5. Yalnızca `PASS` candidate `latest` olur ve yayınlanır.
6. `FAIL`, `STALE` veya `INSUFFICIENT_SOURCE` durumunda son geçerli snapshot korunur.

## Bilinen operasyonel sınır

Hepsiburada erişim katmanı zaman zaman 403/güvenlik engeli döndürebilir. Bu durumda sistem bekleme/retry uygular, veri uydurmaz ve ilgili koşuyu başarısız veya yetersiz olarak raporlar.

## Doğrulama

- Python syntax/compile: başarılı
- Node syntax: başarılı
- Node testleri: başarılı
- Headless/ headed browser mode: doğrulandı
- Playwright cleanup: doğrulandı
- Ingest secrets yokken güvenli yayın atlama: doğrulandı
