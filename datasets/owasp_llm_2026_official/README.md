# OWASP GenAI LLM Top 10 2026 - Official Training Sources

Bu klasör, kullanıcının sağladığı `OWASP-GenAI-LLM-Top-10-2026-v1.0.pdf`
belgesinin 10-57. sayfalarındaki on risk bölümünden çıkarılmış, kaynakla
izlenebilir eğitim ham maddelerini içerir.

Kaynak: [OWASP GenAI LLM Top 10 2026](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/)

Lisans: **CC BY-SA 4.0**. Türetilmiş/verbatim içerik kullanılırken OWASP atfı ve
ShareAlike koşulları korunmalıdır.

## Çıktılar

- `official_llm2026_catalog.json`: Her kategori için açıklama, yaygın risk
  örnekleri, mitigation stratejileri ve saldırı senaryolarının tam yapılandırılmış
  kataloğu.
- `official_attack_scenarios.jsonl`: Tehdit sınıflandırması için 63 resmî saldırı
  senaryosu.
- `official_common_risk_examples.jsonl`: Tehdit sınıflandırması/veri artırımı için
  72 yaygın risk örneği.
- `official_mitigations.jsonl`: Mitigation generation için 96 resmî kontrol ve
  azaltım maddesi.
- `manifest.json`: Sayımlar, kategori başına dağılım ve kaynak sayfaları.
- `extract_official_training_sources.py`: PDF'den aynı çıktıları yeniden üreten
  deterministik çıkarım scripti.

## Sayımlar

| Kod | Kategori | Sayfalar | Senaryo | Mitigation | Risk örneği |
|---|---|---:|---:|---:|---:|
| `LLM01:2026` | Prompt Injection | 10-17 | 9 | 11 | 8 |
| `LLM02:2026` | Sensitive Information Disclosure | 18-22 | 10 | 19 | 7 |
| `LLM03:2026` | Excessive Agency | 23-26 | 1 | 9 | 6 |
| `LLM04:2026` | Supply Chain | 27-32 | 8 | 7 | 7 |
| `LLM05:2026` | Data and Model Poisoning | 33-37 | 9 | 12 | 9 |
| `LLM06:2026` | Unbounded Consumption | 38-42 | 8 | 10 | 9 |
| `LLM07:2026` | Misinformation | 43-45 | 7 | 10 | 7 |
| `LLM08:2026` | Hidden Context Exposure | 46-49 | 2 | 3 | 5 |
| `LLM09:2026` | Vector and Embedding Weaknesses | 50-54 | 3 | 6 | 7 |
| `LLM10:2026` | Improper Output Handling | 55-57 | 6 | 9 | 7 |
| **Toplam** |  |  | **63** | **96** | **72** |

## Eğitimde kullanım

### Threat classification

`official_attack_scenarios.jsonl` ve `official_common_risk_examples.jsonl`
etiketli seed kayıtlarıdır. `input` alanı modele verilecek metin, `label` alanı
beklenen `LLMxx:2026` cevabıdır.

Bu kayıtların paraphrase veya sentetik varyantları üretilirse aynı kaynak
senaryodan türeyen bütün varyantlar tek `scenario_group` altında ve tek split'te
tutulmalıdır. PDF'deki orijinal senaryonun train'e, paraphrase'inin test'e
konulması veri sızıntısıdır.

### Mitigation generation

`official_mitigations.jsonl` kategori bazlı resmî mitigation havuzudur. Bazı
kategorilerde tier bilgisi (`Tier 1`, `Tier 2`, `Tier 3`) korunmuştur.

Bir kategorinin bütün mitigation maddeleri her senaryoya otomatik olarak doğru
kabul edilmemelidir. Nihai scenario-to-mitigation eğitim çiftleri oluşturulurken:

1. Senaryodaki somut control gap belirlenmeli.
2. Yalnız bu control gap'i karşılayan mitigation maddeleri seçilmeli.
3. Eşleştirme uzman tarafından doğrulanmalı.
4. İlgili fakat uygulanamaz kontroller negatif/uygulanamaz olarak ayrıca
   işaretlenebilmelidir.

## Yeniden üretme

Proje kökünden, `pypdf` bulunan Python ortamıyla:

```powershell
python datasets\owasp_llm_2026_official\extract_official_training_sources.py `
  C:\path\to\OWASP-GenAI-LLM-Top-10-2026-v1.0.pdf
```

Script yalnız PDF'nin metin katmanını yapılandırır; yeni senaryo veya mitigation
uydurmaz. Üretilen içerikte `source_pages`, resmî URL ve lisans bilgisi korunur.

