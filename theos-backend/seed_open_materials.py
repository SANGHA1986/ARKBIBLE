"""공개 자료(주석·교부급 요약) 시드 — PD/공개 범위의 짧은 알려진 내용만.

이 파일은 레거시 시드용입니다. 신규 수집은 collect_open_materials.py 를 사용하세요.
"""
from __future__ import annotations

from database import SessionLocal
import models

MATERIALS = [
    {
        "title": "Institutes of the Christian Religion (공개 영역 요약)",
        "author": "John Calvin",
        "publisher": "Public Domain / CCEL",
        "source_url": "https://www.ccel.org/ccel/calvin/institutes.html",
        "source_type": "Book",
        "tradition": "개신교",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "academic_level": "A",
        "note": "칼뱅 《기독교 강요》는 공개 영역 번역본이 존재합니다. 아래는 창세기 1:1 관련으로 흔히 인용되는 요지 요약입니다.",
        "verse": ("창세기", 1, 1),
        "viewpoint": "개신교",
        "scholar_name": "존 칼뱅",
        "claim": "창조 서술은 하나님이 만물의 창조주이심을 선포한다.",
        "evidence": "창세기 1:1의 ‘태초에 하나님이…’ 구조는 피조 세계와 창조주를 구분하는 고백으로 읽힌다. (공개 영역 칼뱅 주석·강요 전통의 요약)",
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
        "note": "가톨릭 교회 교리서 — 공개 인용 범위의 요약 시드(전문 복제 아님).",
        "verse": ("창세기", 1, 1),
        "viewpoint": "가톨릭",
        "scholar_name": "가톨릭 교회 교리서 전통",
        "claim": "창조는 하느님의 자유로운 행위이며, 만물은 하느님께 의존한다.",
        "evidence": "창세기 서두는 창조 신앙의 기초 구절로 전통적으로 읽힌다.",
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
        "note": "원어 번호·영문 정의. 원어 연구 탭에서 조회.",
        "verse": None,
        "viewpoint": None,
        "scholar_name": None,
        "claim": None,
        "evidence": None,
    },
]


def main():
    db = SessionLocal()
    try:
        for m in MATERIALS:
            src = db.query(models.Source).filter_by(title=m["title"]).first()
            if not src:
                src = models.Source(
                    title=m["title"],
                    author=m["author"],
                    publisher=m["publisher"],
                    source_url=m.get("source_url"),
                    source_type=m.get("source_type") or "Book",
                    tags=m.get("tradition") or "",
                    description=m.get("note") or "",
                    copyright_owner=m["author"],
                    copyright_status=m["copyright_status"],
                    academic_level=m["academic_level"],
                    verification_status="공개시드",
                    original_location=f"seed://{m['title'][:40]}",
                )
                db.add(src)
                db.commit()
                db.refresh(src)
            elif not src.description and m.get("note"):
                src.description = m["note"]
                if not src.tags:
                    src.tags = m.get("tradition") or ""
                db.commit()

            if not getattr(src, "license", None):
                try:
                    lic = models.License(
                        source_id=src.id,
                        license_type=m["license_type"],
                        license_url=m.get("source_url", ""),
                        visibility_level="Public",
                        allow_ai_read=True,
                        allow_ai_summary=True,
                        allow_ai_embedding=True,
                        allow_ai_quote=True,
                        allow_free_user=True,
                        allow_paid_user=True,
                        allow_institution=True,
                        can_view_original=True,
                        can_download=False,
                    )
                    db.add(lic)
                    db.commit()
                except Exception:
                    db.rollback()

            if m["verse"] and m["claim"]:
                book_name, ch, vs = m["verse"]
                book = db.query(models.BibleBook).filter_by(name=book_name).first()
                if not book:
                    continue
                verse = (
                    db.query(models.Verse)
                    .filter_by(book_id=book.id, chapter_num=ch, verse_num=vs)
                    .first()
                )
                if not verse:
                    continue
                exists = (
                    db.query(models.Interpretation)
                    .filter_by(verse_id=verse.id, scholar_name=m["scholar_name"])
                    .first()
                )
                if not exists:
                    db.add(
                        models.Interpretation(
                            verse_id=verse.id,
                            source_id=src.id,
                            viewpoint=m["viewpoint"],
                            scholar_name=m["scholar_name"],
                            claim=m["claim"],
                            evidence=m["evidence"],
                        )
                    )
                    print("interp+", m["scholar_name"], book_name, f"{ch}:{vs}")
        db.commit()
        print("OK materials seed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
