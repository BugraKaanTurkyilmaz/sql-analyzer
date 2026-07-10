# SQL Analyzer

Oracle SQL script'lerini (INSERT / UPDATE / DELETE / DDL / EXEC) analiz eden, riskli ifadeleri tespit eden ve her ifade için **doğrulama SELECT'i** üreten bir Flask web uygulaması.

Script'i doğrudan veritabanında çalıştırmadan önce, ne yapacağını görmek için kullanılır: hangi UPDATE/DELETE'lerin `WHERE` koşulu yok, hangi tablo/sütunlar mevcut değil, hangi DDL'ler çakışacak — hepsi tek bir doğrulama script'i olarak üretilir ve DB'de önce bu üretilen SELECT'ler çalıştırılarak kontrol edilir.

🔗 canlı demo / kaynak: [github.com/BugraKaanTurkyilmaz/sql-analyzer](https://github.com/BugraKaanTurkyilmaz/sql-analyzer)

## Özellikler

- **INSERT** → hedef satırın zaten var olup olmadığını kontrol eden SELECT üretir (dinamik değerler — `SYSDATE`, `NEXTVAL` vb. — otomatik atlanır)
- **UPDATE / DELETE** → etkilenecek satır sayısına göre risk seviyesi üretir (Düşük / Orta / Yüksek); `WHERE` koşulu yoksa **KRİTİK** olarak işaretler
- **DDL (CREATE / ALTER / DROP / TRUNCATE)** → Oracle data dictionary'ye (`ALL_TABLES`, `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_INDEXES`, `ALL_OBJECTS`) karşı ön kontrol SELECT'i üretir; olası `ORA-` hatalarını isim bazında haber verir
- **EXEC / EXECUTE / CALL** → prosedür/paket prosedürünün mevcut olup olmadığını kontrol eder
- Şema/tablo bazlı özet tablo ve risk istatistikleri
- Sonucu `.sql` dosyası olarak indirme
- Dosya yükleme veya doğrudan metin yapıştırma ile toplu script analizi
- Opsiyonel erişim anahtarı (token) koruması

> Not: Araç üretilen SELECT'leri **kendisi çalıştırmaz** — sadece doğrulama script'ini üretir. Üretilen script'i hedef veritabanında sen çalıştırıp sonucu kontrol edersin. Özellikle `MODIFY` gibi veri-bağımlı DDL işlemlerinde (örn. precision azaltma) üretilen kontrol yalnızca sütunun varlığını doğrular; gerçek işlemin veriyle uyumluluğunu garanti etmez.

## Hızlı Başlangıç

```bash
git clone https://github.com/BugraKaanTurkyilmaz/sql-analyzer.git
cd sql-analyzer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
# → http://localhost:5001
```

macOS için hazır script:

```bash
./baslat.sh
```

Linux kurulumu için ayrıntılı adımlar: [LINUX_KURULUM.md](LINUX_KURULUM.md)

## Kullanım

### Web arayüzü

`http://localhost:5001` adresine git, script'i yapıştır veya dosya yükle, **Dönüştür**'e bas. Üretilen doğrulama script'ini kopyalayabilir veya `.sql` olarak indirebilirsin.

### CLI

```bash
python3 run.py input.sql              # sonucu ekrana yazar
python3 run.py input.sql output.sql   # dosyaya kaydeder
```

## Yapılandırma

| Ortam Değişkeni | Açıklama |
|---|---|
| `PORT` | Uygulamanın dinleyeceği port (varsayılan `5001`) |
| `ACCESS_TOKEN` | Doldurulursa arayüz/istekler bu token ile korunur; boşsa koruma devre dışıdır (yerel geliştirme için) |

## Üretim Ortamı

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

Railway gibi platformlarda `Procfile` üzerinden doğrudan deploy edilebilir.

## Proje Yapısı

```
app.py              Flask route'ları (/,  /convert,  /download)
sql_converter.py     Parse + risk analizi + doğrulama SELECT üretim motoru
run.py               CLI arayüzü
templates/index.html Tek sayfalık web arayüzü
baslat.sh            macOS için kurulum + başlatma script'i
Procfile             Railway/gunicorn üretim başlatma komutu
LINUX_KURULUM.md      Linux'a özel adım adım kurulum kılavuzu
```

## Geliştirici

**Buğra Kaan Türkyılmaz**
[LinkedIn](https://www.linkedin.com/in/bu%C4%9Fra-kaan-t%C3%BCrkyilmaz/?locale=tr)
