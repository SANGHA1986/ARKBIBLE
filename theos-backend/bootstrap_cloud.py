"""
클라우드(Render) 부트스트랩 — 테스트용으로 본문+주석+논문+지식망까지 채움.

Git에 *.db 를 올리지 않으므로, 배포 서버는 이 스크립트로 채운다.
무료 인스턴스는 재배포 시 디스크가 비워질 수 있어, 기동 시 자동 재적재한다.
"""
from __future__ import annotations

import os
import sys
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
}


def _counts() -> dict:
    db = SessionLocal()
    try:
        return {
            "verses": db.query(models.Verse).count(),
            "commentaries": db.query(models.Commentary).count(),
            "sources": db.query(models.Source).count(),
            "characters": db.query(models.Character).count(),
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


def collect_papers_safe(limit: int = 100) -> None:
    _set("papers", f"collecting OA papers (limit={limit})…")
    import collect_oa_papers as papers

    old = list(sys.argv)
    try:
        sys.argv = ["collect_oa_papers.py", "--limit", str(limit)]
        papers.main()
    finally:
        sys.argv = old


def collect_commentaries_safe() -> None:
    """목사 테스트용: 핵심 책 × 전 CC0 주석 세트."""
    _set("commentaries", "collecting CC0 commentaries (core books)…")
    import collect_open_commentaries as co

    core_books = [
        "john",
        "genesis",
        "romans",
        "matthew",
        "psalms",
        "isaiah",
        "exodus",
        "acts",
        "luke",
        "mark",
        "hebrews",
        "revelation",
        "1-corinthians",
        "philippians",
        "james",
        "1-john",
        "galatians",
        "ephesians",
        "colossians",
        "1-peter",
    ]
    # 우선순위 목록을 핵심 책으로 일시 교체
    old_priority = list(co.PRIORITY_BOOKS)
    old_argv = list(sys.argv)
    try:
        co.PRIORITY_BOOKS[:] = core_books
        sys.argv = ["collect_open_commentaries.py"]
        co.main()
    finally:
        co.PRIORITY_BOOKS[:] = old_priority
        sys.argv = old_argv


def collect_crossrefs_safe() -> None:
    _set("crossrefs", "collecting OpenBible cross-references…")
    import collect_cross_references as xref

    old = list(sys.argv)
    try:
        sys.argv = ["collect_cross_references.py"]
        xref.main()
    finally:
        sys.argv = old


def collect_lexicons_safe() -> None:
    _set("lexicons", "collecting Strong/STEP lexicons…")
    import collect_open_lexicons as lex

    old = list(sys.argv)
    try:
        sys.argv = ["collect_open_lexicons.py"]
        lex.main()
    finally:
        sys.argv = old


def run_bootstrap(force: bool = False) -> dict:
    with _LOCK:
        if _STATE["running"]:
            return status()
        _STATE["running"] = True
        _STATE["done"] = False
        _set("start", "starting full beta bootstrap")

    try:
        models.Base.metadata.create_all(bind=engine)
        c = _counts()

        # 1) 본문
        if c["verses"] < 30000 or force:
            _set("books", "ensuring 66 books…")
            ensure_books()
            stats = load_ko_pd()
            _set("ko", f"KO done {stats}")
        else:
            _set("ko", f"KO already loaded ({c['verses']})")

        # 2) 지식망
        if c["characters"] < 50 or force or _counts()["characters"] < 50:
            seed_kg_safe()

        # 3) 논문
        if _counts()["sources"] < 40 or force:
            collect_papers_safe(limit=100)

        # 4) 주석 (시간 김 — 백그라운드 스레드에서 실행)
        if _counts()["commentaries"] < 1000 or force:
            collect_commentaries_safe()

        # 5) 연관구절
        try:
            collect_crossrefs_safe()
        except Exception as e:
            _set("crossrefs", f"skipped: {e}")

        # 6) 원어
        try:
            collect_lexicons_safe()
        except Exception as e:
            _set("lexicons", f"skipped: {e}")

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
