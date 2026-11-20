# v3 durum notu

Son güncelleme: 2026-11-20 · Branch: `v3` · Plan: `PLAN_v3.md` (çalışma klasöründe)

Bu dosya v3 çalışmasının kararlarını, kanıtlarını ve açık maddelerini tutar. Her bölüm sonunda güncellenir.

## Faz 0: durum

| Adım | Durum | Kanıt |
| --- | --- | --- |
| 0.1 Demo durumu | Tamam | Merge öncesi: Groq `llama-3.3-70b-versatile` kapalı (`model_not_found`), her çağrı Gemini fallback'e düşüyordu |
| 0.2 Push edilmemiş commit | Tamam | Eski kopyadaki OTel bağımlılık commit'i `v3`'e alındı (`3090e75`) |
| 0.3 Klon ve `v3` | Tamam | — |
| 0.4 `.gitignore` | Tamam | `.env`, `data/*.db`, `data/chroma/`, `data/answer_cache.json`, `.streamlit/secrets.toml` |
| 0.5 `.env` ve `data/` taşıma | Tamam | 16/16 dosya, 1.988.257.776 bayt, kaynakla aynı; `answer_cache.json` bilerek taşınmadı |
| 0.6 Ortam ve testler | Tamam | Python 3.11.9, 21 test geçiyor |
| 0.7 gpt-oss-20b | Tamam | PR #1 (`55ccca2`) |
| 0.8 Demo | Tamam | Canlı demo: "Which store has the most products listed?" → Whirlpool, 405; SQL ile aynı; rota `sql`, 1,8 sn |
| 0.9 README | Tamam (commit 0.11'de) | Sayılar STATUS.md 2026-07-11 satırıyla eşleşiyor (SQL 92%, faith 1.00, rel 0.87, trajectory 100%); n sütunu, ölçüm modeli (Llama 3.3 70B) ve 3 sınıflı routing notu eklendi; Stack gpt-oss-20b; `pytest` 21 passed |
| 0.10 `eval_results/baseline.json` | Tamam (commit 0.11'de) | Geçmiş kayıt, yeni koşu yok. Kaynak: STATUS.md 2026-07-11 satırı, `d4d1e16`. Golden set sha256 (git blob, LF) HEAD ve `d4d1e16`'da aynı. README'den bağlantılı. |
| 0.11 Kapı ve commit | Tamam | `pytest` 21 passed; README = STATUS.md = baseline.json (9/9 kontrol); değişen dosyalarda anahtar deseni ve `.env` değeri 0; code-review 1 bulgu (README self-judge notu) düzeltildi |

## Kararlar

| Tarih | Karar | Gerekçe |
| --- | --- | --- |
| 2026-11-20 | Bulut sağlayıcı Groq (`groq/openai/gpt-oss-20b`), model gpt-oss-20b sabit | Ollama Cloud API çağrısı kredi istedi, bütçe kuralına uymadı. Groq ücretsiz katmanda aynı modeli sunuyor (test: 1,31 sn). Model değişmediği için parite planı geçerli. |
| 2026-11-20 | Model kimlikleri `PRIMARY_MODEL` / `FALLBACK_MODEL` ile `.env`'den değiştirilebilir | Sağlayıcı değişikliği kod değişikliği gerektirmesin. Profil sistemi (Faz 1) bunun üzerine kurulacak. |
| 2026-11-20 | `test_critic` grounded örneği kaynak cümleyle eşleştirildi | Eski cümlenin atfı belirsizdi; Gemini (1/1) ve gpt-oss (3/3) aynı gerekçeyle reddetti. Test amacı korundu. |
| 2026-11-20 | Demo hata ayrıntıları gizlendi (`showErrorDetails = "none"`) | AppTest ile kanıtlandı: önce stack trace ve dosya yolları görünüyordu, sonra sadece redakte mesaj. |
| 2026-11-20 | Hotfix `main`'e ayrı branch'ten girdi, `v3` onun üzerine rebase edildi | Canlı demo yarım kalmış v3 işinden etkilenmesin. |
| 2026-11-20 | NVIDIA Nemotron 3.5 Lightning kapsam dışı | Laptopa sığmıyor, model değişikliği eval geçmişini sıfırlar. v3 sonrası eşli karşılaştırma adayı. |
| 2026-11-20 | Baseline yeni koşu değil, geçmiş kayıt | Llama 3.3 70B kapandı, aynı koşul tekrar üretilemez. Kusurlar (B10, `rag_03`/`rag_10` düzenlemesi) gizlenmeden `caveats`'te. |
| 2026-11-20 | B7 (pysqlite3 marker) Faz 1'e ertelendi | Ortam kararı; B2 (sürüm eşitleme, lock) ile birlikte ele alınır. Kapı commit'i sadece doküman/kayıt. |
| 2026-11-20 | `docs/security_report.md` Faz 4'e ertelendi | Tarama özeti burada var; ikinci kopya ayrışır. Rapor S2/S3 kapandıktan sonra gerçek PASS/FAIL ile yazılır. |
| 2026-11-20 | Heyet ve direktör uzlaşırsa adım onay beklemeden uygulanır | Murat'ın talimatı; uzlaşma yoksa sorulur. |

## Bulgular (Faz 0 sırasında)

| # | Bulgu | Etki | Ne zaman |
| --- | --- | --- | --- |
| B1 | Demo örneklerinden biri golden set sorusuyla birebir aynı (`rag_01`), biri yakın (`sql_05`, Jaccard 0,59) | Golden set sızıntısı; eski önbellekte bu cevaplar vardı | Faz 4 (örnekler değişecek). Baseline'da not edilecek. |
| B2 | Yerel Python 3.11.9, canlı demo Python 3.14 | Parite ve tekrarlanabilirlik riski | Faz 1: sürüm eşitleme / lock dosyası |
| B3 | gpt-oss SQL cevaplarında `[asin]` / `【asin】` artığı | Biçim kalitesi | Faz 2'de golden set üzerinde ölçülecek |
| B4 | Hybrid rotası critic reddettiğinde de `Sources:` satırını ekliyor (`graph.py`) | Kullanılmayan kaynak gösteriliyor | Faz 2 |
| B5 | Fallback sessiz: cevabın hangi modelden geldiği sonuçta işaretlenmiyor | Eval'de modeller karışabilir, judge yanlılığı geri gelebilir | Faz 1 (trace'e model), Faz 2 (eval'de fallback kapalı) |
| B6 | `llm` marker'lı canlı testler varsayılan `pytest` koşusunda çalışıyor | Her test koşusu kota harcar | Faz 5 (CI) |
| B7 | `requirements.txt` içindeki `pysqlite3-binary` Windows'ta kurulmuyor | Yerel kurulum kırılıyor | Önerilen: `; sys_platform == "linux"` marker'ı |
| B8 | Rate limit ve soru uzunluğu sınırı yok | Kota tükenmesiyle demo kilitlenebilir | Faz 4 |
| B9 | Ortamda TLS denetimi var (`self-signed certificate in certificate chain`) | Yerel profil ve Docker'da bağlantı sorunu çıkabilir | Faz 1 |
| B10 | Eski eval'de judge = üreten model (`run_eval.py` judge'ı `ask_llm` ile çağırıyor) | Faithfulness 1.00 ve relevance 0.87 self-judged; yanlılık riski | Faz 2: Gemini judge, fallback kapalı |

## Güvenlik taraması (2026-11-20)

- 47 commit'te bilinen anahtar desenleri: 0 eşleşme (pozitif kontrol: aynı desenler `.env`'de 3 anahtarı buldu).
- `.env`'deki her anahtar değeri birebir arandı: geçmişte ve çalışma alanında 0.
- `.env` ve hassas dosyalar hiç commit edilmemiş; `.dockerignore` `.env`'i dışarıda tutuyor.
- Sağlayıcı hata mesajında anahtar yok (sahte anahtarla test).
- XSS: `st.markdown` `unsafe_allow_html` olmadan. SQL: SELECT-only guard ve read-only bağlantı.
- Çalıştırılmadı: bağımlılık açık taraması (`pip-audit`), Faz 5 CI adayı.

## Ortam

- Yerel: Windows, Python 3.11.9, `.venv`, `litellm` 1.91.x.
- Canlı demo: Streamlit Community Cloud, `main` branch, Python 3.14, secrets'ta `GROQ_API_KEY` ve `GEMINI_API_KEY`.

## Sıradaki adım

Faz 0 kapısı geçti. Sırada Faz 1: instrumentation ve model katmanı (`@traced_node`, Langfuse, `cloud`/`local` profilleri, fail-closed yerel mod, smoke set). Ek olarak B2, B5, B7, B9. Not: plandaki "Ollama Cloud hesabı" maddesi Groq kararıyla yeniden değerlendirilecek.
