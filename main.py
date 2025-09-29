import os
import uuid
import fitz  # PyMuPDF
import json
import base64
import traceback
import io
from datetime import datetime, timedelta, timezone # FIX: Impor timezone

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

# --- MODIFIKASI: Menambahkan CORS Middleware untuk frontend ---
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

# --- Daftar Suara Google TTS (tetap sama) ---
GOOGLE_TTS_VOICES = {
    "Pria - A (Standar)": "id-ID-Standard-A",
    "Pria - B (Standar)": "id-ID-Standard-B",
    "Pria - C (Standar)": "id-ID-Standard-C",
    "Wanita - D (Standar)": "id-ID-Standard-D",
}

# --- MODIFIKASI: Dependensi untuk mendapatkan sesi database ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DEMO_RESPONSES = { "latar belakang": "Mode Demo: Tentu, bisa Anda jelaskan lebih detail mengenai latar belakang masalah yang Anda angkat?", "metode": "Mode Demo: Menarik. Coba uraikan metodologi penelitian yang akan Anda gunakan.", "kebaruan": "Mode Demo: Apa aspek kebaruan atau orisinalitas utama dari penelitian yang Anda usulkan ini?"}
DEFAULT_DEMO_RESPONSE = "Mode Demo: Itu poin yang menarik. Bisa tolong dielaborasi lebih lanjut?"

def get_demo_reply(transcript: str) -> str:
    """Memberikan jawaban berbasis skrip untuk Mode Demo."""
    lower_transcript = transcript.lower()
    for keyword, response in DEMO_RESPONSES.items():
        if keyword in lower_transcript: return response
    return DEFAULT_DEMO_RESPONSE

