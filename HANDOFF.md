# PROJE DEVİR NOTU - GÜNCEL DURUM

Son doğrulama: **19 Eylül 2026**

Repository: `C:\Users\user\Desktop\ThreatModelwFlask`

Branch: `master`

Son commit: `bbb8504` - `Adding tests for base model` (17 Eylül 2026)

Bu dosya mevcut repository, güncel `RQ.txt`, tez PDF'si, datasetler, benchmark
çıktıları ve çalışan testler birlikte incelenerek sıfırdan yazılmıştır. Eski handoff
bilgileri geçersizdir.

## 1. Otorite sırası

Çelişki olduğunda aşağıdaki sıra kullanılmalıdır:

1. Araştırma soruları ve deney niyeti için **`RQ.txt`**.
2. Uygulamanın gerçek davranışı için **aktif kod ve testler**.
3. Yeni deney datası için **`datasets/rq1_owasp31_survey/`** ve
   **`datasets/owasp_llm_2026_official/`**.
4. Yazılmış tez metninin durumunu görmek için
   **`Automated_Threat_Modeling_for_LLM_Enabled_Applications_Using_Local_Large_Language_Models_and_DREAD_Risk_Assessment.pdf`**.
5. `THESIS_PROJECT_CONTEXT.md`, eski `training/` dosyaları, eski pipeline koşuları
   ve eski benchmark çıktıları yalnız tarihsel bağlamdır; güncel gerçeğin üzerinde
   değildir.

## 2. Kısa yönetici özeti

- Uygulama çalışan, testli ve deterministic-first bir Flask tehdit modelleme
  pipeline'ıdır.
- Anket 91 sorudur ve iki soru veritabanı birebir aynıdır.
- Aktif LLM kataloğu **OWASP GenAI LLM Top 10:2026** sürümüne geçirilmiştir.
- Web kataloğu **OWASP Web Top 10:2025**, API kataloğu **OWASP API Security
  Top 10:2023** olarak kalmıştır.
- Güncel RQ1 bootstrap dataseti hazırdır: **31 sınıf x 50 = 1.550 kayıt**.
- OWASP LLM 2026 PDF'sinden ayrıca **63 resmî saldırı senaryosu, 72 yaygın risk
  örneği ve 96 mitigation** çıkarılmıştır.
- Tüm testler geçmektedir: **134/134**.
- Tez PDF'si 85 sayfa ve tüm ana bölümleri içerir; ancak araştırma soruları,
  dataset açıklaması ve Results bölümü güncel proje durumunun gerisindedir.
- Tezdeki 500/1000/1500 fine-tuning sonuçları yeni RQ1 dataseti için geçerli
  sonuçlar değildir. Bunlar eski 2025 LLM kodlu task-output datasetlerine dayanır.
- Yeni dataset ile ilk vanilla-vs-QLoRA koşusu 19 Eylül 2026'da Colab'da
  tamamlanmıştır. Run01 held-out testte %92,58 strict accuracy ve %92,42 macro
  F1 üretmiştir; ayrıntılar bu dosyanın 15. bölümündedir.

## 3. Güncel araştırma soruları

`RQ.txt` kanonik kaynaktır. Mevcut set şöyledir:

### RQ1 - Effectiveness improvement

**How can local LLM threat-identification effectiveness be improved?**

Ana deney: aynı sabit model/prompt üzerinde vanilla ve LoRA fine-tuned modelin
tehdit sınıflandırma performansını karşılaştırmak. Güncel kontrollü etiket uzayı:
OWASP LLM 2026 + Web 2025 + API 2023 + `NO_THREAT`.

### RQ2 - Mitigation generation

**To what extent can local LLMs generate relevant mitigation strategies?**

RQ1'e benzer vanilla/fine-tuned karşılaştırma yapılacak; ancak mitigation çıktısı
tek etiket sınıflandırması değildir. Senaryo, control gap ve uygulanabilir kontrol
arasındaki ilişki korunmalıdır.

### RQ3 - Sustainability / extraction fidelity

