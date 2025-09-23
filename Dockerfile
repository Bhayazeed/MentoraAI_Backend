# 1. Mulai dari "dapur" yang sudah ada: Python versi 3.10 yang ramping.
FROM python:3.10-slim

# 2. Buat folder kerja di dalam "koper" kita. Sebut saja /app.
WORKDIR /app

# 3. Salin HANYA file daftar belanja (requirements) terlebih dahulu.
# Ini trik agar Docker lebih cepat di kemudian hari.
COPY requirements.txt requirements.txt

# 4. Install semua "bahan" yang ada di daftar belanja.
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 5. Sekarang, salin semua sisa kode proyek Anda ke dalam folder /app.
COPY . .

# 6. Beritahu dunia luar bahwa "koper" ini akan membuka layanan di port 8000.
EXPOSE 8000

# 7. Perintah terakhir: Saat "koper" dibuka, jalankan aplikasi ini.
# Gunakan --host 0.0.0.0 agar bisa diakses dari luar "koper".
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

