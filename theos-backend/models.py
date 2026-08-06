from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table, Boolean, DateTime, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import datetime

# ==========================================
# 다차원 탐색망을 위한 Association Tables (N:M 매핑)
# ==========================================
verse_character = Table('verse_character', Base.metadata, Column('verse_id', Integer, ForeignKey('verses.id')), Column('character_id', Integer, ForeignKey('characters.id')))
verse_event = Table('verse_event', Base.metadata, Column('verse_id', Integer, ForeignKey('verses.id')), Column('event_id', Integer, ForeignKey('events.id')))
verse_location = Table('verse_location', Base.metadata, Column('verse_id', Integer, ForeignKey('verses.id')), Column('location_id', Integer, ForeignKey('locations.id')))
verse_concept = Table('verse_concept', Base.metadata, Column('verse_id', Integer, ForeignKey('verses.id')), Column('concept_id', Integer, ForeignKey('concepts.id')))
verse_language = Table('verse_language', Base.metadata, Column('verse_id', Integer, ForeignKey('verses.id')), Column('language_id', Integer, ForeignKey('language_data.id')))

event_character = Table('event_character', Base.metadata, Column('event_id', Integer, ForeignKey('events.id')), Column('character_id', Integer, ForeignKey('characters.id')))
event_location = Table('event_location', Base.metadata, Column('event_id', Integer, ForeignKey('events.id')), Column('location_id', Integer, ForeignKey('locations.id')))

concept_doctrine = Table('concept_doctrine', Base.metadata, Column('concept_id', Integer, ForeignKey('concepts.id')), Column('doctrine_id', Integer, ForeignKey('doctrines.id')))

# ==========================================
# 1. 성경 핵심 뼈대
# ==========================================
class BibleBook(Base):
    __tablename__ = "bible_books"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    testament = Column(String(20))
    verses = relationship("Verse", back_populates="book")

class Verse(Base):
    __tablename__ = "verses"
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("bible_books.id"))
    chapter_num = Column(Integer, nullable=False)
    verse_num = Column(Integer, nullable=False)
    text_ko = Column(Text, nullable=False)
    text_en = Column(Text)  # 공개 영문(WEB 등)
    text_original = Column(Text)
    
    book = relationship("BibleBook", back_populates="verses")
    interpretations = relationship("Interpretation", back_populates="verse")
    
    characters = relationship("Character", secondary=verse_character, back_populates="verses")
    events = relationship("Event", secondary=verse_event, back_populates="verses")
    locations = relationship("Location", secondary=verse_location, back_populates="verses")
    concepts = relationship("Concept", secondary=verse_concept, back_populates="verses")
    language_data = relationship("LanguageData", secondary=verse_language, back_populates="verses")

# ==========================================
# 2. 신학 지식 엔티티
# ==========================================
class Character(Base):
    __tablename__ = "characters"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    original_name = Column(String(100))
    era = Column(String(100))
    genealogy_info = Column(Text)
    father_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    
    father = relationship("Character", remote_side=[id], backref="children")
    verses = relationship("Verse", secondary=verse_character, back_populates="characters")
    events = relationship("Event", secondary=event_character, back_populates="characters")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    period = Column(String(100))
    historical_background = Column(Text)
    
    verses = relationship("Verse", secondary=verse_event, back_populates="events")
    characters = relationship("Character", secondary=event_character, back_populates="events")
    locations = relationship("Location", secondary=event_location, back_populates="events")

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    ancient_name = Column(String(100))
    coordinates = Column(String(100))
    
    verses = relationship("Verse", secondary=verse_location, back_populates="locations")
    events = relationship("Event", secondary=event_location, back_populates="locations")

class Concept(Base):
    __tablename__ = "concepts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False) # 언약, 창조, 구원
    definition = Column(Text)
    
    verses = relationship("Verse", secondary=verse_concept, back_populates="concepts")
    doctrines = relationship("Doctrine", secondary=concept_doctrine, back_populates="concepts")

class Doctrine(Base):
    __tablename__ = "doctrines"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False) # 삼위일체, 칭의
    description = Column(Text)
    
    concepts = relationship("Concept", secondary=concept_doctrine, back_populates="doctrines")

class LanguageData(Base):
    __tablename__ = "language_data"
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False) # 원어 단어
    language_type = Column(String(20)) # 히브리어 / 헬라어
    transliteration = Column(String(100)) # 음역
    morphology = Column(Text) # 형태소 분석
    strong_number = Column(String(16), index=True, nullable=True)  # H#### / G####
    
    verses = relationship("Verse", secondary=verse_language, back_populates="language_data")


