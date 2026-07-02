# PROJE DEVİR NOTU — START HERE (2026-07-03)

> Yeni bir makinede/Claude Code oturumunda devam ederken **önce bunu**, sonra `RQ Ideas.txt`
> ("LOCKED RQ SET") ve `THESIS_PROJECT_CONTEXT.md`'yi oku. **Faz: kod DONDU, tez yazımı başlıyor.**
> ✅ `THESIS_PROJECT_CONTEXT.md` 2026-07-03'te sıfırdan temiz yazıldı — güncel V1 akışını yansıtıyor
> (eski extraction/`llm_risk_review`/MS-TMT-STRIDE-GPT/82-soru içeriği tamamen çıkarıldı).

## PROJE NEDİR
Flask tabanlı, **deterministik-first, anket güdümlü** tehdit modelleme aracı — LLM-tabanlı
uygulamalar için. Tek adaptif anketle OWASP **LLM + Web + API** risklerini birlikte:
**BUL → EŞLE → SKORLA (DREAD) → MİTİGE**. Yerel LLM (Ollama) opsiyonel yardımcı katman. Master tezi.

## ÇIKIŞ NOKTASI (motivasyon)
Mevcut TM araçları (örn. Microsoft Threat Modeling Tool, illüstratif örnek) hem **kullanımı zor**
(manuel DFD çizimi, STRIDE uzmanlığı, jenerik gürültü) hem **risk değerlendirmesinde zayıf** (her
elemana şablon tehdit, bağlama duyarlı önceliklendirme yok). Asıl boşluk: LLM tabanlı uygulamalar
aynı anda **Web + API + LLM** saldırı yüzeyini taşır, ama araçlar bunları ayrı taksonomi/akışlarla
ele alır; domain-specific çözümler (örn. healthcare) generalize olmaz. Tool buna cevap: **tek anketle,
birleşik, sisteme-yönelik, deterministik-first** bir akış.
⚠️ **Değerlendirme İÇSEL** (deterministic vs base LLM vs fine-tuned) — **dış araç kıyası YOK** (MS TMT
ve STRIDE GPT foil olarak DÜŞTÜ) ve **insan/uzman değerlendirmesi YOK** (kullanıcı test ettiremiyor);
tüm metrikler otomatik/yapısal. Ayrıntı: `RQ Ideas.txt` "LOCKED RQ SET".

## GÜNCEL DURUM (working tree, 115/115 test geçiyor — V1 uncommitted)
- Phases 1-4 + 91q DREAD migration + **V1 template-guided threat pipeline** (working tree'de, henüz
  push edilmedi). Son commit `24a1e8b` "Local Developments".
- **SKORLAMA = DETERMİNİSTİK DREAD** (`app/services/dread_scoring.py`). Her koda D/R/E/A/D (1-3),
  toplam 5-15; risk seviyesi DREAD **ORTALAMASINDAN** türetilir (`level_from_average`):
  **≥2.7 Critical / ≥2.2 High / ≥1.5 Medium / <1.5 Low** (eşdeğer total: 14-15 / 11-13 / 8-10 / 5-7).
  Anket cevaplarından; her kural okuduğu soruyu belgeliyor (izlenebilir). `score_code` →
  `block["band"] = level_from_average(average)` → `risk_level` HER ZAMAN buradan, ASLA LLM'den.
- **LLM UÇTAN UCA AKIŞ (V1):** `pipeline_orchestrator.run_risk_analysis` →
  1. DFD: `static_dfd_mapper.build_static_dfd_from_answers` (deterministik, LLM yok)
  2. `discover_candidate_risks` (deterministik aday kodlar, `risk_catalog`, LLM yok)
  3. `llm_threat_identification.identify_threats` (LLM/qwen3:8b, CHUNK'lı @ `LLM_THREAT_ID_CHUNK_SIZE`=10;
     primary `code` enum ile deterministik adaylara kilitli, node/edge id'leri gerçek DFD'ye kilitli)
  4. `threat_grounding_validator.validate_threats` (pure-Python: halüsinasyon id strip, aday-olmayan
     kodu secondary'ye demote, unknown-only ≠ confirmed, değinilmeyen adayları `unaddressed_candidates`
     olarak backfill)
  5. `score_validated_threats` → deterministik DREAD (yukarıdaki)
  6. `llm_mitigation_service.generate_mitigations` (LLM, BATCH'li @ `LLM_MITIGATION_BATCH_SIZE`=3,
     best-effort; yoksa statik `OWASP_MITIGATIONS` fallback)
