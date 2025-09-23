<p align="center">
  <img src="https://drive.google.com/uc?export=view&id=1Wz8usbc2212t8nZ8lMEXpu3cpS7LI6sn" alt="MentoraAI" width="400"/>
</p>

# MentoraAI - Simulasi Seminar Proposal dengan AI 🧠✨
---
Selamat datang di **repositori backend untuk MentoraAI!  
Proyek ini adalah aplikasi web canggih yang dirancang untuk membantu mahasiswa mempersiapkan diri menghadapi **seminar proposal (sempro)** atau **sidang skripsi** melalui simulasi interaktif bersama **Dosen Penguji berbasis AI**.

## 📝 Deskripsi Proyek
MentoraAI memberikan pengalaman simulasi **sempro yang realistis**.  
Mahasiswa dapat mengunggah file proposal dalam format **PDF**, dan AI akan berperan sebagai dosen penguji yang memberikan **pertanyaan kritis dan relevan** berdasarkan isi proposal.  

Di akhir sesi, mahasiswa akan mendapatkan:
- Skor penilaian  
- Umpan balik konstruktif  
- Laporan lengkap dalam format **PDF**

### 🎯 Tujuan Proyek
- **Meningkatkan Kepercayaan Diri** → membantu mahasiswa berlatih & mengurangi rasa gugup.  
- **Mengidentifikasi Kelemahan** → menemukan bagian penelitian yang perlu diperkuat.  
- **Memberikan Umpan Balik Instan** → evaluasi langsung tanpa menunggu jadwal dengan dosen sungguhan.  

---

## 🚀 Fitur Utama
- 🗣️ **Simulasi Interaktif** → komunikasi dua arah (teks & suara) dengan AI Dosen Penguji.  
- 📄 **Analisis PDF Cerdas** → membaca & memahami proposal yang diunggah.  
- 📊 **Penilaian Komprehensif** → skor akhir berdasarkan relevansi, kejelasan, & penguasaan materi.  
- 💡 **Umpan Balik Konstruktif** → feedback detail untuk perbaikan.  
- 📥 **Laporan PDF** → unduh laporan evaluasi lengkap.  
- 🔐 **Otentikasi Aman** → login berbasis JWT untuk melindungi data.  
- 🗂️ **Riwayat Sesi** → simpan & lihat kembali simulasi dan laporan.  

---

## 🛠️ Tumpukan Teknologi (Tech Stack)
- **Backend**: Python, FastAPI  
- **Database**: PostgreSQL  
- **Otentikasi**: JWT (JSON Web Tokens)  
- **AI & Machine Learning**: Google Gemini Pro  
- **Text-to-Speech (TTS)**: Google Cloud TTS  
- **Penyimpanan File**: Google Cloud Storage (GCS)  
- **Kontainerisasi**: Docker & Docker Compose  

---

## 🏗️ Arsitektur Sistem
Aplikasi ini berjalan dalam **lingkungan Docker** yang terisolasi, memastikan konsistensi antara development & production.

![Diagram Arsitektur Aplikasi](link-ke-diagram-anda)

- **Frontend (React.js)** → antarmuka pengguna, berjalan di browser (`localhost:3000`).  
- **Backend (FastAPI)** → logika bisnis, otentikasi, komunikasi layanan eksternal (`localhost:8000`).  
- **Database (PostgreSQL)** → menyimpan data pengguna & sesi (dalam container terpisah).  
- **Layanan Google Cloud** → untuk AI, TTS, & penyimpanan laporan PDF.  

---

## 🏁 Panduan Memulai (Getting Started)

### ✅ Prasyarat
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (terinstal & berjalan)  
- [Git](https://git-scm.com/)  

### ⚙️ Langkah-langkah Setup

#### 1. Clone Repositori
```bash
git clone https://github.com/NAMA_ANDA/mentora-backend.git
cd mentora-backend
```

#### 2. Konfigurasi Environment Docker

Buat file baru bernama .env.docker, lalu salin isi dari .env.example.
Isi nilai berikut:
```bash
GEMINI_API_KEY=...
GCS_BUCKET_NAME=...
SECRET_KEY=...   # string acak, panjang & aman
```
#### 3. Tambahkan Kredensial Google Cloud 🔑

•Buat folder credentials/

•Masukkan file kredensial JSON Google Cloud ke folder tersebut

•Pastikan nama file sama dengan GOOGLE_APPLICATION_CREDENTIALS di .env.docker

#### 4. Jalankan dengan Docker Compose 🚀
```bash
docker-compose up --build
```
Tunggu proses selesai → jika berhasil, Anda akan melihat log dari Uvicorn server.

#### 5. Verifikasi

Buka browser → http://localhost:8000/docs
Jika muncul Swagger UI, backend sudah berjalan 🎉
