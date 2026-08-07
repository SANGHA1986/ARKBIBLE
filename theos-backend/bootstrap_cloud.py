"""
클라우드(Render) 부트스트랩 — 저장소에 동봉한 데이터로 빠르게 복구.

무료 Render는 재시작 시 DB가 비워지므로, Git에 넣은 스냅샷으로
본문·주석·논문·지식망을 수 분 안에 다시 채운다.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time

from database import SessionLocal, engine
import models
from collect_open_bible import BOOKS, ensure_book
from collect_ko_pd_bible import (
    ensure_registry,
    iter_verses,
    load_manifest,
    upsert_ko,
    validate_manifest,
    DATA_DIR,
)

BOOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_bootstrap")

_LOCK = threading.Lock()
_STATE = {
    "running": False,
    "done": False,
    "phase": "",
    "message": "",
    "verses": 0,
    "commentaries": 0,
    "sources": 0,
    "characters": 0,
    "strong": 0,
    "concepts": 0,
    "doctrines": 0,
}


def _counts() -> dict:
    db = SessionLocal()
    try:
        return {
            "verses": db.query(models.Verse).count(),
            "commentaries": db.query(models.Commentary).count(),
            "sources": db.query(models.Source).count(),
            "characters": db.query(models.Character).count(),
            "strong": db.query(models.StrongEntry).count(),
            "concepts": db.query(models.Concept).count(),
            "doctrines": db.query(models.Doctrine).count(),
        }
    finally:
        db.close()


def verse_count() -> int:
    return _counts()["verses"]


def status() -> dict:
    out = dict(_STATE)
    out.update({f"{k}_now": v for k, v in _counts().items()})
    return out


def _set(phase: str, message: str) -> None:
    _STATE["phase"] = phase
    _STATE["message"] = message
    print(f"[bootstrap] {phase}: {message}", flush=True)


def ensure_books() -> int:
    db = SessionLocal()
    try:
        n = 0
        for _slug, ko_name, testament, _max_ch in BOOKS:
            ensure_book(db, ko_name, testament)
            n += 1
        return n
    finally:
        db.close()


def load_ko_pd() -> dict:
    m = load_manifest()
    errors = validate_manifest(m)
    if errors:
        raise RuntimeError("manifest invalid: " + "; ".join(errors))
    if not m.get("verified"):
        raise RuntimeError("manifest.verified is false")

    data_file = m.get("data_file") or "verses.jsonl"
    data_path = os.path.join(DATA_DIR, data_file)
    if not os.path.exists(data_path):
        raise RuntimeError(f"missing {data_path}")

    db = SessionLocal()
    stats = {"insert": 0, "update": 0, "skip": 0, "keep_existing": 0, "fail": 0, "no_book": 0}
    n = 0
    try:
        ensure_registry(db, m)
        for row in iter_verses(data_path):
            n += 1
            try:
                action = upsert_ko(
                    db,
                    str(row["book"]),
                    int(row["chapter"]),
                    int(row["verse"]),
                    str(row.get("text") or row.get("text_ko") or ""),
                )
                stats[action] = stats.get(action, 0) + 1
                if action in ("insert", "update") and stats[action] % 500 == 0:
                    db.commit()
                    _STATE["verses"] = n
                    _set("ko", f"loading KO… {n}")
            except Exception:
                db.rollback()
                stats["fail"] += 1
        db.commit()
    finally:
        db.close()
    stats["rows"] = n
    return stats


def seed_kg_safe() -> None:
    _set("kg", "seeding characters/events/doctrines…")
    from seed_kg_bulk import main as kg_main
    from seed_kg_gaps import main as gaps_main

    kg_main()
    gaps_main()


def _ensure_source(db, title: str, author: str, license_label: str, source_url: str, source_type: str) -> models.Source:
    src = db.query(models.Source).filter_by(title=title).first()
    if src:
        return src
    src = models.Source(
        title=title,
        author=author or "",
        publisher="ARK bootstrap snapshot",
        source_url=source_url or "",
        source_type=source_type or "Commentary",
        copyright_owner=author or "",
        copyright_status=license_label or "CC0-1.0",
        academic_level="A",
        verification_status="공개수집",
        tags="주석, commentary, bootstrap",
        description=f"{title} — {author}",
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def load_sources_snapshot() -> int:
    path = os.path.join(BOOT_DIR, "sources.jsonl")
    if not os.path.exists(path):
        _set("sources", "sources.jsonl missing — skip")
        return 0
    _set("sources", "loading sources snapshot…")
    db = SessionLocal()
    n = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                title = (row.get("title") or "").strip()
                if not title:
                    continue
                existing = db.query(models.Source).filter_by(title=title).first()
                if existing:
                    continue
                db.add(
                    models.Source(
                        title=title,
                        author=row.get("author") or "",
                        source_type=row.get("source_type") or "JournalArticle",
                        copyright_status=row.get("copyright_status") or "CC BY",
                        source_url=row.get("source_url") or "",
                        description=(row.get("description") or "")[:2000],
                        academic_level="B",
                        verification_status="공개수집",
                        tags="논문, paper, bootstrap",
                    )
                )
                n += 1
                if n % 50 == 0:
                    db.commit()
        db.commit()
    finally:
        db.close()
    _set("sources", f"sources loaded +{n}")
    return n


def load_commentaries_snapshot() -> int:
    gz = os.path.join(BOOT_DIR, "commentaries_core.jsonl.gz")
    raw = os.path.join(BOOT_DIR, "commentaries_core.jsonl")
    if os.path.exists(gz):
        opener = lambda: gzip.open(gz, "rt", encoding="utf-8")
    elif os.path.exists(raw):
        opener = lambda: open(raw, "r", encoding="utf-8")
    else:
        _set("commentaries", "commentaries snapshot missing — skip")
        return 0

    _set("commentaries", "loading commentary snapshot…")
    db = SessionLocal()
    book_cache: dict[str, int] = {}
    n = 0
    skip = 0
    try:
        with opener() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                book_name = row.get("book")
                text = (row.get("text") or "").strip()
                if not book_name or not text:
                    continue
                if book_name not in book_cache:
                    b = db.query(models.BibleBook).filter_by(name=book_name).first()
                    if not b:
                        skip += 1
                        continue
                    book_cache[book_name] = b.id
                passage = row.get("passage_ref") or f"{book_name}.{row.get('chapter')}"
                title = (row.get("title") or "Public Commentary").strip()
                author = (row.get("author") or "").strip()
                src = _ensure_source(
                    db,
                    title=title,
                    author=author,
                    license_label=row.get("license") or "CC0-1.0",
                    source_url=row.get("source_url") or "",
                    source_type="Commentary",
                )
                exists = (
                    db.query(models.Commentary.id)
                    .filter_by(source_id=src.id, passage_ref=passage)
                    .first()
                )
                if exists:
                    skip += 1
                    continue
                h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
                db.add(
                    models.Commentary(
                        source_id=src.id,
                        book_id=book_cache[book_name],
                        chapter_num=int(row.get("chapter") or 1),
                        verse_start=row.get("verse_start"),
                        verse_end=row.get("verse_end"),
                        passage_ref=passage,
                        commentary_text=text,
                        content_hash=h,
                    )
                )
                n += 1
                if n % 300 == 0:
                    db.commit()
                    _STATE["commentaries"] = n
                    _set("commentaries", f"loading commentaries… {n}")
        db.commit()
    finally:
        db.close()
    _set("commentaries", f"commentaries loaded +{n} (skip {skip})")
    return n


def _ensure_registry(
    db,
    code: str,
    title: str,
    author: str,
    source_url: str,
    copyright_status: str,
    license_type: str,
    attribution_text: str,
) -> models.SourceRegistry:
    row = db.query(models.SourceRegistry).filter_by(code=code).first()
    if row:
        return row
    row = models.SourceRegistry(
        code=code,
        title=title or code,
        author=author or "",
        publisher="ARK bootstrap",
        source_url=source_url or "",
        source_type="Lexicon",
        copyright_owner=author or "",
        copyright_status=copyright_status or "Public Domain",
        license_type=license_type or "Public Domain",
        attribution_text=attribution_text or title or code,
        commercial_use=True,
        allow_ai_quote=True,
        verification_status="공개수집",
    )
    db.add(row)
    db.flush()
    return row


def load_lexicon_snapshot() -> dict:
    strong_gz = os.path.join(BOOT_DIR, "strong_entries.jsonl.gz")
    exp_gz = os.path.join(BOOT_DIR, "lexicon_expansions.jsonl.gz")
    if not os.path.exists(strong_gz):
        _set("lexicon", "strong_entries.jsonl.gz missing — skip")
        return {"strong": 0, "expansions": 0}

    _set("lexicon", "loading Strong's lexicon…")
    db = SessionLocal()
    reg_cache: dict[str, int] = {}
    n_s = n_e = skip_s = skip_e = 0
    try:
        with gzip.open(strong_gz, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                sn = (row.get("strong_number") or "").strip().upper()
                if not sn:
                    continue
                if db.query(models.StrongEntry.id).filter_by(strong_number=sn).first():
                    skip_s += 1
                    continue
                code = (row.get("source_code") or "STRONGS_OS").strip()
                if code not in reg_cache:
                    reg = _ensure_registry(
                        db,
                        code=code,
                        title=row.get("source_title") or code,
                        author=row.get("source_author") or "",
                        source_url=row.get("source_url") or "",
                        copyright_status=row.get("copyright_status") or "Public Domain",
                        license_type=row.get("license_type") or "Public Domain",
                        attribution_text=row.get("attribution_text") or code,
                    )
                    reg_cache[code] = reg.id
                db.add(
                    models.StrongEntry(
                        strong_number=sn,
                        language_type=row.get("language_type") or ("Greek" if sn.startswith("G") else "Hebrew"),
                        lemma=row.get("lemma"),
                        transliteration=row.get("transliteration"),
                        pronunciation=row.get("pronunciation"),
                        gloss=row.get("gloss"),
                        definition_short=row.get("definition_short"),
                        definition_full=row.get("definition_full"),
                        morphology_hint=row.get("morphology_hint"),
                        root_word=row.get("root_word"),
                        source_id=reg_cache[code],
                        content_hash=row.get("content_hash"),
                    )
                )
                n_s += 1
                if n_s % 500 == 0:
                    db.commit()
                    _STATE["strong"] = n_s
                    _set("lexicon", f"loading Strong's… {n_s}")
        db.commit()

        if os.path.exists(exp_gz):
            _set("lexicon", "loading STEP expansions…")
            with gzip.open(exp_gz, "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    sn = (row.get("strong_number") or "").strip().upper()
                    name = (row.get("lexicon_name") or "").strip()
                    text = (row.get("entry_text") or "").strip()
                    if not sn or not name or not text:
                        continue
                    code = (row.get("source_code") or "STEP").strip()
                    if code not in reg_cache:
                        reg = _ensure_registry(
                            db,
                            code=code,
                            title=row.get("source_title") or code,
                            author=row.get("source_author") or "",
                            source_url=row.get("source_url") or "",
                            copyright_status=row.get("copyright_status") or "CC BY 4.0",
                            license_type=row.get("license_type") or "CC BY 4.0",
                            attribution_text=row.get("attribution_text") or "STEP Bible",
                        )
                        reg_cache[code] = reg.id
                    exists = (
                        db.query(models.LexiconExpansion.id)
                        .filter_by(strong_number=sn, lexicon_name=name, source_id=reg_cache[code])
                        .first()
                    )
                    if exists:
                        skip_e += 1
                        continue
                    db.add(
                        models.LexiconExpansion(
                            strong_number=sn,
                            lexicon_name=name,
                            entry_text=text,
                            source_id=reg_cache[code],
                            content_hash=row.get("content_hash"),
                        )
                    )
                    n_e += 1
                    if n_e % 400 == 0:
                        db.commit()
                        _set("lexicon", f"loading expansions… {n_e}")
            db.commit()
    finally:
        db.close()
    out = {"strong": n_s, "expansions": n_e, "skip_strong": skip_s, "skip_exp": skip_e}
    _set("lexicon", f"lexicon loaded {out}")
    return out


def run_bootstrap(force: bool = False) -> dict:
    with _LOCK:
        if _STATE["running"]:
            return status()
        _STATE["running"] = True
        _STATE["done"] = False
        _set("start", "starting packaged bootstrap")

    try:
        models.Base.metadata.create_all(bind=engine)
        c = _counts()

        _set("books", "ensuring 66 books…")
        ensure_books()

        if c["verses"] < 30000 or force:
            stats = load_ko_pd()
            _set("ko", f"KO done {stats}")
        else:
            _set("ko", f"KO already loaded ({c['verses']})")

        # 지식망 upsert — 교부·종교개혁 인물/교리 반영
        seed_kg_safe()

        if _counts()["sources"] < 40 or force:
            load_sources_snapshot()

        if _counts()["commentaries"] < 1000 or force:
            load_commentaries_snapshot()

        if _counts()["strong"] < 10000 or force:
            load_lexicon_snapshot()

        final = _counts()
        _STATE.update(final)
        _STATE["done"] = True
        _set("done", f"ok {final}")
        return status()
    except Exception as e:
        _STATE["message"] = f"error: {e}"
        print(f"[bootstrap] ERROR {e}", flush=True)
        return status()
    finally:
        _STATE["running"] = False


def start_bootstrap_background(force: bool = False) -> None:
    def _job():
        time.sleep(2)
        run_bootstrap(force=force)

    threading.Thread(target=_job, name="ark-bootstrap", daemon=True).start()