# ==========================================
# 1b. Strong's 통합 사전 (중복 방지 핵심)
# ==========================================
class SourceRegistry(Base):
    """학술/저작권 출처 레지스트리. sources 테이블과 병행, 수집 파이프라인 전용."""
    __tablename__ = "source_registry"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    author = Column(String(100))
    publisher = Column(String(100))
    source_url = Column(String(500))
    source_type = Column(String(50))
    copyright_owner = Column(String(100))
    copyright_status = Column(String(50), nullable=False)  # Public Domain | CC BY 4.0 | Mixed
    license_type = Column(String(50), nullable=False)      # PD / CC-BY-4.0 — CC0 자동 스탬프 금지
    license_url = Column(String(500))
    attribution_text = Column(Text, nullable=False)
    commercial_use = Column(Boolean, default=False)
    allow_ai_quote = Column(Boolean, default=True)
    publication_year = Column(Integer)
    verification_status = Column(String(20), default="미검증")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class StrongEntry(Base):
    __tablename__ = "strong_entries"
    id = Column(Integer, primary_key=True, index=True)
    strong_number = Column(String(16), unique=True, nullable=False, index=True)
    language_type = Column(String(20), nullable=False)
    lemma = Column(Text)
    transliteration = Column(String(200))
    pronunciation = Column(String(200))
    gloss = Column(Text)
    definition_short = Column(Text)
    definition_full = Column(Text)
    morphology_hint = Column(String(100))
    root_word = Column(Text)
    source_id = Column(Integer, ForeignKey("source_registry.id"), nullable=False)
    content_hash = Column(String(64))
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    source = relationship("SourceRegistry")


class LexiconExpansion(Base):
    __tablename__ = "lexicon_expansions"
    __table_args__ = (
        UniqueConstraint("strong_number", "lexicon_name", "source_id", name="uq_lexicon_expansion"),
    )
    id = Column(Integer, primary_key=True, index=True)
    strong_number = Column(String(16), nullable=False, index=True)
    lexicon_name = Column(String(80), nullable=False)
    entry_text = Column(Text, nullable=False)
    source_id = Column(Integer, ForeignKey("source_registry.id"), nullable=False)
    content_hash = Column(String(64))

    source = relationship("SourceRegistry")


class MorphologyLink(Base):
    __tablename__ = "morphology_links"
    __table_args__ = (
        UniqueConstraint("strong_number", "related_strong", "relation_type", "source_id", name="uq_morph_link"),
    )
    id = Column(Integer, primary_key=True, index=True)
    strong_number = Column(String(16), nullable=False, index=True)
    related_strong = Column(String(16), nullable=False)
    relation_type = Column(String(50), nullable=False)
    morph_code = Column(String(100))
    source_id = Column(Integer, ForeignKey("source_registry.id"), nullable=False)

    source = relationship("SourceRegistry")


class SefariaPassage(Base):
    __tablename__ = "sefaria_passages"
    id = Column(Integer, primary_key=True, index=True)
    ref_key = Column(String(200), unique=True, nullable=False, index=True)
    title = Column(String(200))
    he_text = Column(Text)
    en_text = Column(Text)
    tradition_note = Column(Text)
    source_id = Column(Integer, ForeignKey("source_registry.id"), nullable=False)
    content_hash = Column(String(64))
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

    source = relationship("SourceRegistry")

# ==========================================
# 3. 출처, 저작권 통제 및 해석 (핵심)
# ==========================================
class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    
    # [Content]
    title = Column(String(200), nullable=False)
    author = Column(String(100))
    publisher = Column(String(100))
    source_url = Column(String(500))
    source_type = Column(String(50)) # Book, Article, Website, Database 등
    original_location = Column(String(500)) # 로컬/S3 파일 경로
    tags = Column(String(500)) # 검색용 한국어/영문 키워드 (주석, commentary, calvin, ...)
    description = Column(Text) # 자료 요약/메모

    # [Copyright]
    copyright_owner = Column(String(100))
    copyright_status = Column(String(50)) # Public Domain, CC0, Copyrighted 등
    publication_year = Column(Integer)

    # 학술 신뢰 등급
    academic_level = Column(String(20)) # A, B, C
    verification_status = Column(String(20)) # 검증됨, 미검증
    
    interpretations = relationship("Interpretation", back_populates="source")
    license = relationship("License", back_populates="source", uselist=False)

class License(Base):
    __tablename__ = "licenses"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey('sources.id'), unique=True, nullable=False)
    
    # [License]
    license_type = Column(String(50)) # CC BY, CC BY-NC, Commercial 등
    license_url = Column(String(500))
    commercial_use = Column(Boolean, default=False)
    modification_allowed = Column(Boolean, default=False)
    redistribution_allowed = Column(Boolean, default=False)
    
    # [AI Permission]
    allow_ai_read = Column(Boolean, default=True)
    allow_ai_summary = Column(Boolean, default=True)
    allow_ai_embedding = Column(Boolean, default=True)
    allow_ai_quote = Column(Boolean, default=True)
    
    # [User Permission]
    allow_free_user = Column(Boolean, default=True)
    allow_paid_user = Column(Boolean, default=True)
    allow_institution = Column(Boolean, default=True)
    
    # [Original Content]
    can_view_original = Column(Boolean, default=True)
    can_download = Column(Boolean, default=False)
    
    # 기존 필드 호환성 유지
    visibility_level = Column(String(20), default="Public")
    contract_expire_date = Column(DateTime, nullable=True)
    
    source = relationship("Source", back_populates="license")

