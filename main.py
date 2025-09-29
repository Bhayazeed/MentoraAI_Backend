import os
import uuid
import fitz  # PyMuPDF
import json
import base64
import traceback
import io
from datetime import datetime, timedelta, timezone

# --- BARU: Impor dan panggil load_dotenv ---
from dotenv import load_dotenv
load_dotenv() # Ini akan memuat variabel dari file .env

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from google.cloud import storage

# --- MODIFIKASI: Impor modul lokal ---
import auth
import models
import schemas
from database import SessionLocal, engine
from auth import get_current_user

# --- Impor Library AI (tetap sama) ---
import google.generativeai as genai
from fpdf import FPDF
from PIL import Image
from google.cloud import texttospeech
import soundfile as sf
import numpy as np

# --- MODIFIKASI: Membuat tabel database saat startup ---
models.Base.metadata.create_all(bind=engine)

# --- Konfigurasi Aplikasi ---
app = FastAPI(
    title="MentoraAI",
    version="2.0.0",
    description="Backend simulasi sempro dengan otentikasi, database, dan GCS.",
)

# --- MODIFIKasi: Menambahkan CORS Middleware untuk frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ganti dengan domain frontend Anda di produksi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODIFIKASI: Menggabungkan router otentikasi ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# --- Konfigurasi Kunci API & GCS dari Environment Variable ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("PERINGATAN: Kunci API 'GEMINI_API_KEY' tidak ditemukan.")

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
if not GCS_BUCKET_NAME:
    print("PERINGATAN: 'GCS_BUCKET_NAME' tidak ditemukan. Upload laporan akan gagal.")

# --- PERBAIKAN FINAL: Menggunakan nama model suara Chirp HD yang benar ---
# Format yang benar adalah 'id-ID-Chirp3-HD-<NamaPersona>'
GOOGLE_TTS_VOICES = {
    "Pria - Algenib (Chirp HD)": "id-ID-Chirp3-HD-Algenib",
    "Pria - Achird (Chirp HD)": "id-ID-Chirp3-HD-Achird",
    "Wanita - Achernar (Chirp HD)": "id-ID-Chirp3-HD-Achernar",
    "Wanita - Aoede (Chirp HD)": "id-ID-Chirp3-HD-Aoede",
}

# --- MODIFIKASI: Dependensi untuk mendapatkan sesi database ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DEMO_RESPONSES = { "latar belakang": "Tentu, bisa Anda jelaskan lebih detail mengenai latar belakang masalah yang Anda angkat?", "metode": "Menarik. Coba uraikan metodologi penelitian yang akan Anda gunakan.", "kebaruan": "Apa aspek kebaruan atau orisinalitas utama dari penelitian yang Anda usulkan ini?"}
DEFAULT_DEMO_RESPONSE = "Itu poin yang menarik. Bisa tolong dielaborasi lebih lanjut?"

def get_demo_reply(transcript: str) -> str:
    """Memberikan jawaban berbasis skrip untuk Mode Demo."""
    lower_transcript = transcript.lower()
    for keyword, response in DEMO_RESPONSES.items():
        if keyword in lower_transcript: return response
    return DEFAULT_DEMO_RESPONSE

