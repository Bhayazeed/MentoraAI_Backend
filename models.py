from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("SimulationSession", back_populates="owner")


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"

    # Menggunakan String untuk UUID agar kompatibel dengan semua DB
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String, nullable=True)
    filename = Column(String, nullable=True) # FIX: Menambahkan kolom filename
    context_data = Column(Text, nullable=False) # Menyimpan JSON dari context_blocks
    final_score = Column(Float, nullable=True) # Diubah ke Float agar konsisten dengan schema
    feedback = Column(Text, nullable=True)
    pdf_gcs_path = Column(String, nullable=True) # Path ke file di GCS
    is_completed = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="sessions")
