"""
공개 주석 수집기 — OpenChristianData/open-christian-data (CC0) GitHub JSON.

데이터: 책별 JSON 파일 (meta + data[]). 각 entry는 book_osis/chapter/verse_range_osis 기준.
라이선스: CC0-1.0 (Public Domain) 만 허용.

사용:
  python collect_open_commentaries.py                  # 우선순위 책 (요한, 창세, 로마서 등)
  python collect_open_commentaries.py --set matthew-henry --book john
  python collect_open_commentaries.py --set matthew-henry              # 한 주석가 전책
  python collect_open_commentaries.py --all                           # 전체 세트/전책 (시간 오래 걸림)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Optional

from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine

USER_AGENT = "ARK-OpenCommentary/0.2 (+research)"
REPO_OWNER = "OpenChristianData"
REPO_NAME = "open-christian-data"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main"
API_TREE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/main?recursive=1"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache", "commentaries")
os.makedirs(DATA_DIR, exist_ok=True)

# 영문 책 slug -> 한글 책명 매핑 (OpenChristianData 파일명 기준)
SLUG_TO_KO = {
    "genesis": "창세기", "exodus": "출애굽기", "leviticus": "레위기", "numbers": "민수기",
    "deuteronomy": "신명기", "joshua": "여호수아", "judges": "사사기", "ruth": "룻기",
    "1-samuel": "사무엘상", "2-samuel": "사무엘하", "1-kings": "열왕기상", "2-kings": "열왕기하",
    "1-chronicles": "역대상", "2-chronicles": "역대하", "ezra": "에스라", "nehemiah": "느헤미야",
    "esther": "에스더", "job": "욥기", "psalms": "시편", "psalm": "시편", "proverbs": "잠언",
    "ecclesiastes": "전도서", "song-of-solomon": "아가", "song-of-songs": "아가",
    "isaiah": "이사야", "jeremiah": "예레미야", "lamentations": "예레미야애가",
    "ezekiel": "에스겔", "daniel": "다니엘", "hosea": "호세아", "joel": "요엘",
    "amos": "아모스", "obadiah": "오바댜", "jonah": "요나", "micah": "미가",
    "nahum": "나훔", "habakkuk": "하박국", "zephaniah": "스바냐", "haggai": "학개",
    "zechariah": "스가랴", "malachi": "말라기",
    "matthew": "마태복음", "mark": "마가복음", "luke": "누가복음", "john": "요한복음",
    "acts": "사도행전", "romans": "로마서", "1-corinthians": "고린도전서",
    "2-corinthians": "고린도후서", "galatians": "갈라디아서", "ephesians": "에베소서",
    "philippians": "빌립보서", "colossians": "골로새서",
    "1-thessalonians": "데살로니가전서", "2-thessalonians": "데살로니가후서",
    "1-timothy": "디모데전서", "2-timothy": "디모데후서", "titus": "디도서",
    "philemon": "빌레몬서", "hebrews": "히브리서", "james": "야고보서",
    "1-peter": "베드로전서", "2-peter": "베드로후서",
    "1-john": "요한일서", "2-john": "요한이서", "3-john": "요한삼서",
    "jude": "유다서", "revelation": "요한계시록",
}

# 우선순위 책 (자주 검색되는 책)
PRIORITY_BOOKS = ["john", "genesis", "romans", "matthew", "psalms", "isaiah",
                  "exodus", "acts", "1-corinthians", "hebrews", "revelation",
                  "jude", "galatians", "ephesians", "philippians", "colossians",
                  "1-peter", "2-peter", "1-john", "james", "luke", "mark",
                  "1-kings", "2-kings", "1-samuel", "2-samuel", "1-chronicles",
                  "2-chronicles", "jeremiah", "ezekiel", "daniel", "job",
                  "proverbs", "deuteronomy", "numbers", "leviticus", "joshua",
                  "judges", "ruth"]

# 수집할 주석 세트 (CC0 확인된 것들)
COMMENTARY_SETS = [
    "matthew-henry",
    "jamieson-fausset-brown",
    "adam-clarke",
    "john-gill",
    "wesley",
    "keil-delitzsch",
]


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("ascii", "replace"), flush=True)


def http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def ensure_source(db: Session, meta: dict) -> models.Source:
    title = meta.get("title") or meta.get("id", "Unknown Commentary")
    src = db.query(models.Source).filter_by(title=title).first()
    license_type = (meta.get("license") or "cc0-1.0").upper()
    if src:
        return src
    author = meta.get("author") or ""
    tradition = ", ".join(meta.get("tradition") or [])
    src = models.Source(
        title=title,
        author=author,
        publisher="OpenChristianData (GitHub)",
        source_url=f"https://github.com/{REPO_OWNER}/{REPO_NAME}",
        source_type="Commentary",
        copyright_owner=author,
        copyright_status=license_type,
        academic_level="A",
        verification_status="공개수집",
        tags=f"주석, commentary, {tradition}, {meta.get('id','')}",
        description=f"{title} — {author} ({meta.get('original_publication_year','')}). {tradition}".strip(),
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    if not getattr(src, "license", None):
        lic = models.License(
            source_id=src.id,
            license_type=license_type,
            license_url=meta.get("license_url") or "https://creativecommons.org/publicdomain/zero/1.0/",
            visibility_level="Public",
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


def parse_verse_range(vr: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """'16' -> (16,16); '1-3' -> (1,3); 'intro'/None -> (None,None)."""
    if not vr or vr == "intro":
        return (None, None)
    m = re.match(r"^(\d+)(?:-(\d+))?$", str(vr).strip())
    if not m:
        return (None, None)
    vs = int(m.group(1))
    ve = int(m.group(2)) if m.group(2) else vs
    return (vs, ve)


def upsert_commentary(db: Session, src: models.Source, book: models.BibleBook,
                      chapter: int, v_start: Optional[int], v_end: Optional[int],
                      passage_ref: str, text: str) -> str:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = (
        db.query(models.Commentary)
        .filter_by(source_id=src.id, passage_ref=passage_ref)
        .first()
    )
    if existing:
        if existing.content_hash == content_hash:
            return "skip"
        existing.commentary_text = text
        existing.content_hash = content_hash
        return "update"
    db.add(models.Commentary(
        source_id=src.id,
        book_id=book.id,
        chapter_num=chapter,
        verse_start=v_start,
        verse_end=v_end,
        passage_ref=passage_ref,
        commentary_text=text,
        content_hash=content_hash,
    ))
    return "insert"


def ingest_file(db: Session, set_slug: str, book_slug: str) -> dict:
    url = f"{RAW_BASE}/data/commentaries/{set_slug}/{book_slug}.json"
    try:
        raw = http_get(url, timeout=90)
    except Exception as e:
        log(f"  fetch fail {set_slug}/{book_slug}: {e}")
        return {"insert": 0, "update": 0, "skip": 0, "fail": 1}

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        log(f"  parse fail {set_slug}/{book_slug}: {e}")
        return {"insert": 0, "update": 0, "skip": 0, "fail": 1}

    meta = data.get("meta", {})
    from license_gate import assert_license_or_skip

    license_type = meta.get("license") or meta.get("license_type") or ""
    # 메타에 라이선스가 없으면 OpenChristianData 기본 CC0으로 간주하되, 명시 거부 문자열은 차단
    check_lic = license_type or "cc0-1.0"
    ok, reason = assert_license_or_skip(check_lic)
    if not ok:
        log(f"  skip {set_slug}/{book_slug}: license={license_type or '(empty)'} ({reason})")
        return {"insert": 0, "update": 0, "skip": 0, "fail": 0, "blocked": 1}

    src = ensure_source(db, meta)
    entries = data.get("data", [])
    stats = {"insert": 0, "update": 0, "skip": 0, "fail": 0}
    book_ko = SLUG_TO_KO.get(book_slug)
    if not book_ko:
        log(f"  unknown book slug: {book_slug}")
        return {"insert": 0, "update": 0, "skip": 0, "fail": len(entries)}
    book = db.query(models.BibleBook).filter_by(name=book_ko).first()
    if not book:
        log(f"  book not in DB: {book_ko}")
        return {"insert": 0, "update": 0, "skip": 0, "fail": len(entries)}

    batch_count = 0
    for entry in entries:
        chapter = entry.get("chapter", 0)
        vr = entry.get("verse_range")
        v_start, v_end = parse_verse_range(vr)
        text = (entry.get("commentary_text") or "").strip()
        if not text:
            continue
        vr_osis = entry.get("verse_range_osis")
        if vr_osis:
            passage_ref = vr_osis
        elif chapter == 0:
            passage_ref = f"{entry.get('book_osis','?')}.intro"
        else:
            passage_ref = f"{entry.get('book_osis','?')}.{chapter}.{vr or ''}"
        action = upsert_commentary(db, src, book, chapter or 0, v_start, v_end, passage_ref, text)
        stats[action] = stats.get(action, 0) + 1
        batch_count += 1
        if batch_count % 50 == 0:
            db.commit()
    db.commit()
    return stats


def list_repo_files() -> dict:
    """GitHub tree에서 commentary 세트별 파일 목록을 반환."""
    try:
        raw = http_get(API_TREE, timeout=30)
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        log(f"  github tree fetch fail: {e}")
        return {}
    result: dict[str, list[str]] = {}
    for t in data.get("tree", []):
        if t.get("type") != "blob":
            continue
        path = t.get("path", "")
        if not path.startswith("data/commentaries/") or not path.endswith(".json"):
            continue
        parts = path.split("/")
        if len(parts) < 4:
            continue
        set_slug = parts[2]
        fname = parts[3]
        if fname.startswith("_") or fname == "manifest.json":
            continue
        book_slug = fname[:-5]  # remove .json
        result.setdefault(set_slug, []).append(book_slug)
    return result


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        log("=== ARK Open Commentary Collector (OpenChristianData CC0) ===")
        log("라이선스 게이트: COLLECT_POLICY / license_gate - PD/CC0/CC BY only (no BY-SA)")

        args = sys.argv[1:]
        do_all = "--all" in args
        target_set = None
        target_book = None
        if "--set" in args:
            target_set = args[args.index("--set") + 1]
        if "--book" in args:
            target_book = args[args.index("--book") + 1]

        repo_files = list_repo_files()
        log(f"repo commentary sets: {len(repo_files)}")

        if do_all:
            sets = COMMENTARY_SETS
        elif target_set:
            sets = [target_set]
        else:
            sets = COMMENTARY_SETS

        total = {"insert": 0, "update": 0, "skip": 0, "fail": 0}
        for set_slug in sets:
            if set_slug not in repo_files:
                log(f"[{set_slug}] 세트 없음, 스킵")
                continue
            books = repo_files[set_slug]
            if target_book:
                books = [b for b in books if b == target_book]
            elif not do_all and not target_set:
                # 우선순위 책만
                books = [b for b in PRIORITY_BOOKS if b in books]
            log(f"[{set_slug}] 수집 대상 {len(books)}권: {books}")
            for book_slug in books:
                stats = ingest_file(db, set_slug, book_slug)
                for k, v in stats.items():
                    total[k] = total.get(k, 0) + v
                log(f"  {set_slug}/{book_slug}: {stats}")
                time.sleep(0.3)

        n = db.query(models.Commentary).count()
        log(f"DONE commentaries={n:,} | stats={total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