**Given an unstructured threat source (CVE description, vendor advisory, CTI
report), how accurately can the system extract structured threat entities (asset,
attack vector, technique, impact) and map them onto an existing threat taxonomy
(STRIDE, CAPEC, MITRE ATT&CK)?**

### RQ4 - Sustainability / model consistency over time

**As threats are added incrementally, does the threat model remain internally
consistent (no duplicate/contradictory nodes, correct risk re-scoring, no drift
from the original architecture) compared to a full from-scratch rebuild?**

### Tez PDF'siyle uyuşmazlık

Tez PDF'sindeki Section 1.3 hâlâ şu eski yapıyı kullanır:

- RQ1: threat identification capability,
- RQ2: effectiveness improvement,
- RQ3: mitigation generation,
- RQ4: genel sustainability/update pipeline.

Bu nedenle tez PDF'sindeki RQ numaraları ve RQ'lara verilen cevaplar güncel
`RQ.txt` ile eşleşmez. Yeni yazımda `RQ.txt` esas alınmalı ve Abstract,
Introduction 1.3, Contributions, Scope, Methodology, Results, Discussion ve
Conclusion birlikte güncellenmelidir. Sadece RQ başlıklarını değiştirmek yeterli
değildir.

## 4. Tezin mevcut yazılı durumu

İncelenen PDF:
`Automated_Threat_Modeling_for_LLM_Enabled_Applications_Using_Local_Large_Language_Models_and_DREAD_Risk_Assessment.pdf`

- 85 sayfa, A4, derlenme tarihi 10 Temmuz 2026.
- Kapak, Abstract/Özet, Introduction, Background, Methodology, Results,
  Discussion and Conclusion, Bibliography ve Appendix mevcut.
- Approval sayfasındaki tarih: **17 Temmuz 2026**.
- Repository içinde güncel TeX kaynak ağacı bulunmuyor. PDF'nin kaynakları başka
  yerde/Overleaf'te tutuluyor olmalı. Tez değişiklikleri bu repository'de doğrudan
  yapılamaz; güncel kaynak ağacı ayrıca temin edilmelidir.

### PDF'de iyi durumda olan bölümler

- 91 soruluk questionnaire-driven yaklaşım açık anlatılmış.
- Deterministik DFD, candidate mapping, grounding validator ve DREAD ayrımı net.
- LLM'nin DFD üretmediği ve severity hesaplamadığı doğru biçimde belirtilmiş.
- Local LLM threat identification ve mitigation rolleri metodolojik olarak
  sınırlandırılmış.
- Fine-tuning sonuç grafiklerinin PDF yerleşimi okunaklı ve görsel olarak sağlam.

### PDF'de güncellenmesi gereken kritik noktalar

1. **Araştırma soruları eski.** Section 1.3 ve RQ referanslı tüm bölümler güncel
   `RQ.txt` ile yeniden hizalanmalı.
2. **OWASP LLM sürümü açıkça 2026'ya sabitlenmeli.** Aktif kod ve yeni dataset
   `LLMxx:2026` kullanırken eski eğitim dosyaları bare `LLM01`-`LLM10` kodlarını
   kullanıyor.
3. **Section 3.10 ve Chapter 4'teki fine-tuning deneyi artık güncel RQ1 deneyini
   temsil etmiyor.** Yeni 31-sınıflı dataset sınıflandırma odaklıdır; mevcut tez
   sonuçları ise pipeline-format threat-ID/mitigation üretimini ölçmektedir.
4. **500/1000/1500 sonuçları yeniden değerlendirilmeden nihai kanıt olarak
   kullanılmamalı.** Repository'de training scripti, W&B exportu veya ham metric
   logları yoktur; yalnız `ft_commands.txt`, eski datasetler ve PDF'ye gömülü
   grafikler vardır. Sonuçlar mevcut repository'den tekrar üretilemiyor.