- ⚠️ **Eski `llm_risk_review.py` (V0 tek-çağrılı review) 2026-07-02'de TAMAMEN SİLİNDİ** (dosya + testi +
  `LEGACY_LLM_RISK_REVIEW_ENABLED` flag'i). Artık kodda yok.
- Pipeline'dan **LLM EXTRACTION ÇIKARILDI** (`770f775`). **Garak backend de tamamen kaldırıldı.**
  (Manuel/lab yolu `/api/reactflow/from-extract` **kasıtlı duruyor** — pipeline değil.)
- ⚠️ **"Add Question" servisi 2026-07-03'te KALDIRILDI** (route `/add-question`, `add_question.html`,
  nav linki, `save_utils.append_question_to_catalog`/`_append_question_to_flow`/`append_question_to_layer`).
  Anket **91 soruda sabit**; çalışma-anında soru ekleme yolu bilinçli olarak yok (ortam bulanmasın).
- Sistem **LLM olmadan da tam çalışır**: Ollama down / herhangi bir exception ⇒ 5-katmanlı fallback
  zinciri orchestrator'ın catch-all'ında `_deterministic_risk_analysis`'e düşer ⇒ **her zaman geçerli
  risks.json** (`pipeline_mode=deterministic_fallback` + `pipeline_warning` damgalı). DREAD hiçbir
  koşulda LLM'e bağımlı değil.

## MODEL-AGNOSTİK (tezin satış noktası)
LLM katmanı tamamen model-bağımsız: `ollama_client.get_ollama_config` → `OLLAMA_MODEL` /
`OLLAMA_HOST`. Model değiştirmek tek satır config; tüm threat-ID+mitigation katmanı kod değişmeden
iyileşir. qwen3:8b base zayıf (uniform Critical→High) ama bu **modele özel, tasarıma değil**.
Büyük/uzak model = base'de bile iyi sonuç. Deterministik guardrail'ler model-swap'i güvenli kılar
(halüsinasyon geri gelmez). **LLM'i "zayıf" diye genelleme — qwen3:8b'ye özel.**

## FINE-TUNE (repo DIŞI, deneysel — DOKUNMA)
VALAR HPC'de koşacak. Dataset (`Desktop\training\`, repoda değil): `train_dread_{700,1500,2804}.json`
= 5004 kayıt, **aynı deterministik scorer'la** etiketli.
- Input: `{project_metadata, questionnaire_answers, deterministic_risks(sadece kodlar),
  extraction_payload, dfd_payload}`
- Output: `{overall_status, risk_summary, risks[...DREAD bloğu dahil...], quick_wins, ...}`
- Yani fine-tune = deterministik scorer'ı LLM'e **distile** etmek (base modelin "her şey Critical"
  çöküşünü düzeltmek). Base model yerelde kalır; fine-tune remote, **karışma**.
- ⚠️ Dairesellik: değerlendirmede deterministik scorer'ı / aynı-dağılım etiketleri **gold-standard
  olarak kullanma** → trivial. Fine-tune sadece **yapısal conformance** (schema/grounding/actionability/
  system-specificity) ile ölçülür; "semantic kalite daha iyi" iddiası kapsam DIŞI (insan değerlendirmesi
  yok). SFT'de olmayan held-out test tut.

## RQ DURUMU (tam kilitli metin `RQ Ideas.txt` → "LOCKED RQ SET", 2026-07-03)
Master scope: **"bir açık vardı → tool ne ölçüde patchledi"**; "to what extent" kısmi/dürüst cevaba
izin verir. **Dış araç kıyası + insan değerlendirmesi YOK** (bkz. ÇIKIŞ NOKTASI). Özet:
- **MAIN:** To what extent can a deterministic-first, questionnaire-driven pipeline model the combined
  Web, API, and LLM attack surface of generic LLM-enabled applications — deriving grounded DFDs and
  reproducible DREAD-based risk scores without manual modeling — and what additional value does a
  constrained, optionally fine-tuned local LLM contribute to threat identification and mitigation
  generation?
- **RQ1 (unified pipeline):** anket → otomatik DFD + OWASP Web/API/LLM birleşik mapping + deterministik DREAD.
- **RQ2 (LLM katkısı):** kısıtlı LLM, deterministik baseline'a sisteme-özgü tehdit + abuse_path/control_gap
  + daha actionable mitigation ekliyor mu (grounding korunarak)?
- **RQ3 (guardrail):** halüsinasyon kod / olmayan DFD referansı / desteksiz bulgu / LLM'in skoru değiştirmesi
  engelleniyor mu?