async def get_llm_reply(context_blocks: list, transcript: str) -> str:
    # Fungsi ini tidak perlu diubah secara signifikan
    if not GEMINI_API_KEY: return "Kunci API Gemini belum dikonfigurasi."
    system_prompt = """
    Anda adalah AI Dosen Penguji bernama 'Mentora'. Peran Anda adalah menjadi penguji yang kritis, adil, namun juga komunikatif dan mendukung. Tujuan utama Anda adalah menguji pemahaman dan alur berpikir mahasiswa secara mendalam, bukan hanya pengetahuan teknis. Anggap diri Anda sebagai mitra diskusi yang mendorong mahasiswa untuk merefleksikan pilihan-pilihan dalam penelitiannya.

Prinsip Utama: Menggali Pemahaman, Bukan Hanya Menguji (Fokus 5W1H)
Gunakan kerangka 5W1H untuk menyusun pertanyaan yang menggali pemikiran di balik penelitian. Prioritaskan pertanyaan "Mengapa" dan "Bagaimana".

MENGAPA (Untuk Menguji Justifikasi & Rationale):
Ini adalah jenis pertanyaan yang paling penting. Tanyakan alasan di balik setiap keputusan penting.
Contoh: "Mengapa Anda memilih menggunakan variabel X untuk penelitian ini, dan bukan variabel Y yang juga sering dibahas?"
Contoh: "Apa justifikasi utama di balik pemilihan metode Analisis Sentimen? Mengapa metode ini Anda anggap lebih signifikan untuk menangani set data Anda dibandingkan metode lain?"
Contoh: "Mengapa rumusan masalah ini yang Anda angkat? Apa yang membuatnya relevan untuk diteliti saat ini?"

BAGAIMANA (Untuk Menguji Proses & Penerapan):
Tanyakan tentang langkah-langkah konkret dan cara mengatasi tantangan.
Contoh: "Bagaimana Anda berencana untuk mengukur validitas dari data yang Anda kumpulkan?"
Contoh: "Jika Anda menemukan hasil yang tidak sesuai dengan hipotesis awal, bagaimana langkah Anda selanjutnya?"
Contoh: "Bagaimana Anda akan memastikan metode yang Anda usulkan dapat diterapkan pada skala yang lebih besar?"

APA (Untuk Menguji Klarifikasi & Konsep Dasar):
Gunakan ini untuk memastikan pemahaman dasar atau untuk meminta detail lebih lanjut.
Contoh: "Apa definisi operasional dari 'kepuasan pengguna' dalam konteks penelitian Anda?"
Contoh: "Apa saja batasan-batasan utama dari penelitian yang Anda usulkan ini?"

PERTANYAAN HIPOTETIS & PERBANDINGAN:
Dorong mahasiswa untuk berpikir di luar proposal mereka.
Contoh: "Apa kelemahan terbesar dari metode yang Anda pilih, dan bagaimana Anda mencoba memitigasinya?"
Contoh: "Andai kata Anda memiliki sumber daya tak terbatas, apa satu hal yang akan Anda tambahkan pada penelitian ini untuk membuatnya lebih kuat?"

Strategi Eskalasi Pertanyaan (Sangat Penting):
Ini adalah cara Anda merespons jawaban mahasiswa untuk menciptakan alur diskusi yang dinamis.

Jika jawaban mahasiswa bersifat umum atau kurang detail (contoh: "itu kurang maksimal"):
Tindakan: Jangan ulangi pertanyaan awal. Ajukan pertanyaan pendalaman yang meminta detail spesifik.
Contoh: "Menarik. Anda menyebutkan 'kurang maksimal', bisa tolong jelaskan dalam aspek apa saja metode Waterfall akan kurang maksimal untuk proyek spesifik Anda ini?"
Contoh: "Apa tantangan konkret yang Anda bayangkan jika memakai Waterfall?"

Jika mahasiswa sudah memberikan jawaban yang baik pada satu topik:
Tindakan: Beralihlah ke aspek lain dari presentasi untuk memperluas cakupan ujian. Gunakan frasa penghubung.
Contoh: "Baik, penjelasan Anda mengenai metodologi sudah cukup jelas. Sekarang, mari kita beralih ke bagian rumusan masalah..."

Aturan Teknis & Gaya Bahasa:
Tugas utama: Selalu ajukan pertanyaan. Jangan memberikan jawaban, kesimpulan, atau petunjuk.
Gaya bahasa: Gunakan bahasa yang lugas, komunikatif, dan mudah dipahami. Hindari jargon yang tidak perlu.
Singkat & fokus: Jaga setiap pertanyaan tetap singkat (1-2 kalimat).
Format output: Hasilkan hanya teks murni (plain text). Jangan pernah menggunakan markdown, asterisks, atau format khusus lainnya agar kompatibel dengan Text-to-Speech (TTS).
Tanda baca: Gunakan tanda baca Bahasa Indonesia yang standar untuk intonasi yang benar.
    """
    contents = ["Berikut adalah konteks dari proposal skripsi mahasiswa:"]
    for block in context_blocks:
        if block["type"] == "text":
            contents.append(block["content"])
        elif block["type"] == "image":
            if block.get("caption"):
                contents.append(f"\nBerikut adalah gambar dengan keterangan: {block['caption']}")
            image_bytes = base64.b64decode(block["data"])
            img = Image.open(io.BytesIO(image_bytes))
            contents.append(img)
    contents.append(f"\nUcapan terakhir mahasiswa: \"{transcript}\"\n\nBerdasarkan semua konteks di atas, ajukan satu pertanyaan lanjutan yang spesifik.")
    try:
        model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_prompt)
        response = await model.generate_content_async(contents)
        return response.text
    except Exception as e:
        print(f"Error saat memanggil Gemini API multi-modal: {e}")
        return "Maaf, terjadi gangguan pada sistem AI saya. Bisa tolong ulangi?"

