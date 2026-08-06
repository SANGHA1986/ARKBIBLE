"""
클라우드(Render) 첫 기동용 — DB가 비어 있으면 개역한글 PD + 책/지식망 적재.

Git에 *.db 를 올리지 않으므로, 배포 서버는 이 부트스트랩으로 본문을 채운다.
"""
from __future__ import annotations

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


_LOCK = threading.Lock()
_STATE = {"running": False, "done": False, "message": "", "verses": 0}


def verse_count() -> int:
    db = SessionLocal()
    try:
        return db.query(models.Verse).count()
    finally:
        db.close()


def status() -> dict:
    out = dict(_STATE)
    out["verses_now"] = verse_count()
    return out


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
            except Exception:
                db.rollback()
                stats["fail"] += 1
        db.commit()
    finally:
        db.close()
    stats["rows"] = n
    return stats


def seed_kg_safe() -> None:
    try:
        from seed_kg_bulk import main as kg_main

        kg_main()
    except Exception as e:
        print(f"[bootstrap] kg seed skipped: {e}", flush=True)


def run_bootstrap(force: bool = False) -> dict:
    with _LOCK:
        if _STATE["running"]:
            return status()
        _STATE["running"] = True
        _STATE["message"] = "starting"
    try:
        models.Base.metadata.create_all(bind=engine)
        vc = verse_count()
        if vc >= 1000 and not force:
            _STATE["done"] = True
            _STATE["message"] = f"already loaded ({vc} verses)"
            _STATE["verses"] = vc
            return status()

        print("[bootstrap] ensure books…", flush=True)
        ensure_books()
        print("[bootstrap] load KO PD…", flush=True)
        stats = load_ko_pd()
        print(f"[bootstrap] KO done {stats}", flush=True)
        seed_kg_safe()
        vc = verse_count()
        _STATE["done"] = True
        _STATE["verses"] = vc
        _STATE["message"] = f"ok verses={vc} ko_stats={stats}"
        return status()
    except Exception as e:
        _STATE["message"] = f"error: {e}"
        print(f"[bootstrap] ERROR {e}", flush=True)
        return status()
    finally:
        _STATE["running"] = False


def start_bootstrap_background(force: bool = False) -> None:
    def _job():
        # 헬스체크가 먼저 통과하도록 약간 지연
        time.sleep(3)
        run_bootstrap(force=force)

    t = threading.Thread(target=_job, name="ark-bootstrap", daemon=True)
    t.start()