# --- PERBAIKAN KUNCI #2: Fungsi LLM Diperbarui ---
# Fungsi ini sekarang menerima 'chat_history' untuk memberikan konteks percakapan.
async def get_llm_reply(context_blocks: list, chat_history: list) -> str:
    if not GEMINI_API_KEY: return "Kunci API Gemini belum dikonfigurasi."

    # --- PERBAIKAN KUNCI #1: System Prompt yang Lebih Cerdas & Kontekstual ---
    # Prompt ini diubah untuk mendorong dialog, bukan interogasi.
    system_prompt = """
    Anda adalah AI Dosen Penguji bernama 'Mentora'. Peran Anda adalah sebagai mitra diskusi yang kritis namun suportif. Tujuan Anda bukan hanya menguji, tetapi membantu mahasiswa mengeksplorasi dan memperkuat argumen penelitiannya. Ciptakan alur diskusi yang alami dan dua arah.

    **Prinsip Utama: Pola "Dengar, Akui, Tanya"**
    Ini adalah kunci untuk membuat percakapan terasa alami.
    1.  **Dengar:** Pahami poin utama dari jawaban mahasiswa.
    2.  **Akui (Acknowledge):** Awali respons Anda dengan pengakuan singkat terhadap jawaban mereka. Ini menunjukkan Anda mendengarkan. Gunakan frasa seperti "Baik, saya paham poin Anda tentang...", "Menarik sekali penjelasan Anda mengenai...", atau "Oke, jadi Anda berpendapat bahwa...".
    3.  **Tanya (Inquire):** Ajukan pertanyaan lanjutan yang MENGALIR dari jawaban sebelumnya. Jangan melompat ke topik baru kecuali mahasiswa sudah tuntas menjawab.

    **Contoh Alur Percakapan yang Baik:**
    -   *Mahasiswa:* "...jadi saya menggunakan metode ABC karena lebih cepat dalam pemrosesan data."
    -   *Anda (Respons Buruk/Kaku):* "Apa kelemahan metode ABC?"
    -   *Anda (Respons BAIK/Alami):* "Poin yang bagus mengenai kecepatan proses. Namun, bagaimana Anda mengantisipasi masalah akurasi yang seringkali menjadi trade-off pada metode ABC?"

    **Aturan Gaya & Teknis:**
    -   **Jadilah Mitra Diskusi:** Jangan hanya bertanya. Anda boleh memberikan afirmasi singkat ("Itu penjelasan yang jernih.") sebelum bertanya.
    -   **Variasi Pertanyaan:** Gunakan berbagai jenis pertanyaan (klarifikasi, perbandingan, hipotetis) untuk menjaga dinamika. Hindari rentetan pertanyaan "Mengapa?" yang monoton.
    -   **Fokus pada Alur:** Usahakan pertanyaan baru selalu terkait dengan jawaban terakhir mahasiswa.
    -   **Jaga Tetap Singkat:** Respons Anda (pengakuan + pertanyaan) sebaiknya tetap dalam 1-3 kalimat agar mudah dipahami.
    -   **Output Wajib Teks Murni:** Jangan pernah gunakan Markdown (*, #, dll.). Ini penting untuk kompatibilitas Text-to-Speech (TTS).
    """

    # --- PERBAIKAN: Memformat ulang 'contents' agar sesuai dengan struktur yang diharapkan API ---
    # 1. Bangun daftar 'parts' (teks & gambar) dari konteks awal PDF.
    initial_parts = ["Berikut adalah konteks dari proposal skripsi mahasiswa untuk menjadi dasar diskusi:"]
    for block in context_blocks:
        if block["type"] == "text":
            initial_parts.append(block["content"])
        elif block["type"] == "image":
            if block.get("caption"):
                initial_parts.append(f"\nBerikut adalah gambar dengan keterangan: {block['caption']}")
            try:
                image_bytes = base64.b64decode(block["data"])
                img = Image.open(io.BytesIO(image_bytes))
                initial_parts.append(img)
            except Exception as e:
                print(f"Warning: Gagal memproses gambar untuk LLM. {e}")

    # 2. Buat daftar 'contents' API yang terstruktur dengan benar.
    #    Turn pertama berisi semua konteks PDF, dianggap sebagai pesan dari 'user'.
    api_contents = [
        {"role": "user", "parts": initial_parts}
    ]
    #    Tambahkan sisa riwayat percakapan.
    api_contents.extend(chat_history)

    try:
        # Menggunakan model yang konsisten dengan kode awal Anda
        model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_prompt)
        # Kirim 'api_contents' yang sudah terstruktur dengan benar.
        response = await model.generate_content_async(api_contents)
        return response.text
    except Exception as e:
        print(f"Error saat memanggil Gemini API: {e}")
        traceback.print_exc()
        return "Maaf, terjadi gangguan pada sistem AI saya. Bisa tolong ulangi?"