5. **Mitigation training datasında tekrar problemi var.** Eski mitigation
   dosyalarının benzersiz satır sayıları 500 için 329, 1000 için 552, 1500 için
   777'dir. Bu durum mevcut mitigation learning curve yorumlarını zayıflatır.
6. **Bibliography nihai değil.** Çok sayıda kaynakta PDF içinde doğrudan
   `Metadata incomplete`, `should be verified`, `unknown` ve `n.d.` notları
   görünmektedir. Teslimden önce bütün bibliyografik metadata doğrulanmalıdır.
7. Results bölümü yeni RQ3 extraction fidelity ve RQ4 incremental consistency
   deneylerini içermiyor.

## 5. Uygulamanın güncel teknik durumu

### Ana pipeline

Akış:

1. 91 soruluk adaptif questionnaire,
2. deterministic static DFD,
3. deterministic OWASP candidate-risk mapping,
4. local LLM threat identification,
5. pure-Python grounding validation,
6. deterministic DREAD scoring,
7. local LLM mitigation generation,
8. LLM başarısızsa deterministic fallback.

Temel servisler:

- `app/services/pipeline_orchestrator.py`
- `app/services/static_dfd_mapper.py`
- `app/services/risk_catalog.py`
- `app/services/llm_threat_identification.py`
- `app/services/threat_grounding_validator.py`
- `app/services/dread_scoring.py`
- `app/services/llm_mitigation_service.py`
- `app/services/risk_analysis_service.py`

Varsayılan local model `qwen3:8b`'dir. Model `OLLAMA_MODEL`, host
`OLLAMA_HOST` ile değiştirilebilir. Threat-ID chunk boyutu 10, mitigation batch
boyutu 3, varsayılan LLM timeout 400 saniyedir.

### OWASP sürümleri

- LLM: **2026**, kodlar `LLM01:2026` ... `LLM10:2026`.
- Web: **2025**, kodlar `A01:2025` ... `A10:2025`.
- API: **2023**, kodlar `API1:2023` ... `API10:2023`.

2026 LLM anlam sırası:

| Kod | Kategori |
|---|---|
| `LLM01:2026` | Prompt Injection |
| `LLM02:2026` | Sensitive Information Disclosure |
| `LLM03:2026` | Excessive Agency |
| `LLM04:2026` | Supply Chain |
| `LLM05:2026` | Data and Model Poisoning |
| `LLM06:2026` | Unbounded Consumption |
| `LLM07:2026` | Misinformation |
| `LLM08:2026` | Hidden Context Exposure |
| `LLM09:2026` | Vector and Embedding Weaknesses |
| `LLM10:2026` | Improper Output Handling |

Numaralar 2025'ten 2026'ya mekanik olarak taşınmamalıdır. Örneğin Excessive
Agency `LLM06` iken 2026'da `LLM03:2026`; Improper Output Handling `LLM05`
iken 2026'da `LLM10:2026` olmuştur.

### Questionnaire doğrulaması

- `app/questions/questionsDb.json`: 91 soru.
- `TM-Questions/questionsDb.json`: 91 soru.
- İki dosyanın SHA-256 hash'i aynıdır:
  `64d8fde4fb8afd75b4be17bdcad4b8685e636ce6ec8215007852307f9e551aab`.
- `TM-Questions/QaT.txt`: 91 adet `Q<number>` akış düğümü.

### Test durumu

Komut:

```powershell
python -m unittest discover -s tests -q
```

Son sonuç: **134 test, tamamı geçti**.

## 6. Dataset envanteri ve kararlar

### 6.1 Güncel RQ1 dataseti - kullanılacak

Klasör: `datasets/rq1_owasp31_survey/`

Ana dosya: `owasp31_survey_single_label.jsonl`

- 31 sınıf.
- Her sınıf 50 örnek.
- Toplam 1.550 kayıt.
- 10 LLM 2026 + 10 Web 2025 + 10 API 2023 + `NO_THREAT`.
- Train: 1.085.
- Validation: 155.
- Test: 310.
- Her sınıf için 35/5/10 split.
- 1.550 benzersiz ID ve 1.550 benzersiz `input_text`.
- Scenario group'lar split'ler arasında kesişmiyor.
- Aynı soru desenini güvenli cevaplarla aynalayan `NO_THREAT` hard negative'leri
  mevcut.
