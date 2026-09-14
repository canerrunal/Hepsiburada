# Hepsiburada Ürün Veri Havuzu

Trendyol veri havuzu mimarisinin Hepsiburada karşılığıdır. Hepsiburada kategori ağacını her gece keşfeder, 5 pilot profilde (`elektronik`, `moda`, `supermarket`, `kozmetik`, `anne-bebek-oyuncak`) katmanlı stratejiyle ürün izler.

## Kapsam kararları (14 Eyl 2026)

- **Tüm ağaç x kategori başına 1000 tam detay günlük** tek Mac'te mümkün değildir (Hepsiburada ~32 ana kategori, milyonlarca ürün; kanıtlanmış kapasite günde ~6.000 detay). Bu yüzden **katmanlı ölçekleme** uygulanır.
- Her gün vitrin **ilk 40** alınır, 10 günlük dönüşümle kategori başına **1000'e** tamamlanır.
- Detay: shard başına günde **100 sabit + 700 dönüşümlü + 700 stok karşılaştırma** (Trendyol taksonomi bütçesiyle aynı).
- Pilot profillerde kalite kapısı: min **200 ürün** + `PASS` durumu, yoksa son geçerli rapor korunur.
- Çalışma penceresi: **22:00-06:00 Europe/Istanbul**, Hermes `no-agent` modunda, global kilitli.
- Hepsiburada ana sayfaya basit GET **403** döndürür; toplayıcı düşük hacimli çalışır, engelde veri uydurmaz, hata verir.

## Üretilen çıktılar

- `taxonomy/catalog.json` + `taxonomy/catalog.csv`: kategori ağacı (ad, kimlik, üst kategori, tam yol)
- `taxonomy/snapshots/YYYY-MM-DD/`: sıralama üyelikleri + tekilleştirilmiş ürün havuzu
- `categories/<profil>/data/history.csv`, `latest.csv/json`
- `categories/<profil>/snapshots/YYYY-MM-DD/`, `lists/YYYY-MM-DD/`, `reports/YYYY-MM-DD.md`
- `quality/latest.json` + `categories/<profil>/quality/latest.json`
- `reports/latest.md`, `reports/telegram-latest.txt` (Telegram kısa özet; bot hazır olunca gönderilir)

## Günlük çalışma

```bash
bash scripts/run_profile.sh elektronik
bash scripts/run_taxonomy_discovery.sh
```

Supabase (Veri Mimarı) yayını `VERI_MIMARI_INGEST_URL` + `VERI_MIMARI_INGEST_SECRET` tanımlanana kadar güvenli atlanır. Telegram gönderimi bot/kanal hazır olana kadar dosyada kalır.
