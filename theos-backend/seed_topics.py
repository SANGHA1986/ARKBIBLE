"""시드 DB에 주제검색용 인물·사건 보강 (drop 없이 upsert)."""
from database import SessionLocal
import models

EXTRA_CHARS = [
    {"name": "블레셋", "original_name": "פְּלִשְׁתִּים", "era": "사사·왕국 시대", "genealogy_info": "가나안 해안 지역의 민족. 이스라엘과 반복적으로 충돌"},
    {"name": "골리앗", "original_name": "גָּלְיָת", "era": "통일왕국 시대", "genealogy_info": "가드 출신 블레셋 전사. 다윗과 대결"},
    {"name": "삼손", "original_name": "שִׁמְשׁוֹן", "era": "사사 시대", "genealogy_info": "블레셋과 싸운 이스라엘의 사사"},
]

EXTRA_EVENTS = [
    {
        "name": "블레셋의 침공",
        "period": "사사·왕국 시대",
        "historical_background": "블레셋이 이스라엘을 압박·침공한 일련의 충돌. 사사기·사무엘서에 기록",
    },
    {
        "name": "다윗과 골리앗",
        "period": "BC 11세기경",
        "historical_background": "소년 다윗이 블레셋 장수 골리앗을 이긴 사건 (사무엘상 17장)",
    },
]


def main():
    db = SessionLocal()
    try:
        for c in EXTRA_CHARS:
            row = db.query(models.Character).filter_by(name=c["name"]).first()
            if not row:
                db.add(models.Character(**c))
                print("char+", c["name"])
            else:
                print("char=", c["name"])
        db.commit()

        for e in EXTRA_EVENTS:
            row = db.query(models.Event).filter_by(name=e["name"]).first()
            if not row:
                db.add(models.Event(**e))
                print("event+", e["name"])
            else:
                print("event=", e["name"])
        db.commit()

        # 연결: 블레셋 침공 ↔ 블레셋/다윗/삼손, 다윗과 골리앗 ↔ 다윗/골리앗
        phil = db.query(models.Event).filter_by(name="블레셋의 침공").first()
        duel = db.query(models.Event).filter_by(name="다윗과 골리앗").first()
        char_p = db.query(models.Character).filter_by(name="블레셋").first()
        char_g = db.query(models.Character).filter_by(name="골리앗").first()
        char_s = db.query(models.Character).filter_by(name="삼손").first()
        char_d = db.query(models.Character).filter_by(name="다윗").first()

        if phil and char_p and char_p not in phil.characters:
            phil.characters.append(char_p)
        if phil and char_s and char_s not in phil.characters:
            phil.characters.append(char_s)
        if phil and char_d and char_d not in phil.characters:
            phil.characters.append(char_d)
        if duel and char_g and char_g not in duel.characters:
            duel.characters.append(char_g)
        if duel and char_d and char_d not in duel.characters:
            duel.characters.append(char_d)

        # 구절 연결 (시드에 있는 것만이라도)
        mat = (
            db.query(models.Verse)
            .join(models.BibleBook)
            .filter(models.BibleBook.name == "마태복음", models.Verse.chapter_num == 1, models.Verse.verse_num == 1)
            .first()
        )
        if duel and mat and mat not in duel.verses:
            # 다윗 언급 구절로라도 연결 (데모)
            if char_d and mat in char_d.verses:
                duel.verses.append(mat)

        db.commit()
        print("OK topic seed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
