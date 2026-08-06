from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import os
import base64
import hashlib
import json
import re
import requests

import models
from database import engine, get_db, SessionLocal
from rag_engine import RagEngine, load_env
import membership
import board_api

# .env (OPENROUTER_API_KEY 등) — uvicorn 기동 시 확실히 로드
load_env()


# Create DB Tables
models.Base.metadata.create_all(bind=engine)

def _migrate_sqlite_columns():
    """기존 SQLite users 테이블에 멤버십 컬럼 추가 (없으면)."""
    alters = [
        "ALTER TABLE users ADD COLUMN membership_status VARCHAR(30) DEFAULT 'Free_Trial'",
        "ALTER TABLE users ADD COLUMN trial_started_at DATETIME",
        "ALTER TABLE users ADD COLUMN limited_started_at DATETIME",
        "ALTER TABLE users ADD COLUMN subscribed_until DATETIME",
        "ALTER TABLE users ADD COLUMN daily_view_limit INTEGER DEFAULT 20",
        "ALTER TABLE language_data ADD COLUMN strong_number VARCHAR(16)",
        "ALTER TABLE users ADD COLUMN password_hash VARCHAR(200)",
        "ALTER TABLE users ADD COLUMN full_name VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN organization VARCHAR(200)",
        "ALTER TABLE users ADD COLUMN activity_region VARCHAR(200)",
        "ALTER TABLE users ADD COLUMN occupation VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN join_purpose TEXT",
        "ALTER TABLE users ADD COLUMN phone VARCHAR(30)",
        "ALTER TABLE users ADD COLUMN withdrawn BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN withdrawn_at DATETIME",
        "ALTER TABLE users ADD COLUMN created_at DATETIME",
        "ALTER TABLE users ADD COLUMN updated_at DATETIME",
    ]
    with engine.begin() as conn:
        for sql in alters:
            try:
                conn.execute(text(sql))
            except Exception:
                pass

_migrate_sqlite_columns()

app = FastAPI(
    title="ARK AI - Theological Knowledge Graph API",
    description="Backend API for querying the relational theology database.",
    version="1.0.0"
)

rag_engine = RagEngine()
app.include_router(board_api.router)

# CORS Setting for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기본 공지 시드
try:
    _db = SessionLocal()
    board_api.seed_default_notice(_db)
    _db.close()
except Exception:
    pass

# Render 등: DB 비어 있으면 개역한글 PD 자동 적재 (백그라운드)
try:
    import bootstrap_cloud

    if bootstrap_cloud.verse_count() < 1000:
        bootstrap_cloud.start_bootstrap_background(force=False)
except Exception as _boot_err:
    print(f"[bootstrap] schedule failed: {_boot_err}", flush=True)


@app.get("/")
def read_root():
    return {"message": "Welcome to ARK AI Knowledge Graph API"}


@app.get("/api/bootstrap/status")
def bootstrap_status():
    try:
        import bootstrap_cloud

        return bootstrap_cloud.status()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/admin/bootstrap")
def admin_bootstrap(
    force: bool = False,
    _: bool = Depends(board_api.require_admin),
):
    """관리자: 클라우드 DB 본문 적재 (이미 충분하면 force=1로 재실행)."""
    import bootstrap_cloud

    # 동기 실행 — Render Shell/수동 호출용. 웹 UI는 status로 폴링.
    return bootstrap_cloud.run_bootstrap(force=force)
import datetime
from sqlalchemy import func