async def get_llm_score_and_feedback(full_transcript_str: str) -> dict:
    # Fungsi ini tidak perlu diubah secara signifikan
    if not GEMINI_API_KEY: return None
    
    system_prompt = """
    Anda adalah Dosen Penilai AI yang sangat kritis, tegas, namun adil. Tugas Anda adalah menganalisis transkrip jawaban mahasiswa secara dingin dan objektif, tanpa ada belas kasihan. Berikan penilaian kuantitatif dan kualitatif yang mencerminkan kualitas jawaban apa adanya berdasarkan rubrik yang ketat.

**Rubrik Penilaian (Terapkan dengan Tegas):**
- **relevance (Relevansi):** Skor 0 jika jawaban sedikitpun melenceng. Skor 100 HANYA jika jawaban sepenuhnya fokus dan langsung menjawab inti pertanyaan.
- **clarity (Kejelasan):** Skor 0 untuk jawaban yang berbelit-belit atau ambigu. Skor 100 HANYA untuk jawaban yang sangat terstruktur, lugas, dan menggunakan bahasa yang presisi.
- **mastery (Penguasaan):** Skor 0 jika ada keraguan sedikitpun dalam pemahaman. Skor 100 HANYA jika mahasiswa menunjukkan penguasaan materi yang mendalam, lengkap dengan terminologi yang tepat, justifikasi yang kuat, dan contoh konkret.

**Prinsip Umpan Balik (Kritis, Objektif, Membangun):**
- **Jangan Memberi Pujian Kosong:** Hindari frasa seperti "Jawaban Anda sudah cukup baik, namun...". Langsung ke pokok permasalahan.
- **Identifikasi Kelemahan Secara Spesifik:** Tunjukkan dengan jelas di mana letak kesalahan atau kelemahan jawaban. Contoh: "Jawaban Anda pada aspek metodologi masih terlalu umum. Anda menyebutkan akan menggunakan 'analisis data', tetapi tidak menjelaskan teknik spesifik apa (misalnya regresi, klasifikasi, atau clustering) yang relevan untuk hipotesis Anda."
- **Berikan Solusi atau Contoh Jawaban Ideal:** Umpan balik Anda WAJIB bersifat membangun. Setelah mengkritik, berikan contoh bagaimana jawaban tersebut bisa diperbaiki. Contoh: "Jawaban yang lebih kuat akan berbunyi: 'Saya akan menggunakan metode klasifikasi Naive Bayes karena data penelitian saya bersifat kategorikal dan saya ingin memprediksi label kelas...'."

**Aturan Penanganan Khusus:**
- Jika transkrip jawaban pengguna **HANYA** berisi basa-basi (misalnya, "baik, pak", "terima kasih", "oke"), tidak mengandung informasi substantif, atau terlalu singkat untuk dinilai, **WAJIB** berikan skor 0 untuk semua kategori dan berikan feedback: "Jawaban tidak mengandung informasi yang cukup untuk dinilai."

**Aturan Format Output:**
- HANYA berikan respons dalam format JSON yang valid. Jangan tambahkan teks atau penjelasan lain di luar struktur JSON.
- Struktur JSON WAJIB seperti ini:
{
    "relevance": <skor 0-100>,
    "clarity": <skor 0-100>,
    "mastery": <skor 0-100>,
    "feedback": "<umpan balik yang kritis, objektif, dan memberi solusi konkret>"
}
"""
    user_prompt = f"Analisislah HANYA bagian dari 'user' dari transkrip ini:\n--- TRANSKRIP ---\n{full_transcript_str}\n--- AKHIR TRANSKRIP ---\n\nBerikan skor dan umpan balik dalam format JSON."
    
    try:
        # Menggunakan model yang konsisten dengan kode awal Anda
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        config_gen = genai.types.GenerationConfig(response_mime_type="application/json")
        response = await model.generate_content_async([user_prompt], generation_config=config_gen)
        return json.loads(response.text)
    except Exception as e:
        print(f"Error saat memanggil Gemini API untuk penilaian: {e}")
        return None

