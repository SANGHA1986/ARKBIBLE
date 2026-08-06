"""
개역한글(1961) Public Domain 적재기 — COLLECT_POLICY.md 준수

원칙:
  - 저작권 만료(PD) 판본만. 개역개정 등 유효 저작권 역본 금지.
  - GitHub 일괄 dump 금지. 로컬 검증 파일 + 매니페스트만.
  - UI/API용 역본명·출처·라이선스를 SourceRegistry에 기록.

디렉터리: theos-backend/data_ko_pd/
  manifest.json  (필수)
  verses.jsonl   또는 verses.json  (본문)

manifest.json 예:
{
  "version_code": "KO_GAEYEOK_1961",
  "version_label": "개역한글(1961)",
  "license_type": "Public Domain",
  "copyright_status": "Public Domain",
  "source_url": "https://…",
  "attribution_text": "개역한글(1961) · Public Domain · {출처}",
  "notice": "NOTICE에 PD로 확인된 디지털 출처 URL/레포를 기입",
  "verified": false
}

verses.jsonl 한 줄:
{"book":"창세기","chapter":1,"verse":1,"text":"…"}

사용:
  python collect_ko_pd_bible.py              # manifest 검사 + verified면 적재
  python collect_ko_pd_bible.py --check-only # 검증만
  python collect_ko_pd_bible.py --force      # verified=false여도 적재(비권장)
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Iterator

from database import SessionLocal, engine
import models
from license_gate import (
    assert_license_or_skip,
    looks_like_forbidden_ko_version,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_ko_pd")
MANIFEST_NAME = "manifest.json"


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("ascii", "replace"), flush=True)


def write_examples() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    man_path = os.path.join(DATA_DIR, MANIFEST_NAME)
    if not os.path.exists(man_path):
        example = {
            "version_code": "KO_GAEYEOK_1961",
            "version_label": "개역한글(1961)",
            "license_type": "Public Domain",
            "copyright_status": "Public Domain",
            "source_url": "",
            "attribution_text": "개역한글(1961) · Public Domain · (디지털 출처 URL을 기입하세요)",
            "notice": (
                "대한성서공회 등 공식 안내상 개역한글(1961)은 저작권 만료(PD)로 알려짐. "
                "실제 파일 판본·NOTICE를 확인한 뒤 verified=true 로 바꾸세요. "
                "개역개정과 혼동 금지. crizin/bible-db 는 NOTICE 항목별로만 채택."
            ),
            "verified": False,
            "data_file": "verses.jsonl",
        }
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(example, f, ensure_ascii=False, indent=2)
        log(f"[template] wrote {man_path}")
    sample = os.path.join(DATA_DIR, "verses.example.jsonl")
    if not os.path.exists(sample):
        with open(sample, "w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "book": "창세기",
                        "chapter": 1,
                        "verse": 1,
                        "text": "(PD 본문 샘플 — 실제 개역한글 1961 텍스트로 교체)",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        log(f"[template] wrote {sample}")


def load_manifest() -> dict[str, Any]:
    path = os.path.join(DATA_DIR, MANIFEST_NAME)
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing {path} — run once to create template")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_manifest(m: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    label = m.get("version_label") or ""
    lic = m.get("license_type") or ""
    status = m.get("copyright_status") or ""
    ok, reason = assert_license_or_skip(lic, status if status in ("Copyrighted", "Unknown", "Unsafe", "") else None)
    if not ok:
        errors.append(f"license gate: {reason}")
    if "개역한글" not in label and "1961" not in label:
        errors.append("version_label should identify 개역한글(1961)")
    if looks_like_forbidden_ko_version(label) or looks_like_forbidden_ko_version(m.get("notice") or ""):
        # notice may mention 개역개정 as "do not use" — only fail on label/title
        if looks_like_forbidden_ko_version(label):
            errors.append("forbidden KO version in version_label")
    if not (m.get("source_url") or "").strip():
        errors.append("source_url empty — set digital provenance URL")
    if not (m.get("attribution_text") or "").strip():
        errors.append("attribution_text required")
    return errors


def ensure_registry(db, m: dict[str, Any]) -> models.SourceRegistry:
    code = m.get("version_code") or "KO_GAEYEOK_1961"
    row = db.query(models.SourceRegistry).filter_by(code=code).first()
    meta = {
        "title": m.get("version_label") or "개역한글(1961)",
        "author": "대한성서공회 (역사적 번역) / Public Domain",
        "publisher": "Public Domain digital source",
        "source_url": m.get("source_url") or "",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "license_url": m.get("source_url") or "",
        "attribution_text": m.get("attribution_text")
        or "개역한글(1961) · Public Domain",
        "commercial_use": True,
        "allow_ai_quote": True,
        "publication_year": 1961,
        "verification_status": "검증됨" if m.get("verified") else "미검증",
    }
    if row:
        for k, v in meta.items():
            setattr(row, k, v)
        db.commit()
        return row
    row = models.SourceRegistry(code=code, **meta)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def iter_verses(data_path: str) -> Iterator[dict]:
    if data_path.endswith(".jsonl"):
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)
        return
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        for row in data:
            yield row
    elif isinstance(data, dict) and "verses" in data:
        for row in data["verses"]:
            yield row
    else:
        raise ValueError("unsupported verses file format")


def upsert_ko(db, book_name: str, chapter: int, verse: int, text: str) -> str:
    book = db.query(models.BibleBook).filter_by(name=book_name).first()
    if not book:
        return "no_book"
    row = (
        db.query(models.Verse)
        .filter_by(book_id=book.id, chapter_num=chapter, verse_num=verse)
        .first()
    )
    text = (text or "").strip()
    if not text:
        return "empty"
    if looks_like_forbidden_ko_version(text[:80]):
        return "forbidden_marker"
    if row:
        # placeholder 또는 비어 있을 때만 덮어쓰기 (기존 시드 보존 우선)
        cur = (row.text_ko or "").strip()
        if cur == text:
            return "skip"
        if not cur or cur.startswith("[공개 한국어"):
            row.text_ko = text
            return "update"
        return "keep_existing"
    row = models.Verse(
        book_id=book.id,
        chapter_num=chapter,
        verse_num=verse,
        text_ko=text,
        text_en="",
        text_original=None,
    )
    db.add(row)
    return "insert"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    check_only = "--check-only" in sys.argv
    force = "--force" in sys.argv

    models.Base.metadata.create_all(bind=engine)
    write_examples()
    log("=== ARK KO PD Bible Collector (개역한글 1961) ===")
    log("See COLLECT_POLICY.md — no bulk GitHub dump; verified local files only.")

    m = load_manifest()
    errors = validate_manifest(m)
    for e in errors:
        log(f"! validation: {e}")
    if errors and not force:
        log("STOP: fix manifest (or pass --force after you accept risk)")
        if check_only:
            sys.exit(1)
        sys.exit(1)

    if not m.get("verified") and not force:
        log("STOP: manifest.verified is false. Confirm PD edition, set verified=true.")
        log("Checklist: edition=1961, not 개역개정, NOTICE/source_url filled, sample verses OK.")
        sys.exit(2)

    if check_only:
        log("CHECK OK (manifest)")
        sys.exit(0)

    data_file = m.get("data_file") or "verses.jsonl"
    data_path = os.path.join(DATA_DIR, data_file)
    if not os.path.exists(data_path):
        log(f"STOP: missing data file {data_path}")
        log("Place verified PD verses there, then re-run.")
        sys.exit(3)

    db = SessionLocal()
    try:
        ensure_registry(db, m)
        stats = {"insert": 0, "update": 0, "skip": 0, "keep_existing": 0, "fail": 0}
        n = 0
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
                if action in ("insert", "update") and stats[action] % 200 == 0:
                    db.commit()
            except Exception as e:
                db.rollback()
                stats["fail"] += 1
                log(f"! row {n}: {e}")
        db.commit()
        log(f"DONE rows={n} {stats}")
        log(
            "UI attribution: "
            + (m.get("attribution_text") or "개역한글(1961) · Public Domain")
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