- Bütün kayıtlar `human_validated=false`.

Bu dataset **LoRA bootstrap deneyi için teknik olarak hazırdır**, fakat uzman
onaylı gerçek-world ground truth değildir. Tezde `survey-grounded synthetic
bootstrap dataset` olarak adlandırılmalıdır.

Önemli sınırlamalar:

- Tek etiket yaklaşımı Web/API/LLM örtüşmelerini sadeleştirir.
- Soru metinleri bazı kategori adlarını veya güçlü ipuçlarını taşır; yüksek
  in-distribution skor genelleme kanıtı değildir.
- Harici, farklı dille yazılmış ve eğitim üretiminden bağımsız bir test seti
  olmadan gerçek dünya başarısı iddia edilmemelidir.
- `A06:2025` datasette vardır; aktif app candidate catalogunda ayrı risk satırı
  değildir. Sınıflandırma deneyiyle uygulama pipeline çıktısı karıştırılmamalıdır.

### 6.2 OWASP LLM 2026 resmî kaynak havuzu - kullanılacak

Klasör: `datasets/owasp_llm_2026_official/`

- `official_attack_scenarios.jsonl`: 63 resmî saldırı senaryosu.
- `official_common_risk_examples.jsonl`: 72 resmî risk örneği.
- `official_mitigations.jsonl`: 96 resmî mitigation maddesi.
- `official_llm2026_catalog.json`: kategori bazlı tam çıkarım.
- Toplam 231 benzersiz kaynak kaydı, 10 LLM 2026 etiketi.
- Kaynak sayfaları, resmî URL ve CC BY-SA 4.0 lisansı kayıtlıdır.
- Extraction scripti deterministiktir; yeniden üretimde hash'ler aynı kalmıştır.

Bu dosyalar doğrudan nihai scenario-to-mitigation çiftleri değildir. Bir
kategorinin bütün mitigation'ları o kategorideki her senaryoya otomatik olarak
uygulanmamalıdır. Önce scenario control gap'i belirlenmeli, ilgili mitigation
seçilmeli ve eşleştirme gözden geçirilmelidir.

### 6.3 Eski `training/` datasetleri - yeni deneyde kullanılmayacak

Dosyalar:

- `training/threatid_{500,1000,1500}.jsonl`
- `training/mitigation_{500,1000,1500}.jsonl`

Durum:

- Bare 2025 LLM kodlarını kullanırlar; `LLMxx:2026` içermezler.
- 29 risk kodlu eski pipeline-output görev formatındadırlar.
- Threat-ID dosyalarında satırlar benzersizdir; mitigation dosyalarında yoğun
  tekrar vardır.
- Tez PDF'sindeki mevcut learning curves bu dataset ailesine aittir.
- Tarihsel kanıt olarak saklanabilirler; yeni RQ1/RQ2 deneyinde girdi olarak
  kullanılmamalıdırlar.

| Dosya | Satır | Benzersiz satır |
|---|---:|---:|
| `threatid_500.jsonl` | 500 | 500 |
| `threatid_1000.jsonl` | 1.000 | 1.000 |
| `threatid_1500.jsonl` | 1.500 | 1.500 |
| `mitigation_500.jsonl` | 500 | 329 |
| `mitigation_1000.jsonl` | 1.000 | 552 |
| `mitigation_1500.jsonl` | 1.500 | 777 |

## 7. RQ bazında gerçek ilerleme

### RQ1 - İlk kontrollü deney tamamlandı

Tamamlananlar:

- 31 sınıflı 1.550 kayıtlık dataset.
- Grup güvenli train/validation/test split.
- `NO_THREAT` hard negative dengesi.
- Aktif app kodlarının LLM 2026'ya taşınması.
- Base-model pilot benchmark scriptlerinin 2026 kodlarına güncellenmesi.
- Sabit Ministral 3 3B model/revision, prompt, split ve greedy decoding ile
  310 kayıtlık vanilla baseline.