@app.get("/api/assistant/chat")
def chat_assistant(query: str, username: str = "free_user", lang: str = "KO", db: Session = Depends(get_db)):
    """
    RAG & Knowledge Graph 기반 AI 연구 비서.
    멤버십: Free_Trial(7일) → Limited_24h → Blocked (402 + pricing).
    """
    user = membership.get_or_create_user(db, username)
    decision = membership.require_access(db, user)

    res = rag_engine.generate_rag_response(db, query, lang=lang)
    res["user_usage"] = {
        "username": username,
        "tier": user.tier,
        "membership": membership.decision_payload(decision),
    }
    # 인용에 source_registry attribution 보강 가능 시 프론트 스플릿뷰용 embed_path 제공
    citations = res.get("source_citations") or []
    for c in citations:
        if isinstance(c, dict) and not c.get("embed_path"):
            title = c.get("title") or c.get("source") or ""
            c["embed_path"] = f"/study?panel=source&q={title}"
            c["open_mode"] = "split"  # 외부 새창 대신 내부 분할
    res["source_citations"] = citations
    return res


@app.get("/api/membership/status")
def membership_status(username: str = "free_user", db: Session = Depends(get_db)):
    user = membership.get_or_create_user(db, username)
    decision = membership.evaluate_access(db, user, increment=False)
    db.commit()
    return {
        "username": username,
        "tier": user.tier,
        **membership.decision_payload(decision),
    }


@app.get("/api/lexicon/strong/{strong_number}")
def get_strong_entry(strong_number: str, username: str = "free_user", db: Session = Depends(get_db)):
    """Strong's 번호 조회 + STEP/BDB 확장 + 출처 attribution (내부 임베드용)."""
    user = membership.get_or_create_user(db, username)
    membership.require_access(db, user)

    sn = strong_number.strip().upper()
    if sn and sn[0] in "GH" and sn[1:].isdigit():
        sn = f"{sn[0]}{int(sn[1:]):04d}"

    entry = db.query(models.StrongEntry).filter_by(strong_number=sn).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Strong number not found: {sn}")

    expansions = (
        db.query(models.LexiconExpansion)
        .filter_by(strong_number=sn)
        .all()
    )
    links = db.query(models.MorphologyLink).filter_by(strong_number=sn).limit(50).all()
    src = entry.source

    gloss_ko = None
    ko_attr = None
    # ARK_KO_GLOSS는 DB에 보탠 요약이므로 사실 레이어로 노출하지 않음.
    # 한국어 해석은 어시스턴트가 등록된 영문 Strong/STEP만 근거로 설명.
    public_expansions = [e for e in expansions if e.lexicon_name != "ARK_KO_GLOSS"]

    return {
        "strong_number": entry.strong_number,
        "language_type": entry.language_type,
        "lemma": entry.lemma,
        "transliteration": entry.transliteration,
        "pronunciation": entry.pronunciation,
        "gloss": entry.gloss,
        "gloss_en": entry.gloss or entry.definition_short,
        "gloss_ko": None,
        "gloss_ko_available": False,
        "gloss_ko_note": (
            "공개 Strong's/STEP는 영문 정의입니다. 한국어 정식 원어 사전은 저작권상 적재하지 않았습니다. "
            "한국어 설명은 어시스턴트가 등록된 영문 기록만 바탕으로 안내합니다."
        ),
        "definition_short": entry.definition_short,
        "definition_full": entry.definition_full,
        "root_word": entry.root_word,
        "source": {
            "id": src.id if src else None,
            "code": src.code if src else None,
            "title": src.title if src else None,
            "copyright_status": src.copyright_status if src else None,
            "license_type": src.license_type if src else None,
            "attribution_text": src.attribution_text if src else None,
            "source_url": src.source_url if src else None,
            "embed_allowed": True,
        },
        "expansions": [
            {
                "lexicon_name": e.lexicon_name,
                "entry_text": e.entry_text,
                "source_id": e.source_id,
                "attribution": e.source.attribution_text if e.source else None,
            }
            for e in public_expansions
        ],
        "morphology_links": [
            {
                "related_strong": l.related_strong,
                "relation_type": l.relation_type,
                "morph_code": l.morph_code,
            }
            for l in links
        ],
        "membership": membership.decision_payload(
            membership.evaluate_access(db, user, increment=False)
        ),
    }


