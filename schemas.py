from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# --- Schemas for User & Auth ---

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True # DIGANTI dari orm_mode

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


# --- Schemas for Transcript & Scoring ---

class TranscriptEntry(BaseModel):
    speaker: str
    text: str

class ScoreBreakdown(BaseModel):
    relevance: int
    clarity: int
    mastery: int

class ScoreRequest(BaseModel):
    session_id: str
    full_transcript: List[TranscriptEntry]

class ScoreResponse(BaseModel):
    status: str
    final_score: float
    feedback: str
    breakdown: ScoreBreakdown
    download_url: Optional[str] = None

# --- Schemas for File Upload ---

class UploadResponse(BaseModel):
    status: str
    session_id: str
    filename: str
    title: str
    context_summary: str
    rumusan_masalah: str
    tujuan_penelitian: str
    metodologi: str

# --- Schema for Session History ---

class SessionHistoryItem(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    final_score: Optional[float] = None
    download_url: Optional[str] = None
    
    class Config:
        from_attributes = True # DIGANTI dari orm_mode

