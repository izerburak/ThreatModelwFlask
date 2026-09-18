# RQ1 OWASP-31 Survey Dataset

Bu klasör, RQ1 için LoRA öncesi başlangıç veri setini içerir. Veri seti,
projedeki `app/questions/questionsDb.json` anketinin soru ve seçeneklerinden
deterministik olarak üretilmiştir.

Bu sürüm bir **survey-grounded synthetic bootstrap dataset**'tir. İnsan uzmanlar
tarafından henüz onaylanmış bir ground-truth veri seti değildir. Tez deneyinde
kullanılmadan önce özellikle birden fazla OWASP kategorisine uyabilecek kayıtlar
uzmanlarca incelenmelidir.

## Kapsam

- OWASP Top 10 for LLM Applications: 2026 — 10 etiket
- OWASP Top 10 Web Application Security Risks: 2025 — 10 etiket
- OWASP API Security Top 10: 2023 — 10 etiket
- `NO_THREAT` — 1 etiket
- Her etiket için 50 kayıt
- Toplam: **31 × 50 = 1.550 kayıt**

Kullanılan OWASP sürümleri:

- <https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/>
- <https://top10.owasp.org/2025/>
- <https://api-security.owasp.org/editions/2023/en/0x00-header/>

## Dosyalar

- `owasp31_survey_single_label.jsonl`: 1.550 eğitim/değerlendirme kaydı
- `label_catalog.json`: etiket sırası, adı, sürümü ve global kayıt aralığı
- `generate_dataset.py`: aynı veri setini deterministik olarak yeniden üretir

Yeniden üretmek için proje kökünde:

```powershell
python datasets\rq1_owasp31_survey\generate_dataset.py
```

## ID ve etiket aralıkları

| Global sıra | Kayıt ID aralığı | Etiket | Tehdit |
|---:|---|---|---|
| 1–50 | `OWASP31-0001`–`OWASP31-0050` | `LLM01:2026` | Prompt Injection |
| 51–100 | `OWASP31-0051`–`OWASP31-0100` | `LLM02:2026` | Sensitive Information Disclosure |
| 101–150 | `OWASP31-0101`–`OWASP31-0150` | `LLM03:2026` | Excessive Agency |
| 151–200 | `OWASP31-0151`–`OWASP31-0200` | `LLM04:2026` | Supply Chain |
| 201–250 | `OWASP31-0201`–`OWASP31-0250` | `LLM05:2026` | Data and Model Poisoning |
| 251–300 | `OWASP31-0251`–`OWASP31-0300` | `LLM06:2026` | Unbounded Consumption |
| 301–350 | `OWASP31-0301`–`OWASP31-0350` | `LLM07:2026` | Misinformation |
| 351–400 | `OWASP31-0351`–`OWASP31-0400` | `LLM08:2026` | Hidden Context Exposure |
| 401–450 | `OWASP31-0401`–`OWASP31-0450` | `LLM09:2026` | Vector and Embedding Weaknesses |
| 451–500 | `OWASP31-0451`–`OWASP31-0500` | `LLM10:2026` | Improper Output Handling |
| 501–550 | `OWASP31-0501`–`OWASP31-0550` | `A01:2025` | Broken Access Control |
| 551–600 | `OWASP31-0551`–`OWASP31-0600` | `A02:2025` | Security Misconfiguration |
| 601–650 | `OWASP31-0601`–`OWASP31-0650` | `A03:2025` | Software Supply Chain Failures |
| 651–700 | `OWASP31-0651`–`OWASP31-0700` | `A04:2025` | Cryptographic Failures |
| 701–750 | `OWASP31-0701`–`OWASP31-0750` | `A05:2025` | Injection |
| 751–800 | `OWASP31-0751`–`OWASP31-0800` | `A06:2025` | Insecure Design |
| 801–850 | `OWASP31-0801`–`OWASP31-0850` | `A07:2025` | Authentication Failures |
| 851–900 | `OWASP31-0851`–`OWASP31-0900` | `A08:2025` | Software or Data Integrity Failures |
| 901–950 | `OWASP31-0901`–`OWASP31-0950` | `A09:2025` | Security Logging and Alerting Failures |
| 951–1000 | `OWASP31-0951`–`OWASP31-1000` | `A10:2025` | Mishandling of Exceptional Conditions |
| 1001–1050 | `OWASP31-1001`–`OWASP31-1050` | `API1:2023` | Broken Object Level Authorization |
| 1051–1100 | `OWASP31-1051`–`OWASP31-1100` | `API2:2023` | Broken Authentication |
| 1101–1150 | `OWASP31-1101`–`OWASP31-1150` | `API3:2023` | Broken Object Property Level Authorization |
| 1151–1200 | `OWASP31-1151`–`OWASP31-1200` | `API4:2023` | Unrestricted Resource Consumption |
| 1201–1250 | `OWASP31-1201`–`OWASP31-1250` | `API5:2023` | Broken Function Level Authorization |
| 1251–1300 | `OWASP31-1251`–`OWASP31-1300` | `API6:2023` | Unrestricted Access to Sensitive Business Flows |
| 1301–1350 | `OWASP31-1301`–`OWASP31-1350` | `API7:2023` | Server Side Request Forgery |
| 1351–1400 | `OWASP31-1351`–`OWASP31-1400` | `API8:2023` | Security Misconfiguration |
| 1401–1450 | `OWASP31-1401`–`OWASP31-1450` | `API9:2023` | Improper Inventory Management |
| 1451–1500 | `OWASP31-1451`–`OWASP31-1500` | `API10:2023` | Unsafe Consumption of APIs |
| 1501–1550 | `OWASP31-1501`–`OWASP31-1550` | `NO_THREAT` | Somut tehdit sinyali yok |