@app.get("/api/lexicon/sefaria/{ref_key:path}")
def get_sefaria_passage(ref_key: str, username: str = "free_user", db: Session = Depends(get_db)):
    user = membership.get_or_create_user(db, username)
    membership.require_access(db, user)
    row = db.query(models.SefariaPassage).filter_by(ref_key=ref_key).first()
    if not row:
        raise HTTPException(status_code=404, detail="Passage not found")
    return {
        "ref_key": row.ref_key,
        "title": row.title,
        "he_text": row.he_text,
        "en_text": row.en_text,
        "tradition_note": row.tradition_note,
        "source": {
            "attribution_text": row.source.attribution_text if row.source else None,
            "license_type": row.source.license_type if row.source else None,
            "embed_allowed": True,
        },
    }

@app.get("/api/bible/{book_name}/{chapter}/{verse}")
def get_verse_analysis(book_name: str, chapter: int, verse: int, db: Session = Depends(get_db)):
    """
    특정 성경 구절과 관련된 모든 지식 그래프(인물, 사건, 장소, 다중 해석)를 가져오는 메인 엔드포인트
    """
    # 1. 구절 기본 정보 조회
    book = db.query(models.BibleBook).filter(models.BibleBook.name == book_name).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    verse_obj = db.query(models.Verse).filter(
        models.Verse.book_id == book.id,
        models.Verse.chapter_num == chapter,
        models.Verse.verse_num == verse
    ).first()
    
    if not verse_obj:
        raise HTTPException(status_code=404, detail="Verse not found")

    # 같은 장 전후 구절 + 그래프 연결 구절
    related = []
    same_chapter = (
        db.query(models.Verse)
        .filter(
            models.Verse.book_id == book.id,
            models.Verse.chapter_num == chapter,
            models.Verse.verse_num != verse,
        )
        .order_by(models.Verse.verse_num)
        .all()
    )
    for nv in same_chapter:
        if abs(nv.verse_num - verse) <= 3:
            related.append(
                {
                    "reference": f"{book.name} {nv.chapter_num}:{nv.verse_num}",
                    "snippet": (nv.text_ko if nv.text_ko and not nv.text_ko.startswith("[공개") else (nv.text_en or ""))[:120],
                    "reason": "같은 장",
                }
            )

    seen_refs = {r["reference"] for r in related}
    for char in verse_obj.characters:
        for v in char.verses[:6]:
            ref = f"{v.book.name} {v.chapter_num}:{v.verse_num}"
            if ref == f"{book.name} {chapter}:{verse}" or ref in seen_refs:
                continue
            related.append(
                {
                    "reference": ref,
                    "snippet": (v.text_ko or v.text_en or "")[:120],
                    "reason": f"인물 연결 · {char.name}",
                }
            )
            seen_refs.add(ref)
    for ev in verse_obj.events:
        for v in ev.verses[:6]:
            ref = f"{v.book.name} {v.chapter_num}:{v.verse_num}"
            if ref == f"{book.name} {chapter}:{verse}" or ref in seen_refs:
                continue
            related.append(
                {
                    "reference": ref,
                    "snippet": (v.text_ko or v.text_en or "")[:120],
                    "reason": f"사건 연결 · {ev.name}",
                }
            )
            seen_refs.add(ref)

    materials = []
    for i in verse_obj.interpretations:
        if i.source:
            lic = i.source.license
            materials.append(
                {
                    "kind": "commentary",
                    "title": i.source.title,
                    "author": i.source.author,
                    "viewpoint": i.viewpoint,
                    "claim": i.claim,
                    "license": i.source.copyright_status
                    or (lic.license_type if lic else None),
                    "source_url": i.source.source_url,
                    "attribution": (i.source.description or "")[:400],
                }
            )

    ko = (verse_obj.text_ko or "").strip()
    ko_is_placeholder = not ko or ko.startswith("[공개 한국어")
    # 2. 관련 데이터 취합 (SQLAlchemy ORM Relationships 활용)
    return {
        "reference": f"{book.name} {chapter}:{verse}",
        "original_text": verse_obj.text_original,
        "translated_text": verse_obj.text_ko,
        "text_en": verse_obj.text_en,
        "text_ko": verse_obj.text_ko,
        "translation_en": "World English Bible (WEB) · Public Domain" if verse_obj.text_en else None,
        "translation_ko": (
            None if ko_is_placeholder else "개역한글(1961) · Public Domain (등록분)"
        ),
        "translation_note": (
            "한국어: 개역한글(1961) PD. 영문: WEB(PD). "
            "일부 절은 절 체계 차이로 한쪽만 있을 수 있습니다. "
            "개역개정 등 저작권 유효 역본은 미수록."
            if (verse_obj.text_en or verse_obj.text_ko)
            else None
        ),
        "related_verses": related[:16],
        "related_characters": [{"name": c.name, "era": c.era} for c in verse_obj.characters],
        "related_events": [{"name": e.name, "historical_background": e.historical_background} for e in verse_obj.events],
        "related_concepts": [{"name": cp.name, "definition": cp.definition} for cp in verse_obj.concepts],
        "language_data": [{"word": l.word, "transliteration": l.transliteration, "morphology": l.morphology} for l in verse_obj.language_data],
        "materials": materials,
        "interpretations": [
            {
                "viewpoint": i.viewpoint,
                "scholar": i.scholar_name,
                "claim": i.claim,
                "evidence": i.evidence,
                "source": {
                    "title": i.source.title,
                    "author": i.source.author,
                    "academic_level": i.source.academic_level,
                    "verification_status": i.source.verification_status,
                    "license": {
                        "visibility": i.source.license.visibility_level if i.source.license else "Public",
                        "allow_ai_quote": i.source.license.allow_ai_quote if i.source.license else True,
                        "can_download": i.source.license.can_download if i.source.license else False
                    } if i.source.license else None
                } if i.source else None
            } for i in verse_obj.interpretations
        ]
    }