- **RQ4 (fine-tune sınırı, deneysel):** fine-tune mitigation conformance'ını (schema/evidence/actionability/
  specificity) base'e göre iyileştiriyor mu?
RQ1-RQ3 = taşıyıcı (hepsi inşa edildi, otomatik ölçülebilir); RQ4 = frontier (uzaktaki VALAR fine-tune).

## YENİ PC KURULUMU (temiz aktarım)
1. Repoyu klonla/kopyala. Python 3.12 (mevcut makinede 3.12).
2. venv: `python -m venv venv-win` → `venv-win\Scripts\activate` (Windows) veya `venv/bin/activate`.
3. `pip install -r requirements.txt` (saf Flask; LLM için ekstra Python paketi YOK — `ollama_client`
   düz HTTP/urllib kullanır. Frontend DFD editörü CDN'den React/React Flow çeker, npm adımı yok).
4. **Uygulamayı çalıştır:** `python run.py` → http://127.0.0.1:5000 (Flask debug). Anket = `/llm_sec`,
   pipeline = `/pipeline`, risk çıktısı = `/risk`.
5. **LLM (opsiyonel):** Ollama'yı ayrıca kur, `ollama pull qwen3:8b`, servis 127.0.0.1:11434'te ayakta
   olsun. Model/host değiştirmek için env: `OLLAMA_MODEL`, `OLLAMA_HOST`. **Ollama olmasa da araç tam
   çalışır** (deterministik fallback). Diğer tunable env'ler: `LLM_REQUEST_TIMEOUT`=400,
   `LLM_THREAT_ID_CHUNK_SIZE`=10, `LLM_MITIGATION_BATCH_SIZE`=3, flag'ler `app/__init__.py`'de.
6. **Durum JSON dosyalarında:** `responses/` (gitignored), `pipelines/`, `generated_models/dfd_runs/`.
   DB yok. Kanonik anket: `app/questions/questionsDb.json` (91 soru), akış `TM-Questions/QaT.txt`.

## DOĞRULAMA (testler)
Testler **unittest** (pytest DEĞİL). `tests/` içinde `__init__.py` YOK → importlib ile
`tests/test_*.py` yükleniyor. Çalıştır: **`python -m unittest discover -s tests -q`**. Şu an
**115/115 geçiyor**. Hızlı duman testi: `python -c "import app; app.create_app(); print('OK')"`.

## SON VERİFİKASYONLAR (2026-06-14 oturumu)
- Trial run `pipelines/20260614...-Codex-Trial-Public-RAG-Support/risks.json`: DREAD çıktısı
  **geçerli ve tutarlı** (30 risk, değerler 1-3, total=toplam, band=risk_level). Dağılım bu run'da
  High16/Medium14 (E/A/Dc sistem-maruziyeti sabit → tek senaryoda bant dar; geniş dağılım
  senaryolar-arası bir özellik).
- `risks.json` 23k satır = **bug değil**; aynı 30 riski 4 görünümde tutan verbose şema
  (`mapped_risks` + `mapped_risks_by_framework` + `owasp_llm/web/api` + `unified_risks`) +
  pretty-print. Redundancy zararsız; frontend tam test edilemediği için **sadeleştirilmedi** (bilerek).

## YARIM / SIRADAKİ
- **Akış DONDU — sıra TEZ YAZIMINDA** (2026-07-03). V1 pipeline working tree'de, testler yeşil.
  Kod commit'i **kullanıcıda** (push'u da hep kullanıcı yapar).
- Değerlendirme protokolünü yaz: her RQ → hangi deney → hangi otomatik metrik → hangi tablo (dış
  araç/insan yok; deterministic vs base LLM vs fine-tuned, çok-koşum + varyans).
- RQ1 için soru→OWASP eşlemesi hand-tagged → CWE/ASVS/ATLAS grounding + traceability matrisi (future
  work olarak da yazılabilir).
- Fine-tune'u VALAR'da koşmak (repo dışı, RQ4 — deneysel uzantı; sonuçsuz çıkarsa future work).
- (Minör, tez-opsiyonel) orchestrator catch-all fallback + JSON-parse-error yolu için doğrudan
  unit test yok; `.env.example`/`config.py` yok (flag'ler `app/__init__.py` + env).

## ÇALIŞMA TARZI NOTLARI (önceki oturumdan)
- LLM'i zayıf diye genelleme (model-agnostik; qwen3:8b'ye özel).
- Master tezi — PhD-seviyesi exhaustive kanıt dayatma; "ne ölçüde" kısmi cevaba izin verir.
- Üretilmiş artifact'ler (pipelines/, generated_models/) git'te tracked; yeni run'lar untracked düşer.
