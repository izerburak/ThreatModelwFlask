# PROJE DEVİR NOTU — START HERE (güncelleme 2026-07-09)

> Yeni bir makinede/Claude Code oturumunda devam ederken **önce bunu**, sonra `RQ.txt`
> (kanonik GÜNCEL RQ seti; eski `RQ Ideas.txt` SİLİNDİ) ve `THESIS_PROJECT_CONTEXT.md`'yi oku.
> **Faz: kod DONDU, TEZ YAZIMI sürüyor.**
> ✅ `THESIS_PROJECT_CONTEXT.md` güncel V1 akışını yansıtıyor
> (eski extraction/`llm_risk_review`/MS-TMT-STRIDE-GPT/82-soru içeriği tamamen çıkarıldı).

## TEZ RESMÎ KÜNYE (main.tex — Sabancı `sabanci-template`, OTORİTE)
- **Title (EN):** *Automated Threat Modeling for LLM-Enabled Applications Using Local Large Language
  Models and DREAD Risk Assessment*
- **Başlık (TR):** *LLM-Destekli Uygulamalar için Yerel Büyük Dil Modelleri ve DREAD Risk
  Değerlendirmesi Kullanarak Otomatik Tehdit Modelleme*
- **Yazar:** Burak İzer · **Derece:** Master · **Program:** Cyber Security / Siber Güvenlik ·
  **Enstitü:** Graduate School of Engineering and Natural Sciences
- **Danışman:** Prof. Süha Orhun Mutluergil · **Jüri:** Assoc. Prof. Feyzullah Orçun Çetin,
  Asst. Prof. Julio Hernandez-Castro · **Onay tarihi:** 01-06-2026
- **Keywords (EN):** Threat modeling; LLM-enabled applications; Secure design; Automated DFD
  generation; DREAD risk assessment; OWASP Top 10 (LLM/Web/API); LLM grounding; **LoRA-based
  supervised fine-tuning**. → Fine-tune yöntemi = **LoRA** (SFT); anahtar kelime, ama merkezi RQ değil.
- **Tez yapısı (main.tex `\import`):** `Chapters/Introduction/Chapter/Introduction` →
  `Chapters/Chapter_2/Chapter/Chapter2` (background/related work) →
  `Chapters/Metodology/Chapter/Metodology`; ardından bibliography + `Chapters/Chapter_2/Appendix/Appendix2`.
  (Bu repo kökünde yalnız `thesis_intro_chapter1_v01.tex` var; asıl tez ağacı ayrı — muhtemelen Overleaf.)

**Resmî ABSTRACT (EN, ≤250 kelime — main.tex'ten):** Threat modeling provides significant value
during secure design, yet existing approaches remain difficult to apply because they often require
manual DFD construction, STRIDE expertise, and produce generic, weakly contextualized outputs —
amplified for LLM-enabled apps that combine web, API, and LLM components with overlapping attack
surfaces modeled through separate taxonomies. The thesis investigates a **deterministic-first,
questionnaire-driven** workflow for the combined attack surface of **generic** LLM-enabled
applications. A single adaptive **91-question** questionnaire drives automatic static DFD generation,
unified OWASP Web/API/LLM candidate-risk mapping, and **reproducible DREAD** scoring without manual
modeling. The deterministic layer is the authoritative core; a **constrained local LLM** only
enriches with system-specific threat descriptions, abuse paths, control gaps, and actionable
mitigations — it does not generate the DFD, compute severity, or introduce primary risks outside the
candidate set. A grounding validator removes hallucinated codes / non-existent DFD references.
Evaluation uses automatic structural metrics comparing deterministic fallback vs base local LLM vs an
**optionally fine-tuned** local LLM (same inputs): DFD integrity, risk coverage, grounding validity,
schema conformance, system-specificity, mitigation actionability, prevention of LLM-driven severity
changes. Even without the LLM, the deterministic fallback guarantees a valid risk output.
> ⚠️ **Tutarlılık:** abstract "optionally fine-tuned" ifadesini **değerlendirme** cümlesinde
> kullanıyor — bu OK ve tutarlı (fine-tune deneysel/opsiyonel). "optionally fine-tuned"ı yalnız
> **MAIN RQ**'dan çıkardık (intro §1.3); abstract'a dokunmaya gerek yok.
> **Definition — "generic LLM-enabled applications":** not restricted to a single vertical
> (healthcare/finance) but sharing web/API entry points, LLM orchestration, retrieval/memory, tool
> use, external services, logging/monitoring.

## TEZ YAZIM DURUMU (2026-07-07)
- **Bölüm 1 — Introduction: TASLAK YAZILDI** → `thesis_intro_chapter1_v01.tex` (motivasyon, 1.1
  Problem, 1.2 Proposed Approach, 1.3 RQ'lar [Main + RQ1–RQ4], 1.4 Contributions [7 madde — 6.
  sustainability update pipeline + 7. SFT dataset/fine-tuning eval eklendi], 1.5 Scope&Evaluation).
  Citation'lar `% TODO-CITE` olarak işaretli. Açık borç: DREAD-seçimi intro'da motive edilmemiş
  (STRIDE illüstratif; skorlama DREAD) — metodolojiye bırakılabilir.
- **Metodoloji 3.1–3.6** drafted+verified (bkz. `THESIS_PROJECT_CONTEXT` companion notlar).
- **Metodoloji 3.9 — "Model-Agnostic Local LLM Integration and Deterministic Resilience": YAZILDI**,
  kodla doğrulandı, sıkıştırıldı (16→~12 paragraf + resilience tablosu). Küçük rötuş notu: fallback'te
  deterministik mitigation her durumda iliştirilir (alternatif değil, taban).