from search_api import unified_search as _unified_search_impl

@app.get("/api/search")
def unified_search(q: str, username: str = "free_user", lang: str = "KO", db: Session = Depends(get_db)):
    return _unified_search_impl(q=q, username=username, db=db, lang=lang)


# 홈 트렌딩 피드 캐시 (연관구절 34만건 GROUP BY가 매 요청 ~1초 → 60초 캐시)
_trending_cache: dict = {"ts": 0.0, "by_lang": {}}


@app.get("/api/feed/trending")
def trending_feed(lang: str = "KO", db: Session = Depends(get_db)):
    """메인 페이지용 실시간 흐르는 콘텐츠 피드: 인기 구절, 인물, 연관 구절 많은 구절, 최근 자료."""
    import time as _time
    from book_i18n import book_display, char_display, normalize_lang
    lang = normalize_lang(lang)
    en = lang == "EN"
    now = _time.time()
    cached = _trending_cache["by_lang"].get(lang)
    if cached and (now - _trending_cache["ts"]) < 60:
        return {"feed": cached}

    feed = []

    def _badge_source(source_type: str | None) -> str:
        st = (source_type or "").strip().lower()
        if en:
            if "journal" in st or st == "journalarticle":
                return "Paper"
            if "comment" in st:
                return "Commentary"
            if "lexicon" in st or "dictionary" in st:
                return "Lexicon"
            return source_type or "Source"
        # KO
        if "journal" in st or st == "journalarticle":
            return "논문"
        if "comment" in st:
            return "주석"
        if "lexicon" in st or "dictionary" in st:
            return "원어"
        if source_type in ("주석", "원어", "자료", "교부", "논문"):
            return source_type
        return "자료"

  // 1) 인기 구절 — DB에 실제 본문 있는 것만 (클라우드 적재 중 빈 링크 방지)
    popular_refs = [
        ("요한복음", 3, 16),
        ("창세기", 1, 1),
        ("시편", 23, 1),
        ("로마서", 8, 28),
        ("마태복음", 5, 3),
        ("빌립보서", 4, 13),
        ("출애굽기", 3, 14),
        ("이사야", 53, 5),
    ]
    for book_name, ch, vs in popular_refs:
        book = db.query(models.BibleBook).filter_by(name=book_name).first()
        if not book:
            continue
        vrow = (
            db.query(models.Verse)
            .filter_by(book_id=book.id, chapter_num=ch, verse_num=vs)
            .first()
        )
        if not vrow:
            continue
        ko = (vrow.text_ko or "").strip()
        en_txt = (vrow.text_en or "").strip()
        if ko.startswith("[공개"):
            ko = ""
        snippet = (ko or en_txt)[:60]
        if not snippet:
            continue
        b = book_display(book_name, lang)
        feed.append({
            "type": "verse",
            "title": f"{b} {ch}:{vs}",
            "subtitle": snippet,
            "link": f"/search?q={b} {ch}:{vs}",
            "badge": "Hot" if en else "인기",
        })
        if len([f for f in feed if f["type"] == "verse"]) >= 6:
            break

    # 2) 인물
    top_chars = db.query(models.Character).order_by(models.Character.id).limit(6).all()
    for char in top_chars:
        title = char_display(char.name, lang)
        feed.append({
            "type": "character",
            "title": title,
            "subtitle": char.original_name or "",
            "link": f"/search?q={title}",
            "badge": "Character" if en else "인물",
        })

    # 3) 최근 수집 공개 자료 (+ 논문 우선 섞기)
    recent_papers = (
        db.query(models.Source)
        .filter(models.Source.source_type == "JournalArticle")
        .order_by(models.Source.id.desc())
        .limit(8)
        .all()
    )
    recent_sources = (
        db.query(models.Source)
        .filter(
            models.Source.copyright_status.notin_(["Copyrighted", "Unsafe", "None", "Unknown", ""]),
            models.Source.source_type != "JournalArticle",
        )
        .order_by(models.Source.id.desc())
        .limit(4)
        .all()
    )
    for src in list(recent_papers) + list(recent_sources):
        feed.append({
            "type": "material",
            "title": src.title,
            "subtitle": src.author or src.source_type or "",
            "link": f"/search?q={src.title}",
            "badge": _badge_source(src.source_type),
        })

    _trending_cache["ts"] = now
    _trending_cache["by_lang"][lang] = feed
    return {"feed": feed}