## Train, validation ve test bölünmesi

Her pozitif sınıftaki 50 kayıt, aynı yapısal örneğin yakın varyantlarının farklı
bölümlere sızmasını önlemek için 10 adet `scenario_group` altında üretilmiştir.
Her pozitif grupta 5 varyant bulunur.

`NO_THREAT` sınıfı 30 pozitif OWASP ailesinin soru desenini ayrı ayrı aynalayan
30 hard-negative gruptan oluşur. Bu gruplarda 1 veya 2 güvenli cevap varyantı
vardır. Böylece model yalnızca belirli bir sorunun varlığına bakarak
`NO_THREAT` kararı veremez.

Her etiketin kendi 50 kayıtlık aralığında:

- İlk 35 kayıt: `train` — grup 1–7
- Sonraki 5 kayıt: `validation` — grup 8
- Son 10 kayıt: `test` — grup 9–10

Toplam dağılım:

| Split | Kayıt sayısı |
|---|---:|
| Train | 1.085 |
| Validation | 155 |
| Test | 310 |
| **Toplam** | **1.550** |

Bu test bölümü sadece üretilmiş anket kombinasyonlarına karşı başarıyı ölçer.
Gerçek genelleme iddiası için ayrıca farklı kaynaklardan hazırlanmış, uzman
etiketli bir external test set kullanılmalıdır.

## Kayıt şeması

Her JSONL satırı bağımsız bir JSON nesnesidir. Önemli alanlar:

| Alan | Açıklama |
|---|---|
| `id` | Sıralı ve benzersiz kayıt kimliği |
| `index` | 1–1550 global sıra numarası |
| `split` | `train`, `validation` veya `test` |
| `scenario_group` | Benzer varyantları aynı split içinde tutan grup |
| `input_text` | Modele verilebilecek soru-cevap metni |
| `answers_by_flow_id` | Uygulamanın kullandığı `Q<number> -> answer` biçimi |
| `evidence_question_ids` | Hedef sınıfı desteklemek üzere seçilen survey soruları |
| `context_question_ids` | Sistem bağlamı için eklenen nötr sorular |
| `label` | Beklenen tek OWASP etiketi veya `NO_THREAT` |
| `framework` | `owasp_llm`, `owasp_web`, `owasp_api` veya `none` |
| `hard_negative_for` | `NO_THREAT` kaydının soru desenini aynaladığı pozitif etiket; pozitiflerde `null` |
| `provenance` | Üretim ve insan doğrulama durumu |