- **Sıradaki:** 3.7 DREAD bölümü; intro citation'larını doldur.

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
tüm metrikler otomatik/yapısal. Ayrıntı: `RQ.txt` (GÜNCEL RQ seti) + RQ DURUMU bölümü.

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

## FINE-TUNE (repo DIŞI, deneysel — DOKUNMA) — RQ2 & RQ4'ün ortak mekanizması
> Not: fine-tuning artık tek bir RQ değil. **RQ2** = sabit bilgi setinde threat-ID etkinliğini
> iyileştirme; **RQ4** = aynı fine-tune mekanizmasını update pipeline'dan gelen YENİ tehdit bilgisini
> modele aktarmanın aracı olarak kullanma. İntroduction bu ikili rolü ayırıyor.
VALAR HPC'de koşacak. **GÜNCEL dataset (2026-07-06) = görev-bölünmüş, chat-format** — `training/`
altında (git'e yeni eklendi, untracked): `threatid_{3000,5000}.jsonl` (threat-ID görevi) +
`mitigation_{3000,5000}.jsonl` (mitigation görevi). İkisi de **fine-tune-READY** (dedup düzeltildi,
kayıtlar unique, 29 kod). ⚠️ **ESKİ `train_dread_{700,1500,2804}.json` ({input,output} risk-report
seti) ARTIK OBSOLETE — kullanma.**
- Fine-tune = iki LLM-destekli aşamayı (threat-ID + mitigation) deterministik-grounded artefaktlarla
  **distile** etmek (base modelin "her şey Critical→High" çöküşünü düzeltmek). Base model yerelde
  kalır; fine-tune remote, **karışma**.
- Açık notlar: `secondary_findings=0`; dağılım Critical-ağırlıklı.
- ⚠️ Dairesellik: değerlendirmede deterministik scorer'ı / aynı-dağılım etiketleri **gold-standard
  olarak kullanma** → trivial. Fine-tune sadece **yapısal conformance** (schema/grounding/actionability/
  system-specificity) + **held-out** ile ölçülür; "semantic kalite daha iyi" iddiası kapsam DIŞI
  (insan değerlendirmesi yok). SFT'de olmayan held-out test tut. (bkz. [[project-sft-dataset]])

## RQ DURUMU (GÜNCEL SET — kanonik metin `RQ.txt`, revize 2026-07-09)
> ⚠️ **2026-07-09 REFRAME:** RQ seti eski "deterministic-first pipeline + LLM ne katkı sağlar"
> çerçevesinden **LLM-merkezli**e çevrildi (bkz. [[feedback-local-llm-is-headline]]). Şema = **Main +
> RQ1–RQ4** (eski "RQ1 + RQ1.1–1.4" ve daha eski deterministic-first RQ1–RQ4 metni ARTIK OBSOLETE).
> Eski RQ1 (unified pipeline) ve RQ3 (guardrail) artık **RQ değil, contribution** (intro §1.4).
Master scope: **"bir açık vardı → tool ne ölçüde patchledi"**; "to what extent" kısmi/dürüst cevaba
izin verir. **Dış araç kıyası + insan değerlendirmesi YOK** (bkz. ÇIKIŞ NOKTASI). Özet:
- **MAIN:** To what extent can local Large Language Models improve the threat modeling process for
  LLM-integrated systems?
- **RQ1 (threat identification):** yerel LLM'ler, TM sürecinde LLM-entegre sistemlere karşı tehditleri
  ne ölçüde tanımlayabiliyor?
- **RQ2 (effectiveness improvement):** yerel LLM'lerin tehdit tanımlama etkinliği nasıl iyileştirilebilir?
  *(Mekanizma = supervised fine-tuning / LoRA.)*
- **RQ3 (mitigation generation):** yerel LLM'ler, tanımlanan tehditler için ne ölçüde ilgili mitigation
  stratejileri üretebiliyor?
- **RQ4 (sustainability — deneysel):** LLM-destekli TM aracı, ortaya çıkan yeni saldırı vektörleri ve
  değişen tehdit örüntüleriyle nasıl güncel tutulabilir? *(Güvenilir kaynaklardan gelen yeni tehdit/
  mitigation bilgisini görev-özel eğitim verisine çevirip yerel LLM'i periyodik güncelleyen update
  pipeline; grounding/traceability/reproducibility korunarak.)*
RQ1 & RQ3 = taşıyıcı (inşa edildi, otomatik ölçülebilir). RQ2 & RQ4 = fine-tuning'e dayanan deneysel
frontier (uzaktaki VALAR fine-tune; RQ2 = sabit bilgi setinde kalite, RQ4 = fine-tune'u YENİ bilgi
aktarımının aracı olarak kullanma). Eski RQ metni için `git log` / önceki commit'ler.

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
- Fine-tune'u VALAR'da koşmak (repo dışı, RQ2 & RQ4 — deneysel uzantı; sonuçsuz çıkarsa future work).
- (Minör, tez-opsiyonel) orchestrator catch-all fallback + JSON-parse-error yolu için doğrudan
  unit test yok; `.env.example`/`config.py` yok (flag'ler `app/__init__.py` + env).

## ÇALIŞMA TARZI NOTLARI (önceki oturumdan)
- LLM'i zayıf diye genelleme (model-agnostik; qwen3:8b'ye özel).
- Master tezi — PhD-seviyesi exhaustive kanıt dayatma; "ne ölçüde" kısmi cevaba izin verir.
- Üretilmiş artifact'ler (pipelines/, generated_models/) git'te tracked; yeni run'lar untracked düşer.
