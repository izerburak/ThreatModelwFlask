# PROJE DEVİR NOTU — START HERE (2026-06-14)

> Yeni bir makinede/Claude Code oturumunda devam ederken **önce bunu**, sonra
> `THESIS_PROJECT_CONTEXT.md` (Phase 4 banner'ı) ve `RQ Ideas.txt`'i oku. Bu dosya, büyük
> context dokümanının üstüne, en güncel durumu özetler.
> ⚠️ `THESIS_PROJECT_CONTEXT.md` §5 ve §9 hâlâ eski "LLM extraction" akışını anlatıyor — task A
> sonrası **stale**; aşağıdaki güncel durum geçerlidir.

## PROJE NEDİR
Flask tabanlı, **deterministik-first, anket güdümlü** tehdit modelleme aracı — LLM-tabanlı
uygulamalar için. Tek adaptif anketle OWASP **LLM + Web + API** risklerini birlikte:
**BUL → EŞLE → SKORLA (DREAD) → MİTİGE**. Yerel LLM (Ollama) opsiyonel yardımcı katman. Master tezi.

## ÇIKIŞ NOKTASI (motivasyon)
Mevcut TM araçları — başta **Microsoft Threat Modeling Tool** — hem **kullanımı zor** (manuel DFD
çizimi, STRIDE uzmanlığı, jenerik gürültü) hem **risk değerlendirmesinde zayıf** (her elemana şablon
tehdit, bağlama duyarlı önceliklendirme yok); LLM uygulamalarında daha da kötü (web+API+LLM yüzeyi bir
arada). Tool buna cevap: **kolay + yerel-LLM destekli + sisteme-yönelik + doğru risk hesaplayan**.
Başta OWASP geneliydi, sonra **LLM-tabanlı uygulamalara daraltıldı**. Foil = MS TMT (asıl),
STRIDE GPT (modern AI ikincil).

## GÜNCEL DURUM (commit'li, master, 68/68 test geçiyor)
- Phases 1-4 tamam (son commit `770f775` "Adding DREAD & Bug Fixes").
- **SKORLAMA = DETERMİNİSTİK DREAD** (`app/services/dread_scoring.py`). Her OWASP koduna D/R/E/A/D
  (1-3), toplam 5-15, bant: **14-15 Critical / 12-13 High / 9-11 Medium / 5-8 Low**. Anket
  cevaplarından; her kural okuduğu soruyu belgeliyor (izlenebilir). `risk_analysis_service.py:358` →
  `risk_level = dread["band"]`.
- **LLM pipeline'da DREAD SKORLAMAZ.** Sadece risk analizinden SONRA `llm_risk_review.py` ile:
  closed-set (risk uyduramaz) + grounded + temp 0 → advisory yorum (`assessed_level`, `rationale`) +
  **context-specific mitigation**. Deterministik `risk_level` baseline kalır; `risk.html` ikisini
  **yan yana** gösterir ("deterministic baseline: X" + "LLM review: Y").
- **MİTİGASYON = LLM-first**, yoksa statik `OWASP_MITIGATIONS` fallback.
- Pipeline'dan **LLM EXTRACTION ÇIKARILDI** (`770f775`): orchestrator artık `generate_dfd` →
  `run_risk_analysis`. **Garak backend de tamamen kaldırıldı.** (Manuel/lab yolu
  `/api/reactflow/from-extract` **kasıtlı duruyor** — pipeline değil.)
- Sistem **LLM olmadan da tam çalışır** (graceful fallback).

## MODEL-AGNOSTİK (tezin satış noktası)
LLM katmanı tamamen model-bağımsız: `ollama_client.get_ollama_config` → `OLLAMA_MODEL` /
`OLLAMA_HOST`. Model değiştirmek tek satır config; tüm review+mitigation katmanı kod değişmeden
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
  olarak kullanma** → trivial. Bağımsız referans + SFT'de olmayan held-out test gerekir.

## RQ DURUMU (tam metin `RQ Ideas.txt`'te)
Master scope: **"bir açık vardı → tool ne ölçüde patchledi"**. "to what extent" kısmi/dürüst cevaba
izin verir; limitation + future work meşru. İllüstratif kanıt yeter (adım/çaba karşılaştırması, vaka
çalışması, skor dağılımı); exhaustive user study / expert gold **zorunlu değil**.
Gold-standard/benchmark = **STRIDE GPT** (doğrulandı: STRIDE + DREAD + mitigation üretiyor; her ikisi
DREAD ürettiği için skorlama karşılaştırması direkt). İki eksen: **kullanılabilirlik + risk kalitesi**.

Finalize edilen RQ seti:
- **MAIN:** To what extent can an easy-to-use, questionnaire-driven, deterministic-first
  threat-modeling tool with optional local-LLM support overcome the usability and risk-assessment
  limitations of established tools (notably the Microsoft Threat Modeling Tool) for LLM-enabled
  applications?
- **RQ2 (usability):** vs MS TMT manuel DFD / uzmanlık ihtiyacı
- **RQ3 (risk-scoring accuracy):** deterministik DREAD vs MS TMT jenerik şablon + STRIDE GPT serbest skor
- **RQ4 (unified identify+map):** tek anket → OWASP LLM+Web+API birlikte (tek-taksonomi araçlara karşı)
- **RQ5 (reproducibility + local LLM + mitigation + hallucination):** model-bağımsız, tekrarlanabilir

## DOĞRULAMA / NASIL ÇALIŞTIRILIR
Testler **unittest** (pytest DEĞİL). `venv-win\Scripts\python.exe`. `tests/` içinde `__init__.py`
YOK → importlib ile `tests/test_*.py` yükleyip `unittest.TextTestRunner`. Şu an **68/68 geçiyor**.

## SON VERİFİKASYONLAR (2026-06-14 oturumu)
- Trial run `pipelines/20260614...-Codex-Trial-Public-RAG-Support/risks.json`: DREAD çıktısı
  **geçerli ve tutarlı** (30 risk, değerler 1-3, total=toplam, band=risk_level). Dağılım bu run'da
  High16/Medium14 (E/A/Dc sistem-maruziyeti sabit → tek senaryoda bant dar; geniş dağılım
  senaryolar-arası bir özellik).
- `risks.json` 23k satır = **bug değil**; aynı 30 riski 4 görünümde tutan verbose şema
  (`mapped_risks` + `mapped_risks_by_framework` + `owasp_llm/web/api` + `unified_risks`) +
  pretty-print. Redundancy zararsız; frontend tam test edilemediği için **sadeleştirilmedi** (bilerek).

## YARIM / SIRADAKİ
- `THESIS_PROJECT_CONTEXT.md` §5/§9 güncellenecek (extraction akışı stale).
- RQ2 için soru→OWASP eşlemesi hand-tagged, dayanaksız → CWE/ASVS/ATLAS grounding + traceability
  matrisi (future work olarak da yazılabilir).
- MS TMT "zor + zayıf risk" iddiasını **literatür atıflarıyla** desteklemek (tezin temel taşı).
- Değerlendirme protokolü (kaç senaryo, hangi metrik/tablo) henüz yazılmadı.
- Fine-tune'u VALAR'da koşmak (repo dışı).

## ÇALIŞMA TARZI NOTLARI (önceki oturumdan)
- LLM'i zayıf diye genelleme (model-agnostik; qwen3:8b'ye özel).
- Master tezi — PhD-seviyesi exhaustive kanıt dayatma; "ne ölçüde" kısmi cevaba izin verir.
- Üretilmiş artifact'ler (pipelines/, generated_models/) git'te tracked; yeni run'lar untracked düşer.
