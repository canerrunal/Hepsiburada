# Hepsiburada Ürün Veri Merkezi

Marketplace bağımsız veri sözleşmesi, Hepsiburada Playwright adapter’ı, taxonomy ürün pipeline’ı, kalite kapısı ve idempotent yayın akışı içerir.

## Kapsam kararları (14 Eyl 2026)

- Profil hedefi kategori başına **1.000 benzersiz ürün**; kaynak kapasitesi yetersizse `INSUFFICIENT_SOURCE` raporlanır.
- Detay taraması günlük en yüksek sıralı **300 ürün** ile başlar; eski ürünler dönüşümlü ele alınır.
- Candidate snapshot kalite kapısından geçmeden `latest` üzerine yazılmaz; başarısız çalışmada son geçerli veri korunur.
- Taxonomy ürünleri `products.ndjson.gz` ve kategori üyelik/sıralamaları `rankings.ndjson.gz` olarak ayrı tutulur.
- Çalışma penceresi Europe/Istanbul, Hermes `no-agent` ve global kilit ile yönetilir.
- Hepsiburada ana sayfaya basit GET **403** döndürür; toplayıcı düşük hacimli çalışır, engelde veri uydurmaz, hata verir.

## Üretilen çıktılar

- `taxonomy/catalog.json` + `taxonomy/catalog.csv`: kategori ağacı (ad, kimlik, üst kategori, tam yol)
- `taxonomy/snapshots/YYYY-MM-DD/`: `products.ndjson.gz`, `rankings.ndjson.gz`, shard ve final özetleri
- `dashboard/status.json`: profil/taxonomy/yayın durum sözleşmesi
- `categories/<profil>/data/history.csv`, `latest.csv/json`
- `categories/<profil>/snapshots/YYYY-MM-DD/`, `lists/YYYY-MM-DD/`, `reports/YYYY-MM-DD.md`
- `quality/latest.json` + `categories/<profil>/quality/latest.json`
- `reports/latest.md`, `reports/telegram-latest.txt` (Telegram kısa özet; bot hazır olunca gönderilir)

## Operasyonel mimari

- Her shard ve profil koşusu `scripts/run_with_timeout.py` üzerinden çalışır; süreç grubu, timeout ve sinyal kapanışı birlikte yönetilir.
- Koşu manifestleri `.runtime/runs/YYYY-MM-DD/*.json` altında tutulur. Bu klasör git dışıdır; `dashboard/status.json` aktif, tamamlanmış ve stale koşuları buradan izler.
- Katalog ve özet dosyaları atomik yazılır. Yarım kalmış JSON/CSV/GZIP çıktısı son geçerli snapshot'ın üzerine geçemez.
- Ürün toplama, taxonomy katalog durumu `PASS/COMPLETE`, dokuz kök kategori ve dolu kök kimlikleri doğrulanmadan başlayamaz.
- Taxonomy merge aynı tarihli ve tamamlanmış shard'ları kabul eder; eksik kök, uyumsuz tarih veya açık kuyrukta `IN_PROGRESS` bırakır.
- Dashboard; ana katalog ile shard keşiflerini ayrı gösterir. Shard satırları ürün üyelik satırlarıyla karıştırılmaz.
- Taxonomy ürün hedefi kökün alt kategori sayısına göre dinamik seçilir: `>1000 = 4.000`, `500–999 = 2.500`, `<500 = 2.000` benzersiz ürün.

## Günlük çalışma

```bash
bash scripts/run_profile.sh elektronik
bash hermes/hepsiburada_discovery.sh
node scripts/build_dashboard_status.cjs
```

Yayın `VERI_MIMARI_INGEST_URL` + `VERI_MIMARI_INGEST_SECRET` ile etkinleşir. Her gönderim profil/tarih/içerik tabanlı `Idempotency-Key` taşır. Telegram gönderimi yapılandırılana kadar dosyada kalır.
