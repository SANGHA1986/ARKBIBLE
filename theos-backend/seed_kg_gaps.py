"""
지식그래프 공백 채우기 — Location / Concept (기존 DB 유지, drop 없음)

사용:
  python seed_kg_gaps.py
"""
from __future__ import annotations

from sqlalchemy.orm import Session

import models
from database import SessionLocal


def verse_of(db: Session, book: str, ch: int, vs: int):
    b = db.query(models.BibleBook).filter_by(name=book).first()
    if not b:
        return None
    return (
        db.query(models.Verse)
        .filter_by(book_id=b.id, chapter_num=ch, verse_num=vs)
        .first()
    )


def upsert_location(db: Session, name: str, ancient: str = "") -> models.Location:
    row = db.query(models.Location).filter_by(name=name).first()
    if row:
        if ancient and not row.ancient_name:
            row.ancient_name = ancient
        return row
    row = models.Location(name=name, ancient_name=ancient or None)
    db.add(row)
    db.flush()
    return row


def upsert_concept(db: Session, name: str, definition: str) -> models.Concept:
    row = db.query(models.Concept).filter_by(name=name).first()
    if row:
        if definition and (not row.definition or len(row.definition) < 10):
            row.definition = definition
        return row
    row = models.Concept(name=name, definition=definition)
    db.add(row)
    db.flush()
    return row


def link_verse(entity, v):
    if v is None:
        return
    if v not in entity.verses:
        entity.verses.append(v)