async def synthesize_audio(text: str, speaker_id: str = "id-ID-Chirp3-HD-Achird") -> bytes:
    """
    Mensintesis teks menjadi audio menggunakan Google Cloud Text-to-Speech API.
    Kredensial diambil secara otomatis dari environment variable GOOGLE_APPLICATION_CREDENTIALS.
    """
    try:
        client = texttospeech.TextToSpeechAsyncClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(language_code="id-ID", name=speaker_id)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000
        )
        response = await client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        buffer = io.BytesIO()
        audio_array = np.frombuffer(response.audio_content, dtype=np.int16)
        sf.write(buffer, audio_array, 24000, format='WAV', subtype='PCM_16')
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        print(f"Gagal menghasilkan audio dari Google TTS: {e}")
        traceback.print_exc()
        return b""

def extract_title(full_text: str) -> str:
    try:
        end_pos = full_text.upper().find("ABSTRAK")
        search_block = full_text[:end_pos] if end_pos != -1 else full_text[:2500]
    except Exception:
        search_block = full_text[:2500]
    lines = [line.strip() for line in search_block.strip().split('\n') if line.strip()]
    longest_line = ""; best_candidate = ""
    for line in lines:
        if len(line) < 10 or any(keyword in line.upper() for keyword in ["SKRIPSI", "TESIS", "TUGAS AKHIR", "UNIVERSITAS"]):
            continue
        if len(line) > len(longest_line): longest_line = line
        if line.isupper() and len(line) > len(best_candidate): best_candidate = line
    final_title = best_candidate if best_candidate else longest_line
    return final_title if final_title else "Judul tidak ditemukan"

def extract_section(full_text: str, start_keys: list[str], end_keys: list[str]) -> str:
    text_upper = full_text.upper()
    search_offset = 0

    while True:
        potential_start_index = -1
        found_key = None
        
        for key in start_keys:
            pos = text_upper.find(key.upper(), search_offset)
            if pos != -1 and (potential_start_index == -1 or pos < potential_start_index):
                potential_start_index = pos
                found_key = key

        if potential_start_index == -1:
            return "" 

        line_end_pos = text_upper.find('\n', potential_start_index)
        if line_end_pos == -1: line_end_pos = len(text_upper)
        
        line_snippet = full_text[potential_start_index:line_end_pos]

        if '...' in line_snippet or line_snippet.count('.') > 10:
            search_offset = line_end_pos
            continue 

        start_index = potential_start_index
        break

    end_index = len(full_text)
    search_area = text_upper[start_index + len(found_key):]
    
    for end_key in end_keys:
        pos = search_area.find(end_key.upper())
        if pos != -1:
            line_start_pos = search_area.rfind('\n', 0, pos)
            if line_start_pos == -1: line_start_pos = 0
            
            line_of_end_key = search_area[line_start_pos:pos + len(end_key)]
            if any(char.isdigit() for char in line_of_end_key) or len(line_of_end_key.split()) < 5:
                end_index = start_index + len(found_key) + line_start_pos
                break

    return full_text[start_index:end_index].strip()


