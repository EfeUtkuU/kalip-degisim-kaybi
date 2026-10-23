# Kalıp Değişim Kaybı

Kalıp değişimlerinde kaybedilen süreyi görmek ve azaltmak için ayrı bir masaüstü uygulaması (mevcut "Enjeksiyon Analiz" uygulamasına dokunmaz).

Sayfalar
- **Kayıp özeti** – toplam kayıp, makine/vardiya/gün/ay kırılımı, en çok kayıp yaratan kalıplar.
- **Plan karşılaştırması** – aynı talebi karşılamak için geçmiş düzen ile "tek kampanya / iki parti / dört parti" planlarının değişim sayısı ve süresi.
- **Saha kaydı** – kronometre ile adım adım (söküm, temizlik, montaj…) ölçüm ya da elle giriş; CSV dışa aktarım.
- **Hedef takibi** – hedef koy, haftalık ilerlemeyi izle.
- **Veri** – Excel dosyası ve dönem seçimi.

Derleme (macOS): `bash build_macos_app.sh` → `backend/dist/KalipDegisimKaybi.app` dosyasını Applications'a sürükle.
Geliştirme: `cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000` ve `cd frontend && npm i && npm run dev`.

Verilerin yeri: `~/Library/Application Support/KalipDegisimKaybi` (Excel kopyası, saha kayıtları, hedefler).

Dürüst notlar
- Excel'deki değişim sürelerinin %43'ü tam 60 dk; yuvarlak/varsayılan olabilir. Süresi girilmeyen değişimler makinenin ortancasıyla tahmin edilir ("tahmini").
- Plan karşılaştırması kuramsaldır: termin, stok, kalıp hazırlığı hesaba katılmaz. Uygulamadan önce üretim planlamayla kontrol edin.
- Gerçek ölçüm için Saha kaydı kullanılmalı; birkaç hafta sonra Excel'deki sürelerle karşılaştırılır.
