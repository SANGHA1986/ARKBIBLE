"""
공개 연관 구절 수집기 — OpenBible.info Cross References (CC BY).

데이터: TSV (From Verse, To Verse, Votes)
  예: Gen.1.1   Joh.1.1-3   42

사용:
  python collect_cross_references.py
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
import urllib.request
import zipfile
from typing import Optional

from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine

USER_AGENT = "ARK-OpenCrossRef/0.1"
DATA_URL = "https://a.openbible.info/data/cross-references.zip"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache")
os.makedirs(DATA_DIR, exist_ok=True)

# OSIS slug -> 한글 책명 (역매핑)
OSIS_TO_KO = {
    "Gen": "창세기", "Exod": "출애굽기", "Lev": "레위기", "Num": "민수기",
    "Deut": "신명기", "Josh": "여호수아", "Judg": "사사기", "Ruth": "룻기",
    "1Sam": "사무엘상", "2Sam": "사무엘하", "1Kgs": "열왕기상", "2Kgs": "열왕기하",
    "1Chr": "역대상", "2Chr": "역대하", "Ezra": "에스라", "Neh": "느헤미야",
    "Esth": "에스더", "Job": "욥기", "Ps": "시편", "Prov": "잠언",
    "Eccl": "전도서", "Song": "아가", "Isa": "이사야", "Jer": "예레미야",
    "Lam": "예레미야애가", "Ezek": "에스겔", "Dan": "다니엘", "Hos": "호세아",
    "Joel": "요엘", "Amos": "아모스", "Obad": "오바댜", "Jonah": "요나",
    "Mic": "미가", "Nah": "나훔", "Hab": "하박국", "Zeph": "스바냐",
    "Hag": "학개", "Zech": "스가랴", "Mal": "말라기",
    "Matt": "마태복음", "Mark": "마가복음", "Luke": "누가복음", "John": "요한복음",
    "Acts": "사도행전", "Rom": "로마서", "1Cor": "고린도전서", "2Cor": "고린도후서",
    "Gal": "갈라디아서", "Eph": "에베소서", "Phil": "빌립보서", "Col": "골로새서",
    "1Thess": "데살로니가전서", "2Thess": "데살로니가후서",
    "1Tim": "디모데전서", "2Tim": "디모데후서", "Titus": "디도서",
    "Phlm": "빌레몬서", "Heb": "히브리서", "Jas": "야고보서",
    "1Pet": "베드로전서", "2Pet": "베드로후서",
    "1John": "요한일서", "2John": "요한이서", "3John": "요한삼서",
    "Jude": "유다서", "Rev": "요한계시록",
}


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("ascii", "replace"), flush=True)


def ensure_source(db: Session) -> models.Source:
    from license_gate import assert_license_or_skip

    ok, reason = assert_license_or_skip("CC BY", "CC BY")
    if not ok:
        raise RuntimeError(f"OpenBible license rejected: {reason}")

    title = "OpenBible.info Cross References (CC BY)"
    src = db.query(models.Source).filter_by(title=title).first()
    if src:
        return src
    src = models.Source(
        title=title,
        author="OpenBible.info",
        publisher="OpenBible.info",
        source_url="https://www.openbible.info/labs/cross-references/",
        source_type="CrossReference",
        copyright_owner="OpenBible.info",
        copyright_status="CC BY",
        academic_level="B",
        verification_status="공개수집",
        tags="연관, cross-reference, TSK, Treasury of Scripture Knowledge",
        description=(
            "OpenBible.info 연관 구절 데이터 — Treasury of Scripture Knowledge 기반 (CC BY). "
            "Attribution: OpenBible.info (https://www.openbible.info/labs/cross-references/)."
        ),
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    if not getattr(src, "license", None):
        lic = models.License(
            source_id=src.id,
            license_type="CC BY",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            visibility_level="Public",
            commercial_use=True,
            allow_ai_read=True,
            allow_ai_summary=True,
            allow_ai_embedding=True,
            allow_ai_quote=True,
            allow_free_user=True,
            allow_paid_user=True,
            allow_institution=True,
            can_view_original=True,
            can_download=True,
        )
        db.add(lic)
        db.commit()
    return src


def download_zip() -> str:
    dest = os.path.join(DATA_DIR, "cross-references.zip")
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        log(f"[cache] {dest}")
        return dest
    log(f"[download] {DATA_URL}")
    req = urllib.request.Request(DATA_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def parse_ref(ref: str) -> Optional[tuple[str, int, int, int]]:
    """'Gen.1.1' / 'Joh.1.1-3' / 'Rom.8.28-Rom.8.30' -> (osis, chapter, v_start, v_end)."""
    ref = ref.strip()
    # 단일 구절 또는 단축 범위: Book.Ch.Verse / Book.Ch.Verse-VerseEnd
    m = re.match(r"^([A-Za-z0-9]+)\.(\d+)\.(\d+)(?:-(\d+))?$", ref)
    if m:
        osis = m.group(1)
        ch = int(m.group(2))
        vs = int(m.group(3))
        ve = int(m.group(4)) if m.group(4) else vs
        return (osis, ch, vs, ve)
    # 전체 범위: Book.Ch.Vs-Book.Ch.Ve
    m = re.match(r"^([A-Za-z0-9]+)\.(\d+)\.(\d+)-([A-Za-z0-9]+)\.(\d+)\.(\d+)$", ref)
    if m:
        if m.group(1) != m.group(4):
            return None  # 다른 책에 걸치는 범위는 미지원
        return (m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(6)))
    return None


def upsert_crossref(db: Session, src: models.Source,
                    from_book: models.BibleBook, from_ch: int, from_v: int,
                    to_book: models.BibleBook, to_ch: int, to_vs: int, to_ve: int,
                    votes: int) -> str:
    existing = (
        db.query(models.CrossReference)
        .filter_by(
            source_id=src.id,
            from_book_id=from_book.id, from_chapter=from_ch, from_verse=from_v,
            to_book_id=to_book.id, to_chapter=to_ch,
            to_verse_start=to_vs, to_verse_end=to_ve,
        )
        .first()
    )
    if existing:
        if existing.votes != votes:
            existing.votes = votes
            return "update"
        return "skip"
    db.add(models.CrossReference(
        source_id=src.id,
        from_book_id=from_book.id, from_chapter=from_ch, from_verse=from_v,
        to_book_id=to_book.id, to_chapter=to_ch,
        to_verse_start=to_vs, to_verse_end=to_ve,
        votes=votes,
    ))
    return "insert"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        log("=== ARK Cross-Reference Collector (OpenBible CC BY) ===")
        src = ensure_source(db)
        zip_path = download_zip()
        # 압축 해제 후 TSV 읽기
        with zipfile.ZipFile(zip_path, "r") as zf:
            tsv_name = next((n for n in zf.namelist() if n.endswith((".tsv", ".txt"))), None)
            if not tsv_name:
                log("no TSV in zip")
                return
            with zf.open(tsv_name, "r") as f:
                raw = io.TextIOWrapper(f, encoding="utf-8")
                lines = raw.readlines()

        # 캐시: 한글 책명
        book_cache = {b.name: b for b in db.query(models.BibleBook).all()}

        # 기존 cross-reference 전체 삭제 (이전 부분 실행 분량) 후 클린 bulk insert
        db.query(models.CrossReference).filter_by(source_id=src.id).delete()
        db.commit()
        existing_keys: set[tuple] = set()
        log("[reset] cleared existing cross-refs for clean bulk insert")

        stats = {"insert": 0, "skip": 0, "bad": 0}
        batch: list[tuple] = []
        BATCH_SIZE = 2000

        from sqlalchemy import text
        insert_sql = text(
            "INSERT OR IGNORE INTO cross_references "
            "(source_id, from_book_id, from_chapter, from_verse, "
            "to_book_id, to_chapter, to_verse_start, to_verse_end, votes) "
            "VALUES (:s, :fb, :fc, :fv, :tb, :tc, :tvs, :tve, :v)"
        )

        def flush():
            if batch:
                db.execute(insert_sql, batch)
                db.commit()
                batch.clear()

        for i, line in enumerate(lines):
            line = line.rstrip("\n")
            if not line or line.startswith("From"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            from_ref, to_ref = parts[0], parts[1]
            votes = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

            fr = parse_ref(from_ref)
            to = parse_ref(to_ref)
            if not fr or not to:
                stats["bad"] += 1
                continue
            from_ko = OSIS_TO_KO.get(fr[0])
            to_ko = OSIS_TO_KO.get(to[0])
            if not from_ko or not to_ko:
                stats["bad"] += 1
                continue
            from_book = book_cache.get(from_ko)
            to_book = book_cache.get(to_ko)
            if not from_book or not to_book:
                stats["bad"] += 1
                continue

            key = (from_book.id, fr[1], fr[2], to_book.id, to[1], to[2], to[3])
            if key in existing_keys:
                stats["skip"] += 1
                continue

            batch.append({
                "s": src.id, "fb": from_book.id, "fc": fr[1], "fv": fr[2],
                "tb": to_book.id, "tc": to[1], "tvs": to[2], "tve": to[3], "v": votes,
            })
            existing_keys.add(key)
            stats["insert"] += 1

            if len(batch) >= BATCH_SIZE:
                flush()
                if stats["insert"] % 20000 == 0:
                    log(f"  ... insert={stats['insert']:,} skip={stats['skip']:,} bad={stats['bad']:,}")

        flush()
        log(f"DONE cross_references stats={stats}")
        n = db.query(models.CrossReference).count()
        log(f"DB total cross_references={n:,}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