def main():
    db = SessionLocal()
    try:
        print("=== seed_kg_gaps: locations + concepts ===")

        locations = [
            ("에덴", "עֵדֶן", [("창세기", 2, 8), ("창세기", 3, 23)]),
            ("예루살렘", "יְרוּשָׁלַ͏ִם", [("시편", 122, 3), ("누가복음", 24, 47), ("요한계시록", 21, 2)]),
            ("베들레헴", "בֵּית לֶחֶם", [("미가", 5, 2), ("마태복음", 2, 1)]),
            ("나사렛", "Ναζαρέτ", [("마태복음", 2, 23), ("누가복음", 4, 16)]),
            ("갈릴리", "הַגָּלִיל", [("마태복음", 4, 15), ("요한복음", 2, 1)]),
            ("사마리아", "שֹׁמְרוֹן", [("열왕기상", 16, 24), ("요한복음", 4, 4)]),
            ("다메섹", "דַּמֶּשֶׂק", [("열왕기상", 20, 34), ("사도행전", 9, 3)]),
            ("이집트", "מִצְרַיִם", [("출애굽기", 1, 1), ("마태복음", 2, 13)]),
            ("시내산", "סִינַי", [("출애굽기", 19, 20), ("출애굽기", 20, 1)]),
            ("바벨론", "בָּבֶל", [("열왕기하", 24, 10), ("다니엘", 1, 1)]),
            ("가버나움", "Καφαρναούμ", [("마태복음", 4, 13), ("마가복음", 1, 21)]),
            ("골고다", "Γολγοθᾶ", [("마태복음", 27, 33), ("요한복음", 19, 17)]),
            ("겟세마네", "Γεθσημανί", [("마태복음", 26, 36), ("마가복음", 14, 32)]),
            ("요단강", "הַיַּרְדֵּן", [("여호수아", 3, 17), ("마태복음", 3, 13)]),
            ("로마", "Ῥώμη", [("사도행전", 28, 16), ("로마서", 1, 7)]),
        ]

        loc_n = 0
        for name, ancient, refs in locations:
            loc = upsert_location(db, name, ancient)
            for book, ch, vs in refs:
                link_verse(loc, verse_of(db, book, ch, vs))
            loc_n += 1

        concepts = [
            ("삼위일체", "성부·성자·성령이 한 하나님이심을 고백하는 교리(정통 신앙 고백)."),
            ("이신칭의", "믿음으로 의롭다 하심을 받는다는 교리(로마서·갈라디아서 중심)."),
            ("성육신", "말씀이 육신이 되신 사건·교리(요한복음 1장)."),
            ("속죄", "그리스도의 십자가로 죄가 사하여짐(대속)."),
            ("부활", "그리스도의 부활과 성도의 부활 소망."),
            ("성화", "구원받은 자가 거룩하게 되어 가는 과정."),
            ("종말", "그리스도의 재림과 새 하늘·새 땅에 대한 소망."),
            ("교회", "그리스도의 몸으로서의 성도의 공동체."),
            ("세례", "그리스도와의 연합을 공적으로 고백하는 성례."),
            ("성찬", "주의 만찬 — 십자가를 기억하며 나누는 성례."),
            ("율법", "하나님의 뜻과 언약의 규범(모세 율법 포함)."),
            ("복음", "예수 그리스도의 십자가와 부활의 기쁜 소식."),
            ("은혜", "받을 자격이 없는 자에게 주시는 하나님의 호의."),
            ("믿음", "하나님과 그 약속을 신뢰함."),
            ("사랑", "하나님과 이웃을 향한 아가페적 사랑."),
            ("지혜", "하나님을 경외함에서 비롯되는 삶·지식."),
            ("예언", "하나님의 말씀을 대언함(선지·계시)."),
            ("왕국", "하나님의 통치 — 이미와 아직(already/not yet)."),
            ("성령", "삼위 중 성령 — 보혜사·능력·거룩하게 하심."),
            ("메시아", "기름 부음 받은 자 — 그리스도."),
        ]
        concept_refs = {
            "삼위일체": [("마태복음", 28, 19), ("고린도후서", 13, 13)],
            "이신칭의": [("로마서", 3, 28), ("갈라디아서", 2, 16)],
            "성육신": [("요한복음", 1, 14), ("빌립보서", 2, 6)],
            "속죄": [("이사야", 53, 5), ("로마서", 5, 8)],
            "부활": [("고린도전서", 15, 3), ("로마서", 6, 4)],
            "성화": [("로마서", 6, 19), ("데살로니가전서", 4, 3)],
            "종말": [("요한계시록", 21, 1), ("마태복음", 24, 30)],
            "교회": [("에베소서", 1, 22), ("마태복음", 16, 18)],
            "세례": [("마태복음", 28, 19), ("로마서", 6, 3)],
            "성찬": [("고린도전서", 11, 23), ("누가복음", 22, 19)],
            "율법": [("출애굽기", 20, 1), ("로마서", 3, 20)],
            "복음": [("로마서", 1, 16), ("마가복음", 1, 1)],
            "은혜": [("에베소서", 2, 8), ("요한복음", 1, 16)],
            "믿음": [("히브리서", 11, 1), ("로마서", 10, 17)],
            "사랑": [("고린도전서", 13, 13), ("요한일서", 4, 8)],
            "지혜": [("잠언", 9, 10), ("야고보서", 1, 5)],
            "예언": [("신명기", 18, 18), ("베드로후서", 1, 21)],
            "왕국": [("마태복음", 6, 33), ("마가복음", 1, 15)],
            "성령": [("요한복음", 14, 26), ("사도행전", 2, 4)],
            "메시아": [("이사야", 9, 6), ("요한복음", 1, 41)],
            "창조": [("창세기", 1, 1)],
            "언약": [("창세기", 9, 16), ("창세기", 17, 7)],
            "구원": [("요한복음", 3, 16), ("사도행전", 4, 12)],
        }

        con_n = 0
        for name, definition in concepts:
            cp = upsert_concept(db, name, definition)
            for book, ch, vs in concept_refs.get(name, []):
                link_verse(cp, verse_of(db, book, ch, vs))
            con_n += 1

        # 기존 3개에도 구절 연결 보강
        for name in ("창조", "언약", "구원"):
            cp = db.query(models.Concept).filter_by(name=name).first()
            if not cp:
                continue
            for book, ch, vs in concept_refs.get(name, []):
                link_verse(cp, verse_of(db, book, ch, vs))

        db.commit()
        print(f"locations upserted≈{loc_n} total={db.query(models.Location).count()}")
        print(f"concepts upserted≈{con_n}+base total={db.query(models.Concept).count()}")
        print("DONE")
    finally:
        db.close()


if __name__ == "__main__":
    main()