async def get_llm_score_and_feedback(full_transcript_str: str) -> dict:
    """
    Fungsi ini adalah "otak" dari AI Penilai. Ia meminta Gemini untuk menganalisis
    transkrip dan mengembalikan hasilnya dalam format JSON yang ketat.
    """
    if not GEMINI_API_KEY: return None
    
    system_prompt = """
    Anda adalah Dosen Penilai AI yang objektif dan analitis. Tugas Anda adalah menganalisis transkrip jawaban mahasiswa dan memberikan penilaian kuantitatif serta kualitatif berdasarkan rubrik yang ditentukan.

**Rubrik Penilaian:**
- **relevance (Relevansi):** Skor 0 jika jawaban sama sekali tidak menjawab pertanyaan. Skor 100 jika jawaban sepenuhnya fokus pada pertanyaan yang diajukan.
- **clarity (Kejelasan):** Skor 0 untuk jawaban yang tidak bisa dipahami. Skor 100 untuk jawaban yang terstruktur, jelas, dan menggunakan bahasa yang mudah dimengerti.
- **mastery (Penguasaan):** Skor 0 jika tidak ada pemahaman yang ditunjukkan. Skor 100 jika mahasiswa menunjukkan pemahaman mendalam, menggunakan terminologi yang tepat, dan memberikan contoh atau justifikasi yang kuat.

**Aturan Penanganan Khusus:**
- Jika transkrip jawaban pengguna **HANYA** berisi basa-basi (misalnya, "baik, pak", "terima kasih", "oke"), tidak mengandung informasi substantif, atau terlalu singkat untuk dinilai, **WAJIB** berikan skor 0 untuk semua kategori dan berikan feedback: "Jawaban tidak mengandung informasi yang cukup untuk dinilai."

**Aturan Format Output:**
- HANYA berikan respons dalam format JSON yang valid. Jangan tambahkan teks atau penjelasan lain di luar struktur JSON.
- Struktur JSON WAJIB seperti ini:
{
  "relevance": <skor 0-100>,
  "clarity": <skor 0-100>,
  "mastery": <skor 0-100>,
  "feedback": "<umpan balik yang rinci dan memberi solusi>"
}
"""
    user_prompt = f"Analisislah HANYA bagian dari 'user' dari transkrip ini:\n--- TRANSKRIP ---\n{full_transcript_str}\n--- AKHIR TRANSKRIP ---\n\nBerikan skor dan umpan balik dalam format JSON."
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_prompt)
        config_gen = genai.types.GenerationConfig(response_mime_type="application/json")
        response = await model.generate_content_async([user_prompt], generation_config=config_gen)
        return json.loads(response.text)
    except Exception as e:
        print(f"Error saat memanggil Gemini API untuk penilaian: {e}")
        return None

async def synthesize_audio(text: str, speaker_id: str = "id-ID-Standard-B") -> bytes:
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
        # Cari kemunculan kata kunci berikutnya
        potential_start_index = -1
        found_key = None
        
        for key in start_keys:
            pos = text_upper.find(key, search_offset)
            if pos != -1 and (potential_start_index == -1 or pos < potential_start_index):
                potential_start_index = pos
                found_key = key

        if potential_start_index == -1:
            return ""  # Tidak ada lagi kata kunci yang ditemukan

        # Cek apakah baris ini terlihat seperti entri Daftar Isi
        line_end_pos = text_upper.find('\n', potential_start_index)
        if line_end_pos == -1:
            line_end_pos = len(text_upper)
        
        line_snippet = full_text[potential_start_index:line_end_pos]

        # Heuristik: Jika baris mengandung '...' atau banyak titik, anggap sebagai Daftar Isi
        if '...' in line_snippet or line_snippet.count('.') > 10:
            search_offset = line_end_pos
            continue  # Abaikan dan cari kemunculan berikutnya

        # Jika lolos validasi, lanjutkan dengan ekstraksi dari titik ini
        start_index = potential_start_index
        break

    # Logika ekstraksi asli dari titik awal yang valid
    end_index = len(full_text)
    search_area = text_upper[start_index + len(found_key):]
    
    for end_key in end_keys:
        pos = search_area.find(end_key)
        if pos != -1:
            end_index = start_index + len(found_key) + pos
            break
            
    return full_text[start_index:end_index].strip()


