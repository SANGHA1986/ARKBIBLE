from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# MVP용 로컬 데이터베이스 (추후 PostgreSQL로 연결 문자열만 변경하면 바로 전환됨)
SQLALCHEMY_DATABASE_URL = "sqlite:///./ark_knowledge_graph.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 60},
)

# SQLite WAL: 읽기/쓰기 동시성·락 대기 완화
try:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _connection_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.close()
except Exception:
    pass
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