Örnek:

```json
{
  "id": "OWASP31-0001",
  "split": "train",
  "input_text": "Q20. Can users influence system prompts or instructions indirectly?\nAnswer: Yes, through prompt templates or variables",
  "answers_by_flow_id": {
    "Q20": "Yes, through prompt templates or variables"
  },
  "label": "LLM01:2026",
  "label_name": "Prompt Injection",
  "framework": "owasp_llm"
}
```

LoRA instruction-tuning dönüşümünde `input_text` user mesajı, `label` ise
assistant cevabı olarak kullanılabilir. Modelden yalnızca izin verilen etiketi
üretmesi istenmelidir.

## Survey eşleştirme yaklaşımı

Pozitif sınıflar, uygulamadaki `risk_catalog.py` eşleştirmeleri başlangıç alınarak
oluşturulmuştur. Kayıtlar, ilgili risk için olumsuz veya zayıf kontrol bildiren
survey seçeneklerinin kombinasyonlarını içerir. Nötr bağlam soruları sistemin
amacını, arayüzünü, mimarisini, ölçeğini ve etkisini çeşitlendirir.

LLM kategorilerinde 2026 numaralandırması kullanıldığı için eski 2025 kodlarına
göre değil kategori anlamına göre taşıma yapılmıştır. Örneğin 2025'te `LLM06`
olan Excessive Agency, bu veri setinde `LLM03:2026` olarak tutulur.

Mevcut uygulama kataloğunda Web `A06:2025 Insecure Design` için ayrı bir aday
satırı yoktur. Bu veri setinde A06; tasarım incelemesi, hassas iş akışları,
onay kontrolleri, güvenlik sahipliği, adversarial test ve replay sorularıyla
temsil edilmiştir.

`NO_THREAT` kayıtları her pozitif sınıfın soru desenini güvenli cevaplarla
aynalar. Q3 arayüz ve Q85 mimari bileşen soruları pozitiflerde olduğu gibi bütün
negatiflerde de bulunur. Diğer sorularda güçlü kimlik doğrulama/yetkilendirme,
doğrulama, izolasyon, rate limiting, logging, fail-closed davranış ve insan
onayı gibi koruyucu seçenekler kullanılır. Bir soruda güvenli/neutral bir seçenek
yoksa o soru hard-negative kaydına zorla eklenmez.

## Bilinen sınırlamalar

1. Web, API ve LLM kategorileri semantik olarak örtüşür. Örneğin Web A02 ile
   API8 aynı anda doğru olabilir. Bu sürüm kontrollü deney için tek bir baskın
   etiket taşır; gerçek sistem daha sonra multi-label olarak değerlendirilmelidir.
2. Kayıtlar gerçek olay metinleri değil, survey cevap kombinasyonlarıdır.
3. Bazı survey soru metinleri hedef kavramı açıkça adlandırır. Bu nedenle yalnızca
   bu veri setinde alınan yüksek skor gerçek dünya tehdit tespit başarısı olarak
   yorumlanmamalıdır.
4. `human_validated` bütün kayıtlarda `false` değerindedir. Uzman incelemesi
   tamamlanmadan bunlar nihai ground truth sayılmamalıdır.
5. Dataset ve aktif uygulama kataloğu LLM Top 10:2026 kodlarına sabitlenmiştir.
   Daha önce üretilmiş 2025 benchmark çıktılarıyla karşılaştırma yapılacaksa
   kategori numarası değil kategori anlamı üzerinden dönüşüm uygulanmalıdır.