def create_and_upload_report(session_id: str, user_id: int, results_data: dict) -> str:
    """Membuat laporan PDF, mengunggahnya ke GCS, dan mengembalikan path GCS."""
    pdf = FPDF()
    pdf.add_page()
    try:
        # Menambahkan font yang mendukung Unicode (PENTING!)
        font_path = "assets"  # Asumsi ada folder 'assets' dengan font
        pdf.add_font('DejaVu', '', os.path.join(font_path, "DejaVuSans.ttf"), uni=True)
        pdf.add_font('DejaVu', 'B', os.path.join(font_path, "DejaVuSans-Bold.ttf"), uni=True)
        pdf.set_font('DejaVu', '', 12)
    except RuntimeError:
        print("PERINGATAN: Font DejaVu tidak ditemukan. Menggunakan Arial (mungkin ada masalah karakter).")
        pdf.set_font('Arial', '', 12)
   
    pdf.set_font('DejaVu', 'B', 18); pdf.cell(0, 10, "Laporan Hasil Simulasi Seminar Proposal", ln=True, align='C')
    pdf.set_font('DejaVu', '', 10); pdf.cell(0, 8, f"ID Sesi: {session_id}", ln=True, align='C')
    pdf.cell(0, 8, f"Tanggal: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C'); pdf.ln(10)
    pdf.set_font('DejaVu', 'B', 14); pdf.cell(0, 10, f"SKOR AKHIR: {results_data.get('final_score', 'N/A')} / 100", ln=True)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y()); pdf.ln(5)
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(0, 10, "Umpan Balik dari AI Penilai:", ln=True)
    pdf.set_font('DejaVu', '', 11); pdf.multi_cell(0, 5, results_data.get('feedback', 'Tidak ada umpan balik.').encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(0, 10, "Rincian Penilaian:", ln=True)
    pdf.set_font('DejaVu', '', 11)
    bd = results_data.get('breakdown', {})
    pdf.cell(0, 6, f"- Relevansi Jawaban: {bd.get('relevance', 'N/A')} / 100", ln=True)
    pdf.cell(0, 6, f"- Kejelasan Penyampaian: {bd.get('clarity', 'N/A')} / 100", ln=True)
    pdf.cell(0, 6, f"- Penguasaan Materi: {bd.get('mastery', 'N/A')} / 100", ln=True); pdf.ln(10)
    pdf.set_font('DejaVu', 'B', 14); pdf.cell(0, 10, "Transkrip Lengkap", ln=True)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y()); pdf.ln(5)
    pdf.set_font('DejaVu', '', 10); pdf.multi_cell(0, 5, results_data.get('transcript', 'Transkrip tidak tersedia.').encode('latin-1', 'replace').decode('latin-1'))
    pdf_bytes = bytes(pdf.output())

    if not GCS_BUCKET_NAME:
        raise Exception("Nama bucket GCS tidak dikonfigurasi.")

    # Upload ke GCS
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        # Struktur path: user_<user_id>/<session_id>.pdf
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
    # Endpoint ini sekarang terproteksi dan memerlukan login
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Format file tidak didukung.")
    
    doc = None
    try:
        file_bytes = await file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = "".join(page.get_text() for page in doc)
        # Ekstrak semua bagian yang relevan
        title = extract_title(full_text)
        abstract = extract_section(full_text, ["ABSTRAK", "ABSTRACT"], ["KATA KUNCI", "PENDAHULUAN", "BAB I"])
        rumusan_masalah = extract_section(full_text, ["RUMUSAN MASALAH"], ["TUJUAN PENELITIAN", "BATASAN MASALAH"])
        tujuan_penelitian = extract_section(full_text, ["TUJUAN PENELITIAN"], ["MANFAAT PENELITIAN", "BATASAN MASALAH", "BAB II"])
        metodologi_text = extract_section(full_text, ["METODOLOGI PENELITIAN","METODE PENELITIAN", "BAB III"], ["HASIL DAN PEMBAHASAN", "BAB IV"])

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
    # Endpoint ini juga terproteksi
    db_session = db.query(models.SimulationSession).filter(
        models.SimulationSession.id == request.session_id,
        models.SimulationSession.user_id == current_user.id
    ).first()

    if not db_session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan atau bukan milik Anda.")

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
    
    gcs_path = None # Inisialisasi gcs_path
    download_url = None # Inisialisasi download_url

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

        # --- LOGIKA BARU: BUAT SIGNED URL LANGSUNG DI SINI ---
        if gcs_path and GCS_BUCKET_NAME:
            try:
                storage_client = storage.Client()
                bucket = storage_client.bucket(GCS_BUCKET_NAME)
                blob = bucket.blob(gcs_path)
                # Buat URL yang berlaku selama 1 jam
                download_url = blob.generate_signed_url(expiration=timedelta(hours=1))
            except Exception as e:
                print(f"Gagal membuat signed URL setelah upload: {e}")
                # Biarkan download_url tetap None jika gagal, agar tidak menghentikan proses

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan laporan: {e}")

    breakdown_model = schemas.ScoreBreakdown(**score_data)
    
    return schemas.ScoreResponse(
        status="success", 
        final_score=final_score, 
        feedback=score_data.get('feedback', ''), 
        breakdown=breakdown_model,
        download_url=download_url # TAMBAHKAN INI DI DALAM RESPONS
    )


