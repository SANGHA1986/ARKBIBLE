"""
공개 논문·연구·개인자료 수집기 (성경 WEB 수집과 분리)

원칙:
  - Public Domain / CC BY / 사용자가 직접 허용한 개인 공개 자료만
  - 가톨릭·개신교·정교회·개인 모두 가능 (tradition 라벨 필수)
  - 유료 DB·저작권 저널 스크래핑 금지
  - 동일 title+author 또는 content_hash면 스킵 (중복 수집 안 함)

사용:
  python collect_open_materials.py
  python collect_open_materials.py --seed-only   # 내장 카탈로그만
  python collect_open_materials.py --local-only  # data_open_materials/ JSON만

개인 자료:
  theos-backend/data_open_materials/*.json 에 파일을 넣고 이 스크립트 실행
  (템플릿: data_open_materials/_template.example.json)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Optional

from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_open_materials")
os.makedirs(DATA_DIR, exist_ok=True)

# 내장 공개 카탈로그 — 짧은 요지/메타만 (전문 무단 복제 아님)
# license_type / tradition / source_url 필수
OPEN_CATALOG: list[dict[str, Any]] = [
    {
        "title": "Institutes of the Christian Religion (공개 영역 요약)",
        "author": "John Calvin",
        "publisher": "Public Domain",
        "source_url": "https://www.ccel.org/ccel/calvin/institutes.html",
        "source_type": "Book",
        "tradition": "개신교",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "academic_level": "A",
        "tags": "주석, 칼뱅, Calvin, 개신교, 기독교 강요, Institutes, 창세기",
        "note": "칼뱅 《기독교 강요》 — 공개 영역 번역본이 존재. 아래는 창세기 1:1 관련 요지.",
        "verse": ("창세기", 1, 1),
        "viewpoint": "개신교",
        "scholar_name": "존 칼뱅",
        "claim": "창조 서술은 하나님이 만물의 창조주이심을 선포한다.",
        "evidence": "창세기 1:1의 구조는 피조 세계와 창조주를 구분하는 고백으로 읽힌다. (PD 칼뱅 전통 요약)",
    },
    {
        "title": "Catechism of the Catholic Church (공개 요약 시드)",
        "author": "Catholic Church",
        "publisher": "ARK open seed",
        "source_url": "https://www.vatican.va/archive/ENG0015/_INDEX.HTM",
        "source_type": "Catechism",
        "tradition": "가톨릭",
        "copyright_status": "Public Domain summary seed",
        "license_type": "Public Domain summary",
        "academic_level": "A",
        "tags": "주석, 가톨릭, 교리서, CCC, Catechism, 창세기",
        "note": "가톨릭 교회 교리서 — 공개 인용 범위의 요약 시드(전문 복제 아님).",
        "verse": ("창세기", 1, 1),
        "viewpoint": "가톨릭",
        "scholar_name": "가톨릭 교회 교리서 전통",
        "claim": "창조는 하느님의 자유로운 행위이며, 만물은 하느님께 의존한다.",
        "evidence": "창세기 서두는 창조 신앙의 기초 구절로 전통적으로 읽힌다.",
    },
    {
        "title": "Ante-Nicene Fathers — sample notes (Public Domain)",
        "author": "Ante-Nicene Fathers (ed. Roberts/Donaldson)",
        "publisher": "CCEL / Public Domain",
        "source_url": "https://www.ccel.org/fathers.html",
        "source_type": "Patristic",
        "tradition": "정교회/초대교회",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "academic_level": "A",
        "tags": "주석, 교부, 정교회, Patristic, Fathers, 십자가, 수난",
        "note": "초대교부 영문 번역 다수 PD. 십자가·수난 관련 공개 메타 시드.",
        "verse": ("요한복음", 19, 30),
        "viewpoint": "정교회",
        "scholar_name": "초대교부 전통 (PD 요약)",
        "claim": "십자가에서의 ‘다 이루었다’는 구속 사역의 완성을 고백하는 전통으로 읽힌다.",
        "evidence": "공관복음·요한복음의 수난 서사와 교부 주석 전통(PD)에서 반복되는 요지.",
    },
    {
        "title": "Strong's Exhaustive Concordance (Public Domain)",
        "author": "James Strong",
        "publisher": "Public Domain",
        "source_url": "https://github.com/openscriptures/strongs",
        "source_type": "Lexicon",
        "tradition": "공통",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "academic_level": "B",
        "tags": "원어, Strong, 헬라어, 히브리어, concordance, lexicon",
        "note": "원어 번호·영문 정의. 상세 항목은 collect_open_lexicons.py 로 적재.",
        "verse": None,
        "viewpoint": None,
        "scholar_name": None,
        "claim": None,
        "evidence": None,
    },
    {
        "title": "STEP Bible Lexicons TBESG/TBESH (CC BY 4.0)",
        "author": "Tyndale House / STEP Bible",
        "publisher": "STEPBible.org",
        "source_url": "https://www.stepbible.org",
        "source_type": "Lexicon",
        "tradition": "공통",
        "copyright_status": "CC BY 4.0",
        "license_type": "CC BY 4.0",
        "academic_level": "A",
        "tags": "원어, STEP, TBESG, TBESH, 어원, etymology, CC BY",
        "note": "어원·확장 Strong. Attribution: STEP Bible (www.stepbible.org). 상세는 lexicon collector.",
        "verse": None,
        "viewpoint": None,
        "scholar_name": None,
        "claim": None,
        "evidence": None,
    },
    {
        "title": "Commentary on the Gospel of John — Chrysostom (PD summary seed)",
        "author": "John Chrysostom",
        "publisher": "CCEL / Public Domain",
        "source_url": "https://www.ccel.org/ccel/schaff/npnf114.html",
        "source_type": "Patristic",
        "tradition": "정교회",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "academic_level": "A",
        "tags": "주석, 요한복음, 크리소스톰, Chrysostom, 정교회, John, 사랑",
        "note": "요한 크리소스톰 요한복음 강해 — PD 영문 번역 존재. 요약 시드.",
        "verse": ("요한복음", 3, 16),
        "viewpoint": "정교회",
        "scholar_name": "요한 크리소스톰",
        "claim": "하나님이 세상을 이처럼 사랑하사 — 구원과 믿음의 초청으로 읽힌다.",
        "evidence": "요한복음 3:16 강해 전통(PD NPNF)의 요지 요약.",
    },
]


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("ascii", "replace"), flush=True)


def content_hash(m: dict) -> str:
    blob = "|".join(
        [
            str(m.get("title") or ""),
            str(m.get("author") or ""),
            str(m.get("claim") or ""),
            str(m.get("evidence") or ""),
            str(m.get("note") or ""),
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def ensure_license(db: Session, src: models.Source, m: dict) -> None:
    if getattr(src, "license", None):
        return
    lic = models.License(
        source_id=src.id,
        license_type=m.get("license_type") or "Public Domain",
        license_url=m.get("source_url") or "",
        commercial_use=m.get("license_type") in ("Public Domain", "CC BY 4.0", "CC0"),
        modification_allowed=True,
        redistribution_allowed=True,
        allow_ai_read=True,
        allow_ai_summary=True,
        allow_ai_embedding=True,
        allow_ai_quote=True,
        allow_free_user=True,
        allow_paid_user=True,
        allow_institution=True,
        can_view_original=True,
        can_download=False,
        visibility_level="Public",
    )
    db.add(lic)
    db.commit()


def upsert_source(db: Session, m: dict) -> tuple[models.Source, str]:
    title = (m.get("title") or "").strip()
    author = (m.get("author") or "").strip()
    if not title:
        raise ValueError("title required")

    existing = (
        db.query(models.Source)
        .filter(models.Source.title == title, models.Source.author == author)
        .first()
    )
    if existing:
        # 메타만 보강, 본문 중복 스킵
        changed = False
        for field, key in [
            ("publisher", "publisher"),
            ("source_url", "source_url"),
            ("source_type", "source_type"),
            ("copyright_status", "copyright_status"),
            ("academic_level", "academic_level"),
            ("tags", "tags"),
        ]:
            val = m.get(key)
            if val and getattr(existing, field, None) != val:
                setattr(existing, field, val)
                changed = True
        if m.get("note") and getattr(existing, "description", None) != m.get("note"):
            existing.description = m.get("note")
            changed = True
        if changed:
            db.commit()
            ensure_license(db, existing, m)
            return existing, "update"
        ensure_license(db, existing, m)
        return existing, "skip"

    src = models.Source(
        title=title,
        author=author or None,
        publisher=m.get("publisher"),
        source_url=m.get("source_url"),
        source_type=m.get("source_type") or "Article",
        original_location=f"open://{content_hash(m)[:12]}|{(m.get('tradition') or '공통')}",
        tags=m.get("tags"),
        description=m.get("note"),
        copyright_owner=author or m.get("publisher"),
        copyright_status=m.get("copyright_status") or "Public Domain",
        academic_level=m.get("academic_level") or "B",
        verification_status="공개수집",
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    ensure_license(db, src, m)
    return src, "insert"


def upsert_interpretation(db: Session, src: models.Source, m: dict) -> str:
    verse_ref = m.get("verse")
    claim = m.get("claim")
    if not verse_ref or not claim:
        return "no_interp"

    if isinstance(verse_ref, (list, tuple)) and len(verse_ref) >= 3:
        book_name, ch, vs = verse_ref[0], int(verse_ref[1]), int(verse_ref[2])
    else:
        return "bad_verse"

    book = db.query(models.BibleBook).filter_by(name=book_name).first()
    if not book:
        return "no_book"
    verse = (
        db.query(models.Verse)
        .filter_by(book_id=book.id, chapter_num=ch, verse_num=vs)
        .first()
    )
    if not verse:
        return "no_verse"

    scholar = m.get("scholar_name") or m.get("author")
    exists = (
        db.query(models.Interpretation)
        .filter_by(verse_id=verse.id, scholar_name=scholar, source_id=src.id)
        .first()
    )
    if exists:
        return "skip"

    db.add(
        models.Interpretation(
            verse_id=verse.id,
            source_id=src.id,
            viewpoint=m.get("viewpoint") or m.get("tradition") or "공통",
            scholar_name=scholar,
            claim=claim,
            evidence=m.get("evidence") or m.get("note"),
        )
    )
    db.commit()
    return "insert"


def load_local_json_files() -> list[dict]:
    items: list[dict] = []
    for name in sorted(os.listdir(DATA_DIR)):
        if name.startswith("_") or not name.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for row in data:
                    row["_file"] = name
                    items.append(row)
            elif isinstance(data, dict):
                data["_file"] = name
                items.append(data)
        except Exception as e:
            log(f"! bad json {name}: {e}")
    return items


def write_template() -> None:
    path = os.path.join(DATA_DIR, "_template.example.json")
    if os.path.exists(path):
        return
    example = {
        "title": "내 공개 연구 노트 제목",
        "author": "본인 이름 또는 필명",
        "publisher": "개인",
        "source_url": "https://example.com/my-open-note",
        "source_type": "Personal",
        "tradition": "개인",
        "copyright_status": "Personal Open",
        "license_type": "CC BY 4.0",
        "academic_level": "C",
        "tags": "주석, 개인, 요한복음, 사랑",
        "note": "직접 공개 허용한 개인 자료만 넣으세요. 타인 저작물·유료 논문 전문 금지.",
        "verse": ["요한복음", 3, 16],
        "viewpoint": "개인",
        "scholar_name": "본인",
        "claim": "이 구절에 대한 주장 한 문장",
        "evidence": "근거·인용·메모",
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(example, f, ensure_ascii=False, indent=2)
    log(f"[template] wrote {path}")


def ingest_list(db: Session, rows: list[dict], label: str) -> dict:
    from license_gate import assert_license_or_skip, looks_like_forbidden_ko_version

    stats = {"insert": 0, "update": 0, "skip": 0, "interp+": 0, "error": 0, "blocked": 0}
    for m in rows:
        try:
            lic = (m.get("license_type") or m.get("copyright_status") or "").strip()
            status = (m.get("copyright_status") or "").strip()
            # status가 BLOCK_STATUS 정확 일치일 때만 status 인자로 전달
            status_arg = status if status in ("Copyrighted", "None", "Unknown", "Unsafe", "") else None
            ok, reason = assert_license_or_skip(lic, status_arg)
            if not ok:
                log(f"! skip ({reason}): {m.get('title')} ({lic})")
                stats["blocked"] += 1
                continue
            blob = f"{m.get('title','')} {m.get('note','')} {m.get('claim','')}"
            if looks_like_forbidden_ko_version(blob):
                log(f"! skip (forbidden KO version marker): {m.get('title')}")
                stats["blocked"] += 1
                continue

            src, action = upsert_source(db, m)
            stats[action] = stats.get(action, 0) + 1
            if action == "insert":
                log(f"+ source [{m.get('tradition') or '?'}] {src.title}")
            interp = upsert_interpretation(db, src, m)
            if interp == "insert":
                stats["interp+"] += 1
                log(f"  + interp {m.get('scholar_name')} {m.get('verse')}")
        except Exception as e:
            db.rollback()
            stats["error"] += 1
            log(f"! {m.get('title')}: {e}")
    log(f"[{label}] {stats}")
    return stats


def main(seed_only: bool = False, local_only: bool = False):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    models.Base.metadata.create_all(bind=engine)
    write_template()
    db = SessionLocal()
    try:
        log("=== ARK Open Materials Collector ===")
        log("License gate: COLLECT_POLICY / license_gate (PD·CC0·CC BY only)")
        log("Bible WEB ≠ this script. Lexicon/etymology → collect_open_lexicons.py")
        if not local_only:
            ingest_list(db, OPEN_CATALOG, "catalog")
        if not seed_only:
            local = load_local_json_files()
            log(f"local json files: {len(local)}")
            if local:
                ingest_list(db, local, "local")
        n_src = db.query(models.Source).count()
        n_i = db.query(models.Interpretation).count()
        log(f"DONE sources={n_src} interpretations={n_i}")
        log(f"Drop personal open JSON in: {DATA_DIR}")
    finally:
        db.close()


if __name__ == "__main__":
    main(
        seed_only="--seed-only" in sys.argv,
        local_only="--local-only" in sys.argv,
    )