- Aynı model üzerinde QLoRA Run01 eğitimi ve aynı held-out testte değerlendirme.
- Accuracy, macro/micro/weighted metrikler, sınıf bazlı metrikler, confusion
  matrix, prediction distribution, latency ve `NO_THREAT` analizi.
- Checkpoint, final adapter, ham tahminler ve run metadata'nın Google Drive'a
  kaydedilmesi.

Eksik olanlar:

- Overfit riskini azaltan, ayrı klasör ve run kimliği kullanan QLoRA Run02.
- Run01 ve Run02 için aynı test protokolünde doğrudan karşılaştırma grafikleri.
- Confidence skoru savunulabilir biçimde üretilirse PR/ROC; yoksa zorlanmamalı.
- En az bir bağımsız external test set.
- Colab hücrelerinin kalıcı training/evaluation scriptine dönüştürülmesi.

Not: RQ1'in güncel tanımı tek etiket threat classification deneyine uygundur.
Eski tezdeki uzun structured threat report generation metriği RQ1'in yerine
geçmez; ayrı bir pipeline-conformance deneyi olarak tutulabilir.

### RQ2 - Kaynak mitigation havuzu hazır, supervised pair set hazır değil

Hazır olanlar:

- OWASP LLM 2026'dan 96 resmî mitigation.
- Eski mitigation generation promptu ve pipeline servisi.
- Mitigation JSON şeması, target component, validation step ve evidence mapping
  alanları.

Eksik olanlar:

- Senaryo/control-gap -> doğru mitigation eşleştirmeleri.
- Uygulanamaz veya yanlış mitigation negatifleri.
- Train/validation/test split ve leakage kontrolü.
- Vanilla vs fine-tuned mitigation benchmarkı.
- `relevance` için savunulabilir gold label veya insan değerlendirme protokolü.

Eski mitigation datasetinin tekrar problemi çözülmeden mevcut sonuçlar RQ2
kanıtı olarak kullanılmamalıdır.

### RQ3 - Extraction prototipi var, fidelity deneyi yok

Hazır olanlar:

- `/sustainability` arXiv cs.CR taraması.
- Keyword filtreleme ve strong-candidate seçimi.
- Seçili arXiv abstract/full-text veya elle yapıştırılan metin için extraction UI.
- `paper-extraction.v1` JSON schema.
- Attack surface, mitigation ve source-exact evidence quote çıkarımı.
- Evidence quote'un kaynakta gerçekten bulunduğunu ve mitigation referanslarının
  geçerli attack-surface ID'lerine bağlandığını doğrulayan local validator.
- JSON ve chat-format JSONL export.
- Unit testler.

Sınırlamalar:

- Yalnız OpenAI provider adapterı uygulanmış; local model extraction benchmarkı
  yok.
- Canlı API başarısı bu oturumda doğrulanmadı; testler mock provider kullanıyor.
- `sustainability/extractions/` altında gerçek kaydedilmiş extraction run'ı yok.
- Güncel schema RQ3'teki asset/attack vector/technique/impact ve
  STRIDE/CAPEC/MITRE ATT&CK mapping alanlarının tamamını içermiyor.
- İnsan-annotated gold set, precision/recall/F1 ve taxonomy-mapping accuracy
  deneyi yok.

Dolayısıyla bu modül RQ3 için başlangıç prototipidir, RQ3 sonucu değildir.

### RQ4 - Deney taslağı var, uygulama/sonuç yok

Mevcut pipeline aynı questionnaire için deterministic DFD ve DREAD üretebilir;
bu RQ4 deneyinin kontrol temelini sağlar. Fakat incremental threat update ile full
rebuild karşılaştırmasını otomatik yürüten bir deney harness'i ve sonuç dosyası
yoktur.

Gerekli deney:

1. Başlangıç threat seti ve zaman sıralı yeni-threat paketleri tanımla.
2. Her adımda incremental update modeli ile sıfırdan rebuild modelini aynı
   architecture input üzerinde çalıştır.
3. Duplicate/contradictory node ve threat sayısı, DFD node/edge drift'i,
   candidate-risk farkı, DREAD re-score doğruluğu ve eski sınıflarda forgetting
   ölç.
4. Daha önce görülmeyen yeni threat setinde kazanımı ayrıca ölç.
5. Bütün adımlarda aynı split ailesini ve kaynak sürümünü koru.

## 8. Base-model pilot benchmark durumu

`LLM-Selection/` altında 11 Eylül 2026 tarihli 3B model pilotu bulunur:

- qwen2.5 3B,
- llama3.2 3B,
- ministral-3 3B.

Pilot 15 vaka x 3 tekrar kullanır ve eski LLM kod adlandırmasına dayanır. Sonuçta
Qwen timeout yaşamış; Ministral strict macro-F1 kuralıyla provisional winner,
Llama ise en iyi operasyonel profile sahip görünmüştür. Bu sonuç yalnız pilot
olarak kullanılmalıdır; 15 benzersiz vaka genel model seçimi için yeterli değildir.

Aktif benchmark scriptleri 2026 kodlarına taşınmıştır, fakat 16 Eylül tarihli
root metadata dosyasının yanında tamamlanmış yeni JSONL/summary bulunmamaktadır.
Bu nedenle 2026 migration sonrası benchmark tamamlanmış sayılmamalıdır.

## 9. Saklanan artifactlerin sürüm durumu

- `pipelines/20260627...` koşuları başarılı tarihsel pipeline artifactleridir.
- Bu koşular bare `LLM01`-`LLM10` kodlarını taşır ve LLM 2026 migration öncesidir.
- Güncel kod davranışının kanıtı olarak kullanılmadan önce aynı senaryo yeniden
  çalıştırılmalıdır.
- Eski benchmark ve pipeline JSON'ları silinmemelidir; tarihsel karşılaştırma için
  tutulabilir, fakat sonuç tablolarında sürümü açıkça belirtilmelidir.

## 10. Öncelikli yapılacaklar

1. **RQ setini tez kaynaklarında güncelle.** Abstract'tan Conclusion'a kadar RQ
   numaralarını ve iddiaları yeniden hizala.
2. **RQ1 Run02'yi koş.** Run01'i değiştirmeden ayrı run klasöründe daha güçlü
   regularization ve early stopping kullan; aynı held-out test protokolünü koru.
3. **External test set hazırla.** OWASP resmî senaryoları kullanılabilir; ancak
   bunlardan üretilen paraphrase'ler aynı scenario group içinde tutulmalı ve
   train-test sızıntısı yapılmamalıdır.
4. **RQ2 pairing dataseti oluştur.** Her scenario için control gap ve gerçekten
   ilgili mitigation seç; uzman/onay statüsünü kaydet.
5. **RQ3 schema ve benchmarkı RQ metnine göre genişlet.** Asset, attack vector,
   technique, impact ve taxonomy mappings ekle; gold extraction seti oluştur.
6. **RQ4 experiment harness'i yaz.** Incremental update ile full rebuild'i aynı
   kaynak snapshotları üzerinde karşılaştır.
7. **OWASP migration sonrası yeni pipeline ve model benchmark koşuları üret.**
8. **Tez Chapter 4'ü gerçek yeni deney sonuçlarıyla değiştir.** Eski learning
   curves yeni RQ1/RQ2 kanıtı olarak bırakılmamalıdır.
9. **Bibliography metadata'yı temizle.** PDF'de görünen placeholder notların hiçbiri
   final teslimde kalmamalıdır.
10. **Reproducibility paketi ekle.** Training scripti/config, random seed, exact
    base model revision, tokenizer, hardware, split hashes ve ham metric exportları
    repository'de veya tez ekinde bulunmalıdır.

## 11. Kurulum ve doğrulama

```powershell
python -m venv venv-win
venv-win\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Uygulama: `http://127.0.0.1:5000`