def create_and_upload_report(session_id: str, user_id: int, results_data: dict) -> str:
    """Membuat laporan PDF, mengunggahnya ke GCS, dan mengembalikan path GCS."""
    pdf = FPDF()
    pdf.add_page()
    try:
        # PENTING: Pastikan folder 'assets' ada di root proyek Anda dengan font di dalamnya
        font_path = "assets"
        pdf.add_font('DejaVu', '', os.path.join(font_path, "DejaVuSans.ttf"), uni=True)
        pdf.add_font('DejaVu', 'B', os.path.join(font_path, "DejaVuSans-Bold.ttf"), uni=True)
        pdf.set_font('DejaVu', 'B', 18)
    except RuntimeError:
        print("PERINGATAN: Font DejaVu tidak ditemukan. Menggunakan Arial (mungkin ada masalah karakter).")
        pdf.set_font('Arial', 'B', 18)
    
    pdf.cell(0, 10, "Laporan Hasil Simulasi Seminar Proposal", ln=True, align='C')
    pdf.set_font('DejaVu', '', 10); pdf.cell(0, 8, f"ID Sesi: {session_id}", ln=True, align='C')
    pdf.cell(0, 8, f"Tanggal: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C'); pdf.ln(10)
    pdf.set_font('DejaVu', 'B', 14); pdf.cell(0, 10, f"SKOR AKHIR: {results_data.get('final_score', 'N/A')} / 100", ln=True)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y()); pdf.ln(5)
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(0, 10, "Umpan Balik dari AI Penilai:", ln=True)
    
    pdf.set_font('DejaVu', '', 11); pdf.multi_cell(0, 5, results_data.get('feedback', 'Tidak ada umpan balik.'))
    pdf.ln(5)
    
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(0, 10, "Rincian Penilaian:", ln=True)
    pdf.set_font('DejaVu', '', 11)
    bd = results_data.get('breakdown', {})
    pdf.cell(0, 6, f"- Relevansi Jawaban: {bd.get('relevance', 'N/A')} / 100", ln=True)
    pdf.cell(0, 6, f"- Kejelasan Penyampaian: {bd.get('clarity', 'N/A')} / 100", ln=True)
    pdf.cell(0, 6, f"- Penguasaan Materi: {bd.get('mastery', 'N/A')} / 100", ln=True); pdf.ln(10)
    pdf.set_font('DejaVu', 'B', 14); pdf.cell(0, 10, "Transkrip Lengkap", ln=True)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y()); pdf.ln(5)

    pdf.set_font('DejaVu', '', 10); pdf.multi_cell(0, 5, results_data.get('transcript', 'Transkrip tidak tersedia.'))
    
    # --- PERBAIKAN: Konversi eksplisit dari bytearray ke bytes untuk kompatibilitas GCS ---
    pdf_bytes = bytes(pdf.output())

    if not GCS_BUCKET_NAME:
        raise Exception("Nama bucket GCS tidak dikonfigurasi.")

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        gcs_path = f"user_{user_id}/report_{session_id}.pdf"
        blob = bucket.blob(gcs_path)
        blob.upload_from_string(pdf_bytes, content_type='application/pdf')
        print(f"Laporan berhasil diunggah ke: gs://{GCS_BUCKET_NAME}/{gcs_path}")
        return gcs_path
    except Exception as e:
        print(f"Gagal mengunggah ke GCS: {e}")
        traceback.print_exc()
        raise

# --- HTTP Endpoints ---