@app.get("/api/character/{name}")
def get_character_graph(name: str, db: Session = Depends(get_db)):
    """
    특정 인물을 중심으로 연결된 모든 사건, 장소, 성경 구절을 반환
    """
    char = db.query(models.Character).filter(models.Character.name == name).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
        
    return {
        "name": char.name,
        "original_name": char.original_name,
        "era": char.era,
        "genealogy_info": char.genealogy_info,
        "father": {"name": char.father.name, "era": char.father.era} if char.father else None,
        "children": [{"name": c.name, "era": c.era} for c in char.children],
        "involved_events": [{"name": e.name, "period": e.period} for e in char.events],
        "mentioned_in_verses": [f"{v.book.name} {v.chapter_num}:{v.verse_num}" for v in char.verses]
    }

@app.get("/api/genealogy/{name}")
def get_character_genealogy(name: str, db: Session = Depends(get_db)):
    """
    특정 인물의 상하행 족보(계보) 추적 API
    """
    char = db.query(models.Character).filter(models.Character.name == name).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
        
    # 상위 조상 추적 (Father -> Grandfather ...)
    ancestors = []
    curr = char.father
    while curr:
        ancestors.append({
            "name": curr.name,
            "era": curr.era,
            "original_name": curr.original_name
        })
        curr = curr.father
    
    # 아담부터 내려오는 순서로 반전
    ancestors.reverse()
    
    # 하위 자손 추적 (직계 자식만)
    descendants = [{
        "name": c.name,
        "era": c.era,
        "original_name": c.original_name
    } for c in char.children]
    
    return {
        "target": {
            "name": char.name,
            "era": char.era,
            "original_name": char.original_name,
            "genealogy_info": char.genealogy_info
        },
        "ancestors": ancestors,
        "descendants": descendants
    }