Önemli sayfalar:

- Survey: `/llm_sec`
- Pipeline: `/pipeline`
- Risk sonucu: `/risk`
- Sustainability scanner: `/sustainability`
- Paper extraction: `/sustainability/extract`

Local LLM için Ollama ayrıca kurulmalıdır. Varsayılan model `qwen3:8b`'dir.
Paper extraction için server environment'ta `OPENAI_API_KEY` gerekir; anahtar UI'ya
yazılmamalıdır.

Test:

```powershell
python -m unittest discover -s tests -q
```

Beklenen güncel sonuç: **134 test, OK**.

## 12. Working tree uyarısı

Working tree temiz değildir. Güncel değişiklikler arasında:

- `RQ.txt`,
- OWASP LLM 2026 catalog/scoring/template değişiklikleri,
- benchmark scriptlerinin 2026 kodlarına taşınması,
- ilgili test güncellemeleri,
- yeni `datasets/` klasörü,
- OWASP LLM 2026 PDF'si

bulunmaktadır. Kullanıcının mevcut değişiklikleri korunmalıdır. `git reset --hard`
veya toplu geri alma yapılmamalıdır. Commit/push kullanıcı kararıdır.

## 13. Tezde güvenle yapılabilecek ve yapılamayacak iddialar

### Güvenli iddialar

- Sistem 91 soruluk questionnaire'dan deterministic DFD ve OWASP candidate set
  üretir.
- DREAD severity LLM tarafından değil deterministik kurallarla hesaplanır.
- LLM çıktısı gerçek DFD ID'leri ve candidate codes ile sınırlandırılır ve local
  validator tarafından kontrol edilir.
- LLM olmadan deterministic fallback geçerli risk artifacti üretebilir.
- Güncel RQ1 dataseti dengeli, grup güvenli ve tekrar içermeyen sentetik bootstrap
  datasettir.
- OWASP LLM 2026 kaynak havuzu resmî PDF'ye izlenebilirdir.

### Şimdilik yapılmaması gereken iddialar

- Run01'in %92,58 test doğruluğunun bağımsız gerçek dünya genellemesini
  kanıtladığı. Bu yalnız survey-grounded sentetik bootstrap testindeki sonuçtur.
- 1.550 sentetik kaydın gerçek dünya tehdit sınıflandırmasını kanıtladığı.
- Mitigation'ların uzman düzeyinde doğru veya ilgili olduğu.
- RQ3 extraction'ın insan anotasyonuna göre yüksek fidelity sağladığı.
- Incremental update'in full rebuild kadar tutarlı olduğu.
- Temmuz PDF'sindeki 500/1000/1500 grafiklerinin güncel deney setini temsil ettiği.
- Eski LLM 2025 artifactlerinin LLM 2026 ile doğrudan karşılaştırılabilir olduğu.

## 14. Hızlı başlangıç - bir sonraki oturum

Bir sonraki çalışma şu sırayla başlamalıdır:

1. `HANDOFF.md` ve `RQ.txt` oku.
2. `datasets/rq1_owasp31_survey/README.md` ve
   `datasets/owasp_llm_2026_official/README.md` oku.
3. `python -m unittest discover -s tests -q` çalıştır.
4. Bölüm 15'teki Run01 kimliğini ve Drive artifactlerini kontrol et.
5. Run02'yi yeni bir experiment ID ve klasörle başlat; Run01 klasörüne yazma.
6. Model, dataset, prompt, split, seed ve decoding'i sabit tut; kontrollü deney
   için aynı anda gereksiz sayıda hiperparametre değiştirme.
7. Her deney çıktısına dataset hash'i, model revision, seed, parametreler ve
   timestamp yaz.

## 15. RQ1 Colab Run01 - 19 Eylül 2026

Colab defteri: `TrainingTestv1.ipynb`

Base model:

- `mistralai/Ministral-3-3B-Instruct-2512-BF16`
- Revision: `b6d637bef2393152b3da2b2fde72eecdee30557e`
- 4-bit NF4, double quantization, FP16 compute
- Tesla T4 14,56 GB