@app.post("/upload", response_model=schemas.UploadResponse)
async def handle_file_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Format file tidak didukung.")
    
    doc = None
    try:
        file_bytes = await file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = "".join(page.get_text() for page in doc)

        title = extract_title(full_text)
        abstract = extract_section(full_text, ["ABSTRAK", "ABSTRACT"], ["KATA KUNCI", "PENDAHULUAN", "BAB I", "I. PENDAHULUAN"])
        rumusan_masalah = extract_section(full_text, ["RUMUSAN MASALAH"], ["TUJUAN PENELITIAN", "BATASAN MASALAH"])
        tujuan_penelitian = extract_section(full_text, ["TUJUAN PENELITIAN"], ["MANFAAT PENELITIAN", "BATASAN MASALAH", "BAB II"])
        metodologi_text = extract_section(full_text, ["METODOLOGI PENELITIAN","METODE PENELITIAN", "BAB III", "III. METODE"], ["HASIL DAN PEMBAHASAN", "BAB IV"])

        if not abstract and not metodologi_text: raise HTTPException(status_code=422, detail="Gagal mengekstrak konten utama.")
        
        context_blocks = [
            {"type": "text", "content": f"[JUDUL]\n{title}"},
            {"type": "text", "content": f"[ABSTRAK]\n{abstract}"},
            {"type": "text", "content": f"[RUMUSAN MASALAH]\n{rumusan_masalah}"},
            {"type": "text", "content": f"[TUJUAN PENELITIAN]\n{tujuan_penelitian}"},
            {"type": "text", "content": f"[METODOLOGI]\n{metodologi_text}"}
        ]
        
        for page_num, page in enumerate(doc):
            page_text_lower = page.get_text("text").lower()
            if "metodologi" in page_text_lower or "metode" in page_text_lower:
                for img in page.get_images(full=True):
                    xref = img[0]; base_image = doc.extract_image(xref)
                    image_bytes, image_ext = base_image["image"], base_image["ext"]
                    b64_img = base64.b64encode(image_bytes).decode('utf-8')
                    context_blocks.append({"type": "image", "mime_type": f"image/{image_ext}", "data": b64_img, "caption": f"Gambar dari bab metodologi (Halaman {page_num + 1})"})
        
        session_id = str(uuid.uuid4())
        db_session = models.SimulationSession(
            id=session_id,
            user_id=current_user.id,
            context_data=json.dumps(context_blocks),
            title=title,
            filename=file.filename,
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        return schemas.UploadResponse(
            status="success",
            session_id=session_id,
            filename=file.filename,
            title=title,
            context_summary=abstract[:500] + "...",
            rumusan_masalah=rumusan_masalah,
            tujuan_penelitian=tujuan_penelitian,
            metodologi=metodologi_text[:1000] + "..."
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan internal: {e}")
    finally:
        if doc: doc.close()

@app.post("/score", response_model=schemas.ScoreResponse)
async def handle_scoring(
    request: schemas.ScoreRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_session = db.query(models.SimulationSession).filter(
        models.SimulationSession.id == request.session_id,
        models.SimulationSession.user_id == current_user.id
    ).first()

    if not db_session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan atau bukan milik Anda.")

    # --- FIX: Mengakses data dari Pydantic model menggunakan dot notation (objek), bukan dict ---
    transcript_str = "\n".join([f"{entry.speaker}: {entry.text}" for entry in request.full_transcript])
    score_data = await get_llm_score_and_feedback(transcript_str)
    
    if not score_data:
        raise HTTPException(status_code=500, detail="Gagal mendapatkan penilaian dari AI.")

    final_score = round((score_data.get('relevance', 0) + score_data.get('clarity', 0) + score_data.get('mastery', 0)) / 3, 2)
    results_to_store = {
        "final_score": final_score, 
        "feedback": score_data.get('feedback', ''), 
        "breakdown": score_data, 
        "transcript": transcript_str
    }
    
    gcs_path = None
    download_url = None

    try:
        gcs_path = create_and_upload_report(
            session_id=request.session_id,
            user_id=current_user.id,
            results_data=results_to_store
        )
        db_session.final_score = final_score
        db_session.feedback = score_data.get('feedback', '')
        db_session.pdf_gcs_path = gcs_path
        db_session.is_completed = True
        db.commit()

        if gcs_path and GCS_BUCKET_NAME:
            try:
                storage_client = storage.Client()
                bucket = storage_client.bucket(GCS_BUCKET_NAME)
                blob = bucket.blob(gcs_path)
                download_url = blob.generate_signed_url(expiration=timedelta(hours=1))
            except Exception as e:
                print(f"Gagal membuat signed URL setelah upload: {e}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan laporan: {e}")

    breakdown_model = schemas.ScoreBreakdown(**score_data)
    
    return schemas.ScoreResponse(
        status="success", 
        final_score=final_score, 
        feedback=score_data.get('feedback', ''), 
        breakdown=breakdown_model,
        download_url=download_url
    )


@app.get("/speakers")
async def get_speakers():
    return {"speakers": list(GOOGLE_TTS_VOICES.keys())}

@app.get("/history", response_model=list[schemas.SessionHistoryItem])
def get_session_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    sessions = db.query(models.SimulationSession).filter(
        models.SimulationSession.user_id == current_user.id,
        models.SimulationSession.is_completed == True
    ).order_by(models.SimulationSession.created_at.desc()).all()
    
    history_items = []
    
    storage_client = None
    bucket = None
    if GCS_BUCKET_NAME:
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
        except Exception as e:
            print(f"Error initializing GCS Client: {e}")

    for session in sessions:
        download_url = None
        if session.pdf_gcs_path and bucket:
            try:
                blob = bucket.blob(session.pdf_gcs_path)
                if blob.exists():
                    download_url = blob.generate_signed_url(expiration=timedelta(hours=1))
                else:
                    print(f"Warning: Blob not found for path: {session.pdf_gcs_path}")
            except Exception as e:
                print(f"Gagal membuat signed URL untuk {session.pdf_gcs_path}: {e}")
        
        history_items.append(
            schemas.SessionHistoryItem(
                session_id=session.id,
                title=session.title,
                filename=session.filename,
                created_at=session.created_at,
                final_score=session.final_score,
                download_url=download_url
            )
        )
    return history_items

@app.websocket("/ws/session/{session_id}")
async def websocket_session_handler(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    mode: str = "simulasi",
    speaker: str = None,
):
    await websocket.accept()
    db: Session = SessionLocal()
    
    try:
        user = auth.get_current_user_from_token(db, token)
        if not user:
            await websocket.close(code=4001, reason="Token tidak valid atau kedaluwarsa")
            return

        db_session = db.query(models.SimulationSession).filter(
            models.SimulationSession.id == session_id,
            models.SimulationSession.user_id == user.id
        ).first()

        if not db_session:
            await websocket.close(code=1008, reason="Sesi tidak valid atau bukan milik Anda.")
            return
        
        context = json.loads(db_session.context_data)
        # --- PERBAIKAN FINAL: Mengubah fallback default ke suara Chirp yang valid ---
        voice_name = GOOGLE_TTS_VOICES.get(speaker, "id-ID-Chirp3-HD-Achird")

        # --- PERUBAIKAN KUNCI #4: Inisialisasi Sejarah Percakapan ---
        chat_history = []

        greeting = "Selamat datang di simulasi seminar proposal. Silakan mulai presentasi Anda kapan pun Anda siap."
        await websocket.send_json({"type": "dosen_reply_start", "text": greeting})
        greeting_audio = await synthesize_audio(greeting, speaker_id=voice_name)
        if greeting_audio: await websocket.send_bytes(greeting_audio)
        
        chat_history.append({"role": "model", "parts": [{"text": greeting}]})
        
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") == "user_transcript":
                transcript = data.get("text", "").strip()
                if not transcript: continue
                
                chat_history.append({"role": "user", "parts": [{"text": transcript}]})

                start_time_utc = db_session.created_at.replace(tzinfo=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                remaining_seconds = (timedelta(minutes=30) - (now_utc - start_time_utc)).total_seconds()
                is_session_ending = remaining_seconds <= 30
                
                if is_session_ending:
                    reply_text = "Baik, waktu sesi Anda hampir habis. Sesi ini akan segera berakhir."
                elif mode == "demo":
                    reply_text = get_demo_reply(transcript)
                else:
                    reply_text = await get_llm_reply(context, chat_history)
                
                if reply_text:
                    chat_history.append({"role": "model", "parts": [{"text": reply_text}]})
                    
                    if len(chat_history) > 20:
                        chat_history = chat_history[-20:]

                    if is_session_ending:
                        await websocket.send_json({"type": "session_ending"})
                    
                    await websocket.send_json({"type": "dosen_reply_start", "text": reply_text})
                    audio_bytes = await synthesize_audio(reply_text, speaker_id=voice_name)
                    if audio_bytes:
                        await websocket.send_bytes(audio_bytes)
                    
                    if is_session_ending:
                        await websocket.close(code=1000)
                        break

    except WebSocketDisconnect:
        print(f"Klien terputus dari sesi: {session_id}")
    except Exception as e:
        print(f"Error pada sesi WebSocket {session_id}: {e}")
        traceback.print_exc()
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        db.close()

