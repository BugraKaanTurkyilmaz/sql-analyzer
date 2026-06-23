# SQL Analyzer — Linux Kurulum ve Çalıştırma Kılavuzu

## Proje Özeti

Bu araç, Oracle SQL betiklerini (INSERT / UPDATE / DELETE / DDL / EXEC) analiz eden, risk skoru üreten ve doğrulama SELECT'leri oluşturan bir Flask web uygulamasıdır. Opsiyonel olarak canlı bir Oracle veritabanına bağlanıp sorguları gerçek zamanlı çalıştırabilir.

---

## Sistem Gereksinimleri

| Bileşen | Minimum Sürüm | Notlar |
|---|---|---|
| İşletim Sistemi | Ubuntu 20.04 / Debian 11 / RHEL 8 veya üstü | Diğer distro'lar da çalışır |
| Python | 3.9+ | 3.10/3.11/3.12 önerilir |
| pip | 21+ | Python ile birlikte gelir |
| RAM | 512 MB | |
| Disk | 200 MB | .venv dahil |
| İnternet | Kurulum sırasında gerekli | pip paketleri için |

---

## 1. Python Kurulumu

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

# RHEL / CentOS / Rocky Linux
sudo dnf install -y python3 python3-pip git
```

Kontrol:
```bash
python3 --version   # 3.9+ olmalı
pip3 --version
```

---

## 2. Projeyi İndir

```bash
git clone https://github.com/BugraKaanTurkyilmaz/sql-analyzer.git
cd sql-analyzer
```

---

## 3. Sanal Ortam Oluştur ve Paketleri Yükle

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` içeriği:
```
flask>=2.3.0
oracledb>=2.0.0
```

---

## 4. Uygulamayı Başlat

### Yöntem A — Doğrudan Python ile

```bash
source .venv/bin/activate   # sanal ortam aktif değilse
python3 app.py
```

Tarayıcıda aç: `http://localhost:5001`

### Yöntem B — Başlatma scripti ile (baslat.sh)

Scriptteki `open` komutu macOS'a özgüdür, Linux'ta çalışmaz ama hata vermez (`2>/dev/null || true` ile bastırılmıştır). Sadece şunu çalıştır:

```bash
chmod +x baslat.sh
./baslat.sh
```

Script:
- `.venv` yoksa otomatik oluşturur ve paketleri yükler
- Uygulamayı başlatır

### Yöntem C — CLI (grafik arayüz olmadan)

```bash
source .venv/bin/activate
python3 run.py input.sql              # ekrana yazar
python3 run.py input.sql output.sql   # dosyaya kaydeder
```

---

## 5. Oracle DB Bağlantısı (Opsiyonel)

Uygulama, üretilen doğrulama SELECT'lerini canlı Oracle'a gönderip sonuç alabilir. Bunun için ek bir sistem kütüphanesi gerekmez — `oracledb` paketi Python-native (thin) modda çalışır, Oracle Client kurulumu gerektirmez.

Arayüzde **"Veritabanında Test Et"** butonuna tıklayarak bağlantı bilgilerini gir:
- **Host**: Oracle sunucusu IP/hostname
- **Port**: varsayılan 1521
- **Service Name**: Oracle servis adı
- **Kullanıcı / Şifre**

---

## 6. Üretim Ortamı için (Opsiyonel)

Flask'ın geliştirme sunucusu yerine **gunicorn** kullan:

```bash
source .venv/bin/activate
pip install gunicorn

# 4 worker, port 5001
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### Systemd Servisi

`/etc/systemd/system/sql-analyzer.service` dosyasını oluştur:

```ini
[Unit]
Description=SQL Analyzer
After=network.target

[Service]
User=<kullanici_adi>
WorkingDirectory=/home/<kullanici_adi>/sql-analyzer
ExecStart=/home/<kullanici_adi>/sql-analyzer/.venv/bin/gunicorn -w 4 -b 0.0.0.0:5001 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now sql-analyzer
```

---

## 7. Firewall (Gerekiyorsa)

```bash
# Ubuntu (ufw)
sudo ufw allow 5001/tcp

# RHEL / Rocky (firewalld)
sudo firewall-cmd --add-port=5001/tcp --permanent
sudo firewall-cmd --reload
```

---

## Ozet — Hizli Baslangic

```bash
sudo apt install -y python3 python3-pip python3-venv git
git clone https://github.com/BugraKaanTurkyilmaz/sql-analyzer.git
cd sql-analyzer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
# → http://localhost:5001
```