Dataset ve protokol:

- SHA-256: `444e14e0c05510edc113b40942d63d95c3db782a562b0a58e3001b68e147c1d8`
- 1.085 train, 155 validation, 310 held-out test
- 31 dengeli sınıf
- Maksimum sequence length 1.024; hiçbir kayıt truncate edilmedi
- Aynı classification promptu ve greedy decoding kullanıldı

QLoRA parametreleri:

- Rank 16, alpha 32, dropout 0,05
- 182 target module; yalnız language model katmanları
- 24.707.072 trainable parameter
- Micro batch 1, gradient accumulation 16, effective batch 16
- Learning rate `1e-4`, weight decay 0,01, cosine scheduler
- 11 warmup step, 3 epoch, seed 42
- `paged_adamw_8bit`, gradient checkpointing
- LoRA trainable ağırlıkları FP32; base model 4-bit kaldı

Validation eğrisi:

| Epoch | Training loss | Validation loss | Mean token accuracy |
|---:|---:|---:|---:|
| 1 | 0,048324 | 0,041527 | 0,980018 |
| 2 | 0,019340 | 0,024447 | 0,991326 |
| 3 | 0,004921 | 0,027719 | 0,991326 |

Epoch 3'te validation loss yükseldiği için hafif overfit gözlendi. En iyi model
epoch 2 / `checkpoint-136` idi. `load_best_model_at_end=True` nedeniyle
`final_adapter` bu en iyi checkpointi içerir. `checkpoint-204` epoch 3 sonunu da
korur.

Held-out test sonuçları:

| Koşul | Strict accuracy | Macro F1 | Invalid output rate | NO_THREAT hata |
|---|---:|---:|---:|---:|
| Vanilla | 0,058065 | 0,028429 | 0,145161 | 8/10 |
| QLoRA Run01 | 0,925806 | 0,924211 | 0 | 0/10 |

Run01 toplam 310 test kaydının 287'sini doğru, 23'ünü yanlış sınıflandırdı. Bu
sonuç sentetik in-distribution held-out test için geçerlidir; bağımsız external
test olmadan gerçek dünya genellemesi olarak sunulmamalıdır.

Kanonik experiment ID:

`rq1_run01_r16_a32_d0p05_lr1e-4_eb16_ep3_seed42`

Google Drive hedef klasörü:

`/content/drive/MyDrive/ThreatModelwFlask/experiments/rq1_run01_r16_a32_d0p05_lr1e-4_eb16_ep3_seed42/`

Son doğrulanan gerçek klasör runtime disconnect öncesinde hâlâ şuydu:

`/content/drive/MyDrive/ThreatModelwFlask/experiments/ministral3_3b_owasp31_qlora/`

Parametreli klasöre taşıma/arşivleme hücresinin başarıyla tamamlandığı kullanıcı
çıktısıyla doğrulanmadı. Yeni oturum önce iki yolu salt-okuma kontrol etmeli; eski
klasör varsa yalnız Drive içi yeniden adlandırma ve manifest üretimi yapmalıdır.
Bu işlem eğitim gerektirmez.

Klasörde `run_manifest.json`, `hyperparameters.json`, `metrics_summary.json`,
training history, ham test tahminleri, per-class metrikler, confusion matrix,
checkpointler ve `final_adapter/` birlikte tutulmalıdır. Runtime disconnect
olmuştur; yeni oturumda Run01 yeniden eğitilmemeli veya üzerine yazılmamalıdır.

Run02 planı:

- Ayrı experiment ID ve Drive klasörü kullan.
- Overfit riskini validation tabanlı early stopping ile sınırla.
- Run01'e göre kontrollü parametre değişikliği yap; model, revision, dataset,
  split, prompt, seed ve test decoding aynı kalsın.
- Run02 tamamlanınca aynı 310 kayıtlık test protokolüyle ölç ve Run01/Run02
  grafikleri üret.