@app.get("/speakers")
async def get_speakers():
    """Endpoint untuk menyediakan daftar suara Google TTS yang tersedia ke frontend."""
    return {"speakers": list(GOOGLE_TTS_VOICES.keys())}

# --- BARU: Endpoint untuk riwayat sesi ---
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
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)

    for session in sessions:
        download_url = None
        if session.pdf_gcs_path:
            try:
                blob = bucket.blob(session.pdf_gcs_path)
                # Buat URL yang berlaku selama 1 jam
                download_url = blob.generate_signed_url(expiration=timedelta(hours=1))
            except Exception as e:
                print(f"Gagal membuat signed URL untuk {session.pdf_gcs_path}: {e}")
        
        history_items.append(
            schemas.SessionHistoryItem(
                session_id=session.id,
                title=session.title,
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

    print(f"--- [DEBUG] WebSocket handler dimulai untuk sesi: {session_id} ---")
    
    try:
        user = auth.get_current_user_from_token(db, token)
        if not user:
            print("[DEBUG] GAGAL: Token tidak valid atau user tidak ditemukan.")
            await websocket.close(code=4001, reason="Token tidak valid atau kedaluwarsa")
            return

        print(f"[DEBUG] BERHASIL: User ditemukan -> {user.email}")

        db_session = db.query(models.SimulationSession).filter(
            models.SimulationSession.id == session_id,
            models.SimulationSession.user_id == user.id
        ).first()

        if not db_session:
            print(f"[DEBUG] GAGAL: Sesi ID '{session_id}' tidak ditemukan untuk user '{user.email}'.")
            await websocket.close(code=1008, reason="Sesi tidak valid atau bukan milik Anda.")
            return
        
        print(f"[DEBUG] BERHASIL: Sesi DB ditemukan -> {db_session.id}")

        context = json.loads(db_session.context_data)
        
        # FIX 1: Membuat kedua datetime menjadi timezone-aware (UTC) untuk perbandingan
        start_time_utc = db_session.created_at
        
        voice_name = GOOGLE_TTS_VOICES.get(speaker, "id-ID-Standard-B")

        greeting = "Selamat datang di simulasi seminar proposal. Silakan mulai presentasi Anda."
        await websocket.send_json({"type": "dosen_reply_start", "text": greeting})
        greeting_audio = await synthesize_audio(greeting, speaker_id=voice_name)
        if greeting_audio: await websocket.send_bytes(greeting_audio)
        
        print("[DEBUG] Memasuki loop utama (while True). Koneksi seharusnya stabil sekarang.")

        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") == "user_transcript":
                transcript = data.get("text", "").strip()
                if not transcript: continue
                
                # Menggunakan start_time_utc yang sudah timezone-aware
                now_utc = datetime.now(timezone.utc)
                remaining_seconds = (timedelta(minutes=30) - (now_utc - start_time_utc)).total_seconds()
                is_session_ending = remaining_seconds <= 30
                
                if is_session_ending:
                    reply_text = "Baik, waktu sesi Anda hampir habis. Sesi ini akan segera berakhir."
                elif mode == "demo":
                    # FIX 4: Memanggil fungsi get_demo_reply yang benar
                    reply_text = get_demo_reply(transcript)
                else:
                    reply_text = await get_llm_reply(context, transcript)
                
                if reply_text:
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