class Interpretation(Base):
    __tablename__ = "interpretations"
    id = Column(Integer, primary_key=True, index=True)
    viewpoint = Column(String(50), nullable=False)
    claim = Column(Text, nullable=False)
    evidence = Column(Text)
    scholar_name = Column(String(100))
    
    verse_id = Column(Integer, ForeignKey("verses.id"), nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    
    verse = relationship("Verse", back_populates="interpretations")
    source = relationship("Source", back_populates="interpretations")


class Commentary(Base):
    """공개 주석(PD/CC) — 구절/장 단위 주석 텍스트. 출처는 SourceRegistry."""
    __tablename__ = "commentaries"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("bible_books.id"), nullable=False)
    chapter_num = Column(Integer, nullable=False)
    verse_start = Column(Integer, nullable=True)   # null이면 장 전체 주석
    verse_end = Column(Integer, nullable=True)
    passage_ref = Column(String(60), nullable=False)  # 예: "John.3.16"
    commentary_text = Column(Text, nullable=False)
    content_hash = Column(String(64))

    __table_args__ = (
        UniqueConstraint("source_id", "passage_ref", name="uq_commentary_passage"),
    )
    source = relationship("Source")
    book = relationship("BibleBook")


class CrossReference(Base):
    """공개 연관 구절(TSK / OpenBible CC BY)."""
    __tablename__ = "cross_references"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    from_book_id = Column(Integer, ForeignKey("bible_books.id"), nullable=False)
    from_chapter = Column(Integer, nullable=False)
    from_verse = Column(Integer, nullable=False)
    to_book_id = Column(Integer, ForeignKey("bible_books.id"), nullable=False)
    to_chapter = Column(Integer, nullable=False)
    to_verse_start = Column(Integer, nullable=False)
    to_verse_end = Column(Integer, nullable=True)
    votes = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint(
            "from_book_id", "from_chapter", "from_verse",
            "to_book_id", "to_chapter", "to_verse_start", "to_verse_end",
            "source_id",
            name="uq_crossref",
        ),
    )
    source = relationship("Source")
    from_book = relationship("BibleBook", foreign_keys=[from_book_id])
    to_book = relationship("BibleBook", foreign_keys=[to_book_id])

class ResponseCache(Base):
    __tablename__ = "response_caches"
    id = Column(Integer, primary_key=True, index=True)
    query_hash = Column(String(64), unique=True, index=True, nullable=False)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source_citations_json = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # [비용 관리 필드]
    use_count = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    difficulty_level = Column(String(20), default="Medium") # Easy, Medium, Hard
    
    # [품질/신뢰도 관리 필드]
    citation_count = Column(Integer, default=0)
    source_reliability = Column(String(20), default="B") # A, B, C 등급
    is_controversial = Column(Boolean, default=False)
    confidence_score = Column(Float, default=1.0) # 0.0 ~ 1.0

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=True)
    full_name = Column(String(100), nullable=True)  # 성함
    organization = Column(String(200), nullable=True)  # 소속
    activity_region = Column(String(200), nullable=True)  # 활동지역
    occupation = Column(String(100), nullable=True)  # 직업
    join_purpose = Column(Text, nullable=True)  # 가입목적
    phone = Column(String(30), nullable=True)  # 휴대폰
    withdrawn = Column(Boolean, default=False, index=True)
    withdrawn_at = Column(DateTime, nullable=True)
    tier = Column(String(20), default="Free")  # Free, Paid, Institution (레거시 호환)
    # Free_Trial(7일) -> Limited_24h -> Blocked | Paid / Institution
    membership_status = Column(String(30), default="Free_Trial", index=True)
    trial_started_at = Column(DateTime, default=datetime.datetime.utcnow)
    limited_started_at = Column(DateTime, nullable=True)
    subscribed_until = Column(DateTime, nullable=True)
    daily_view_limit = Column(Integer, default=20)  # Limited_24h 일일 조회 상한
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class UserUsage(Base):
    __tablename__ = "user_usages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(String(10), nullable=False) # "YYYY-MM-DD"
    request_count = Column(Integer, default=0)

class DocumentOcrCache(Base):
    __tablename__ = "document_ocr_caches"
    id = Column(Integer, primary_key=True, index=True)
    file_hash = Column(String(64), unique=True, index=True, nullable=False)
    filename = Column(String(255))
    extracted_text = Column(Text, nullable=False)
    structured_metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Notice(Base):
    """공지사항 (어드민 작성)."""
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    body = Column(Text, nullable=False)
    pinned = Column(Boolean, default=False)
    published = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class FeedbackReport(Base):
    """제보: 버그 / 데이터오류 / 기능제안."""
    __tablename__ = "feedback_reports"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(40), nullable=False, index=True)  # bug | data | feature
    title = Column(String(300), nullable=False)
    body = Column(Text, nullable=False)
    contact = Column(String(200), nullable=True)
    page_url = Column(String(500), nullable=True)
    search_query = Column(String(300), nullable=True)
    status = Column(String(30), default="open", index=True)  # open | in_progress | done
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

