"""
공개 성경 본문 적재 — World English Bible (Public Domain) via bible-api.com

한국어 개역개정 등 저작권 유효 역본은 수집하지 않음.
개역한글(1961) PD는 collect_ko_pd_bible.py (검증된 로컬 파일만).

사용:
  python collect_open_bible.py           # PRIORITY_CHAPTERS만
  python collect_open_bible.py --full    # 등록된 모든 책 전 장
  python collect_open_bible.py --gaps   # DB에 없는 장만 (중복 API 호출 최소)
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from database import SessionLocal
import models

# bible-api slug, 한글명, 구약/신약, 장 수
BOOKS: list[tuple[str, str, str, int]] = [
    ("genesis", "창세기", "구약", 50),
    ("exodus", "출애굽기", "구약", 40),
    ("leviticus", "레위기", "구약", 27),
    ("numbers", "민수기", "구약", 36),
    ("deuteronomy", "신명기", "구약", 34),
    ("joshua", "여호수아", "구약", 24),
    ("judges", "사사기", "구약", 21),
    ("ruth", "룻기", "구약", 4),
    ("1samuel", "사무엘상", "구약", 31),
    ("2samuel", "사무엘하", "구약", 24),
    ("1kings", "열왕기상", "구약", 22),
    ("2kings", "열왕기하", "구약", 25),
    ("1chronicles", "역대상", "구약", 29),
    ("2chronicles", "역대하", "구약", 36),
    ("ezra", "에스라", "구약", 10),
    ("nehemiah", "느헤미야", "구약", 13),
    ("esther", "에스더", "구약", 10),
    ("job", "욥기", "구약", 42),
    ("psalms", "시편", "구약", 150),
    ("proverbs", "잠언", "구약", 31),
    ("ecclesiastes", "전도서", "구약", 12),
    ("songofsolomon", "아가", "구약", 8),
    ("isaiah", "이사야", "구약", 66),
    ("jeremiah", "예레미야", "구약", 52),
    ("lamentations", "예레미야애가", "구약", 5),
    ("ezekiel", "에스겔", "구약", 48),
    ("daniel", "다니엘", "구약", 12),
    ("hosea", "호세아", "구약", 14),
    ("joel", "요엘", "구약", 3),
    ("amos", "아모스", "구약", 9),
    ("obadiah", "오바댜", "구약", 1),
    ("jonah", "요나", "구약", 4),
    ("micah", "미가", "구약", 7),
    ("nahum", "나훔", "구약", 3),
    ("habakkuk", "하박국", "구약", 3),
    ("zephaniah", "스바냐", "구약", 3),
    ("haggai", "학개", "구약", 2),
    ("zechariah", "스가랴", "구약", 14),
    ("malachi", "말라기", "구약", 4),
    ("matthew", "마태복음", "신약", 28),
    ("mark", "마가복음", "신약", 16),
    ("luke", "누가복음", "신약", 24),
    ("john", "요한복음", "신약", 21),
    ("acts", "사도행전", "신약", 28),
    ("romans", "로마서", "신약", 16),
    ("1corinthians", "고린도전서", "신약", 16),
    ("2corinthians", "고린도후서", "신약", 13),
    ("galatians", "갈라디아서", "신약", 6),
    ("ephesians", "에베소서", "신약", 6),
    ("philippians", "빌립보서", "신약", 4),
    ("colossians", "골로새서", "신약", 4),
    ("1thessalonians", "데살로니가전서", "신약", 5),
    ("2thessalonians", "데살로니가후서", "신약", 3),
    ("1timothy", "디모데전서", "신약", 6),
    ("2timothy", "디모데후서", "신약", 4),
    ("titus", "디도서", "신약", 3),
    ("philemon", "빌레몬서", "신약", 1),
    ("hebrews", "히브리서", "신약", 13),
    ("james", "야고보서", "신약", 5),
    ("1peter", "베드로전서", "신약", 5),
    ("2peter", "베드로후서", "신약", 3),
    ("1john", "요한일서", "신약", 5),
    ("2john", "요한이서", "신약", 1),
    ("3john", "요한삼서", "신약", 1),
    ("jude", "유다서", "신약", 1),
    ("revelation", "요한계시록", "신약", 22),
]

# 레거시 호환: slug -> 장 목록 ( --full / 기본 모드 없이 slug만 지정할 때 )
PRIORITY_CHAPTERS = {
    "genesis": list(range(1, 51)),
    "exodus": list(range(1, 41)),
    "matthew": list(range(1, 29)),
    "john": list(range(1, 22)),
    "romans": list(range(1, 17)),
    "1samuel": list(range(1, 32)),
    "psalms": [1, 8, 19, 23, 51, 91, 103, 119, 139],
    "isaiah": list(range(1, 67)),
    "1corinthians": list(range(1, 17)),
    "acts": list(range(1, 29)),
    "luke": list(range(1, 25)),
    "mark": list(range(1, 17)),
    "deuteronomy": list(range(1, 35)),
    "leviticus": list(range(1, 28)),
    "joshua": list(range(1, 25)),
    "judges": list(range(1, 22)),
    "2samuel": list(range(1, 25)),
    "1kings": list(range(1, 23)),
    "proverbs": list(range(1, 32)),
    "jeremiah": list(range(1, 53)),
    "galatians": list(range(1, 7)),
    "ephesians": list(range(1, 7)),
    "philippians": list(range(1, 5)),
    "hebrews": list(range(1, 14)),
    "revelation": list(range(1, 23)),
}

REQUEST_DELAY_SEC = 1.1
MAX_RETRIES = 5
PLACEHOLDER_KO = "[공개 한국어 번역 미등록 — 영문 WEB 참조]"


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)


def ensure_registry(db):
    from license_gate import assert_license_or_skip

    ok, reason = assert_license_or_skip("Public Domain", "Public Domain")
    if not ok:
        raise RuntimeError(f"WEB license rejected: {reason}")

    src = db.query(models.SourceRegistry).filter_by(code="WEB_PD").first()
    if src:
        # attribution 보강
        if not src.attribution_text:
            src.attribution_text = (
                "Scripture quotations from the World English Bible (WEB), Public Domain."
            )
            db.commit()
        return src
    src = models.SourceRegistry(
        code="WEB_PD",
        title="World English Bible (WEB)",
        author="WEB translation team",
        publisher="eBible.org / Public Domain",
        source_url="https://worldenglish.bible/",
        copyright_status="Public Domain",
        license_type="Public Domain",
        license_url="https://worldenglish.bible/",
        attribution_text="Scripture quotations from the World English Bible (WEB), Public Domain.",
        commercial_use=True,
        allow_ai_quote=True,
        publication_year=2000,
        verification_status="검증",
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def ensure_book(db, name: str, testament: str) -> models.BibleBook:
    row = db.query(models.BibleBook).filter_by(name=name).first()
    if row:
        return row
    row = models.BibleBook(name=name, testament=testament)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def chapter_has_verses(db, book_id: int, chapter: int) -> bool:
    return (
        db.query(models.Verse.id)
        .filter_by(book_id=book_id, chapter_num=chapter)
        .first()
        is not None
    )


def chapter_has_empty_en(db, book_id: int, chapter: int) -> bool:
    """장 안에 text_en 이 비어 있는 절이 있으면 True."""
    q = (
        db.query(models.Verse.id)
        .filter_by(book_id=book_id, chapter_num=chapter)
        .filter((models.Verse.text_en.is_(None)) | (models.Verse.text_en == ""))
    )
    return q.first() is not None


def fetch_chapter(slug: str, chapter: int) -> list[dict]:
    # 단권 짧은 책: `slug+1` 이 1절만 오는 경우가 있어 범위 쿼리 사용
    short_ranges = {
        "obadiah": "obadiah 1:1-21",
        "philemon": "philemon 1:1-25",
        "2john": "2john 1:1-13",
        "3john": "3john 1:1-14",
        "jude": "jude 1:1-25",
    }
    if slug in short_ranges and chapter == 1:
        path = short_ranges[slug]
    else:
        path = f"{slug}+{chapter}"
    url = f"https://bible-api.com/{urllib.parse.quote(path)}?translation=web"
    req = urllib.request.Request(url, headers={"User-Agent": "ARK-OpenCollector/1.0"})
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("verses") or []
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = min(30, 2 ** attempt * 2)
                log(f"  429 {slug} {chapter} — wait {wait}s (retry {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err or RuntimeError(f"fetch failed {slug} {chapter}")


def upsert_verse(db, book: models.BibleBook, chapter: int, verse: int, text_en: str):
    row = (
        db.query(models.Verse)
        .filter_by(book_id=book.id, chapter_num=chapter, verse_num=verse)
        .first()
    )
    if row:
        if row.text_en == text_en:
            return row, False
        row.text_en = text_en
        if not row.text_ko or row.text_ko.startswith("[공개 한국어"):
            row.text_ko = PLACEHOLDER_KO
        return row, True
    row = models.Verse(
        book_id=book.id,
        chapter_num=chapter,
        verse_num=verse,
        text_ko=PLACEHOLDER_KO,
        text_en=text_en,
        text_original=None,
    )
    db.add(row)
    return row, True


def chapters_for_book(slug: str, max_ch: int, full: bool, gaps_only: bool) -> list[int]:
    if gaps_only or full:
        return list(range(1, max_ch + 1))
    return PRIORITY_CHAPTERS.get(slug, [1])


def ingest_chapter(db, book: models.BibleBook, slug: str, ko_name: str, ch: int, gaps_only: bool):
    if gaps_only and chapter_has_verses(db, book.id, ch):
        return 0, "skip"
    verses = fetch_chapter(slug, ch)
    if not verses:
        return 0, "empty"
    touched = 0
    for v in verses:
        _, changed = upsert_verse(
            db, book, int(v["chapter"]), int(v["verse"]), v["text"].strip()
        )
        if changed:
            touched += 1
    db.commit()
    return touched, f"+ {ko_name} {ch} ({len(verses)} verses, touched={touched})"


def main(full: bool = False, gaps_only: bool = False, fill_empty_en: bool = False):
    db = SessionLocal()
    skipped = fetched = failed = 0
    verses_touched = 0
    t0 = time.time()
    try:
        ensure_registry(db)
        for slug, ko_name, testament, max_ch in BOOKS:
            book = ensure_book(db, ko_name, testament)
            chapters = chapters_for_book(slug, max_ch, full or fill_empty_en, gaps_only)
            for ch in chapters:
                try:
                    if gaps_only and chapter_has_verses(db, book.id, ch):
                        skipped += 1
                        continue
                    if fill_empty_en:
                        # 장이 아예 없으면 채우고, EN 빈 절이 있을 때만 재수집
                        if chapter_has_verses(db, book.id, ch) and not chapter_has_empty_en(
                            db, book.id, ch
                        ):
                            skipped += 1
                            continue
                    n, msg = ingest_chapter(db, book, slug, ko_name, ch, gaps_only=False)
                    if msg == "skip":
                        skipped += 1
                    else:
                        verses_touched += n
                        fetched += 1
                        log(msg)
                    time.sleep(REQUEST_DELAY_SEC)
                except Exception as e:
                    db.rollback()
                    failed += 1
                    log(f"! {slug} {ch}: {e}")
                    time.sleep(3)
        elapsed = int(time.time() - t0)
        log(
            f"OK bible ingest verses_touched={verses_touched} "
            f"chapters_fetched={fetched} skipped={skipped} failed={failed} elapsed_sec={elapsed}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    main(
        full="--full" in sys.argv,
        gaps_only="--gaps" in sys.argv,
        fill_empty_en="--fill-empty-en" in sys.argv,
    )
