import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Ambil URL Database dari environment variables ---
# Contoh untuk PostgreSQL: "postgresql://user:password@host:port/dbname"
# Contoh untuk MySQL: "mysql+pymysql://user:password@host:port/dbname"
# Contoh untuk SQLite (development): "sqlite:///./test.db"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mentora.db")

engine = create_engine(
    DATABASE_URL,
    # connect_args diperlukan untuk SQLite, bisa dihapus untuk PostgreSQL/MySQL
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
