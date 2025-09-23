MentoraAI - Simulasi Seminar Proposal dengan AI 🧠✨
Selamat datang di repositori backend untuk MentoraAI! Proyek ini adalah sebuah aplikasi web canggih yang dirancang untuk membantu mahasiswa mempersiapkan diri menghadapi seminar proposal (sempro) atau sidang skripsi dengan melakukan simulasi interaktif bersama Dosen Penguji berbasis AI.


📝 Deskripsi Proyek
MentoraAI memberikan pengalaman simulasi sempro yang realistis. Mahasiswa dapat mengunggah file proposal mereka dalam format PDF, dan AI akan berperan sebagai dosen penguji yang memberikan pertanyaan-pertanyaan kritis dan relevan berdasarkan konten proposal tersebut. Di akhir sesi, mahasiswa akan mendapatkan skor, umpan balik konstruktif, dan laporan lengkap dalam format PDF.

Tujuan utama proyek ini adalah:

Meningkatkan Kepercayaan Diri: Membantu mahasiswa berlatih dan mengurangi rasa gugup.

Mengidentifikasi Kelemahan: Menemukan area dalam penelitian yang perlu diperkuat.

Memberikan Umpan Balik Instan: Memberikan evaluasi langsung tanpa harus menunggu jadwal dengan dosen sungguhan.

🚀 Fitur Utama
🗣️ Simulasi Interaktif: Komunikasi dua arah (teks dan suara) dengan AI Dosen Penguji.

📄 Analisis PDF Cerdas: AI mampu membaca dan memahami konteks dari file proposal yang diunggah.

📊 Penilaian Komprehensif: Dapatkan skor akhir berdasarkan relevansi, kejelasan, dan penguasaan materi.

💡 Umpan Balik Konstruktif: AI memberikan feedback mendetail untuk area perbaikan.

📥 Laporan PDF: Unduh laporan evaluasi lengkap di akhir setiap sesi.

🔐 Otentikasi Aman: Sistem login berbasis JWT untuk melindungi data pengguna.

🗂️ Riwayat Sesi: Lihat kembali semua riwayat simulasi dan laporan yang pernah dilakukan.

🛠️ Tumpukan Teknologi (Tech Stack)
Arsitektur aplikasi ini dibangun menggunakan teknologi modern dan skalabel.

Backend: Python, FastAPI

Database: PostgreSQL

Otentikasi: JWT (JSON Web Tokens)

AI & Machine Learning: Google Gemini Pro

Text-to-Speech (TTS): Google Cloud TTS

Penyimpanan File: Google Cloud Storage (GCS)

Kontainerisasi: Docker & Docker Compose

🏗️ Arsitektur Sistem
Aplikasi ini berjalan dalam lingkungan Docker yang terisolasi, memastikan konsistensi antara development dan produksi.

[Gambar dari diagram arsitektur aplikasi web]

Frontend (React.js): Berjalan di browser pengguna (localhost:3000), menangani antarmuka dan interaksi.

Backend (FastAPI): Berjalan di dalam container Docker (localhost:8000), menangani semua logika bisnis, otentikasi, dan komunikasi dengan layanan eksternal.

Database (PostgreSQL): Berjalan di container Docker terpisah, menyimpan data pengguna dan sesi.

Layanan Google Cloud: Digunakan untuk AI, TTS, dan penyimpanan laporan PDF.

🏁 Panduan Memulai (Getting Started)
Berikut adalah cara menjalankan proyek ini di lingkungan lokal Anda. Panduan ini ditujukan untuk tim frontend atau QA yang ingin menjalankan backend.

✅ Prasyarat
Docker Desktop: Pastikan sudah terinstal dan sedang berjalan.

Git: Sudah terinstal untuk mengunduh kode.

⚙️ Langkah-langkah Setup
Clone Repositori
Buka terminal dan jalankan perintah berikut:

git clone [https://github.com/NAMA_ANDA/mentora-backend.git](https://github.com/NAMA_ANDA/mentora-backend.git)
cd mentora-backend

Konfigurasi Environment Docker ‼️
Anda perlu membuat file konfigurasi untuk Docker.

Buat file baru bernama .env.docker.

Salin semua isi dari file .env.example ke dalam .env.docker.

Isi semua nilai yang diperlukan, terutama:

GEMINI_API_KEY

GCS_BUCKET_NAME

SECRET_KEY (buat string acak yang panjang dan aman)

Tambahkan Kredensial Google Cloud 🔑

Buat folder baru bernama credentials/.

Letakkan file kredensial JSON dari Google Cloud Anda di dalam folder ini.

Pastikan nama file JSON ini sama dengan nilai yang Anda tulis di GOOGLE_APPLICATION_CREDENTIALS dalam file .env.docker.

Jalankan dengan Docker Compose! 🚀
Ini adalah satu-satunya perintah yang Anda perlukan untuk menyalakan seluruh backend dan database-nya.

docker-compose up --build

Tunggu beberapa saat hingga proses selesai. Jika berhasil, Anda akan melihat log dari server Uvicorn di terminal.

Verifikasi
Buka browser dan akses http://localhost:8000/docs. Jika Anda melihat halaman dokumentasi API interaktif (Swagger UI), berarti backend berhasil berjalan dengan sukses! 🎉

🔌 Menghubungkan Frontend (React)
Pastikan proyek React Anda memiliki file .env dengan variabel berikut untuk terhubung ke backend Docker:

REACT_APP_API_BASE_URL=http://localhost:8000

🔐 Keamanan
Repositori ini menggunakan file .gitignore untuk mencegah file-file sensitif (seperti .env*, credentials/, venv/) terunggah ke GitHub. Pastikan Anda tidak pernah menghapus atau mengubah file .gitignore ini.