@app.post("/api/admin/import-document")
async def import_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    academic_level: Optional[str] = Form("C"),
    db: Session = Depends(get_db)
):
    # 1. 파일 바이트 읽기 및 해시 생성
    file_bytes = await file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    
    # 2. 이중 캐시 확인 (중복 파일 업로드 방지)
    cache_entry = db.query(models.DocumentOcrCache).filter(models.DocumentOcrCache.file_hash == file_hash).first()
    
    if cache_entry:
        metadata = json.loads(cache_entry.structured_metadata_json)
        existing_source = db.query(models.Source).filter(models.Source.original_location == f"hash://{file_hash}").first()
        if existing_source:
            return {
                "message": "이미 성공적으로 업로드 및 분석이 완료된 중복 문서입니다. (API 요금 부과 없이 캐시 반환)",
                "cached": True,
                "file_hash": file_hash,
                "transcribed_text": cache_entry.extracted_text,
                "metadata": metadata
            }
        extracted_text = cache_entry.extracted_text
    else:
        # 캐시가 없는 경우: Gemini Flash Lite API 호출 수행
        api_key = os.environ.get("OPENROUTER_API_KEY")
        ocr_model = os.environ.get("OCR_MODEL", "google/gemini-2.5-flash-lite")
        
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenRouter API key not configured in .env")
            
        is_image = file.content_type and file.content_type.startswith("image/")
        
        try:
            if is_image:
                base64_data = base64.b64encode(file_bytes).decode("utf-8")
                mime_type = file.content_type or "image/jpeg"
                image_url = f"data:{mime_type};base64,{base64_data}"
                
                payload = {
                    "model": ocr_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "주어진 신학 고서적 스캔 이미지의 텍스트를 정확하게 판독(OCR)하고 분석하십시오.\n"
                                        "반드시 다음 JSON 스키마 형식으로만 응답을 반환하십시오. 다른 설명글이나 코드 블록 기호(```json) 없이 순수 JSON만 반환해야 합니다:\n"
                                        "{\n"
                                        "  \"transcribed_text\": \"판독된 전체 본문 텍스트 (히브리어/헬라어 특수문자 포함)\",\n"
                                        "  \"metadata\": {\n"
                                        "    \"book_name\": \"관련 성경 책 명 (예: 창세기, 로마서, 시편 등)\",\n"
                                        "    \"chapter_num\": 1,\n"
                                        "    \"verse_num\": 1,\n"
                                        "    \"viewpoint\": \"신학적 관점 (예: 개신교, 가톨릭, 정교회, 유대교 등)\",\n"
                                        "    \"scholar_name\": \"주장한 학자 혹은 저자 이름\",\n"
                                        "    \"claim\": \"핵심 신학적 주장 요약\",\n"
                                        "    \"evidence\": \"주장의 성경적/역사적 근거 요약\"\n"
                                        "  }\n"
                                        "}"
                                    )
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_url
                                    }
                                }
                            ]
                        }
                    ]
                }
            else:
                text_content = file_bytes.decode("utf-8", errors="ignore")
                payload = {
                    "model": ocr_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "주어진 다음 신학 텍스트 문서를 분석하십시오.\n"
                                "반드시 다음 JSON 스키마 형식으로만 응답을 반환하십시오. 다른 설명글 없이 순수 JSON만 반환해야 합니다:\n"
                                "{\n"
                                "  \"transcribed_text\": \"정제된 본문 텍스트\",\n"
                                "  \"metadata\": {\n"
                                "    \"book_name\": \"관련 성경 책 명 (예: 창세기, 로마서, 시편 등)\",\n"
                                "    \"chapter_num\": 1,\n"
                                "    \"verse_num\": 1,\n"
                                "    \"viewpoint\": \"신학적 관점 (예: 개신교, 가톨릭, 정교회, 유대교 등)\",\n"
                                "    \"scholar_name\": \"주장한 학자 혹은 저자 이름\",\n"
                                "    \"claim\": \"핵심 신학적 주장 요약\",\n"
                                "    \"evidence\": \"주장의 성경적/역사적 근거 요약\"\n"
                                "  }\n"
                                "}\n\n"
                                f"[문서 내용]\n{text_content}"
                            )
                        }
                    ]
                }
                
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "ARK AI"
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=45
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"OpenRouter OCR API error: {response.text}")
                
            res_json = response.json()
            raw_content = res_json["choices"][0]["message"]["content"].strip()
            
            if raw_content.startswith("```"):
                lines = raw_content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_content = "\n".join(lines).strip()
                
            parsed_data = json.loads(raw_content)
            extracted_text = parsed_data["transcribed_text"]
            metadata = parsed_data["metadata"]
            
            new_ocr_cache = models.DocumentOcrCache(
                file_hash=file_hash,
                filename=file.filename,
                extracted_text=extracted_text,
                structured_metadata_json=json.dumps(metadata, ensure_ascii=False)
            )
            db.add(new_ocr_cache)
            db.commit()
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OCR 파싱 실패: {str(e)}")

    try:
        book_name = metadata.get("book_name", "창세기")
        book = db.query(models.BibleBook).filter(models.BibleBook.name == book_name).first()
        if not book:
            book = models.BibleBook(name=book_name, testament="구약")
            db.add(book)
            db.commit()
            db.refresh(book)
            
        chap_num = metadata.get("chapter_num", 1)
        verse_num = metadata.get("verse_num", 1)
        verse = db.query(models.Verse).filter(
            models.Verse.book_id == book.id,
            models.Verse.chapter_num == chap_num,
            models.Verse.verse_num == verse_num
        ).first()
        
        if not verse:
            verse = models.Verse(
                book_id=book.id,
                chapter_num=chap_num,
                verse_num=verse_num,
                text_ko=extracted_text[:150] + "...",
                text_original=""
            )
            db.add(verse)
            db.commit()
            db.refresh(verse)
            
        doc_title = title or file.filename
        doc_author = author or metadata.get("scholar_name", "미상")
        
        new_source = models.Source(
            title=doc_title,
            author=doc_author,
            publisher="ARK AI Content Import",
            source_url="http://localhost",
            source_type="Book",
            original_location=f"hash://{file_hash}",
            copyright_owner=doc_author,
            copyright_status="Public Domain",
            publication_year=2026,
            academic_level=academic_level,
            verification_status="Pending Verification"
        )
        db.add(new_source)
        db.commit()
        db.refresh(new_source)
        
        new_license = models.License(
            source_id=new_source.id,
            license_type="CC BY",
            license_url="",
            commercial_use=False,
            modification_allowed=False,
            redistribution_allowed=False,
            allow_ai_read=True,
            allow_ai_summary=True,
            allow_ai_embedding=True,
            allow_ai_quote=True,
            allow_free_user=True,
            allow_paid_user=True,
            allow_institution=True,
            can_view_original=True,
            can_download=False
        )
        db.add(new_license)
        
        new_interpretation = models.Interpretation(
            viewpoint=metadata.get("viewpoint", "일반"),
            claim=metadata.get("claim", "주장 정보가 추출되지 않았습니다."),
            evidence=metadata.get("evidence", "근거 정보가 추출되지 않았습니다."),
            scholar_name=doc_author,
            verse_id=verse.id,
            source_id=new_source.id
        )
        db.add(new_interpretation)
        db.commit()
        
        return {
            "message": "신학 고전 문서가 정상적으로 OCR 처리되고 지식 데이터베이스에 연동되었습니다.",
            "cached": False,
            "file_hash": file_hash,
            "transcribed_text": extracted_text,
            "metadata": metadata,
            "db_reference": f"{book_name} {chap_num}장 {verse_num}절"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB 적재 실패: {str(e)}")


