import models
from database import engine, SessionLocal
from datetime import datetime

def seed_database():
    # Re-create tables
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        print("Starting Database Seeding...")

        # 1. 성경책 등록
        books = {
            "창세기": models.BibleBook(name="창세기", testament="구약"),
            "출애굽기": models.BibleBook(name="출애굽기", testament="구약"),
            "마태복음": models.BibleBook(name="마태복음", testament="신약"),
            "로마서": models.BibleBook(name="로마서", testament="신약")
        }
        db.add_all(books.values())
        db.commit()
        for b in books.values():
            db.refresh(b)

        # 2. 성경 구절 등록
        verses = {
            "gen1_1": models.Verse(
                book_id=books["창세기"].id, chapter_num=1, verse_num=1,
                text_ko="태초에 하나님이 천지를 창조하시니라.",
                text_original="בְּרֵאשִׁית בָּרָα אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ׃"
            ),
            "gen5_1": models.Verse(
                book_id=books["창세기"].id, chapter_num=5, verse_num=1,
                text_ko="이것은 아담의 계보를 적은 책이니라.",
                text_original="זֶה סֵפֶר תּוֹלְדֹת אָדָם בְּיוֹם בְּרֹא אֱלֹהִים אָדָם בִּדְמוּת אֱלֹהִים עָשָׂה אֹתוֹ׃"
            ),
            "exo3_14": models.Verse(
                book_id=books["출애굽기"].id, chapter_num=3, verse_num=14,
                text_ko="하나님이 모세에게 이르시되 나는 스스로 있는 자이니라.",
                text_original="וַיֹּאמֶר אֱלֹהִים אֶל־מֹשֶׁה אֶהְיֶה אֲשֶׁר אֶהְיֶה..."
            ),
            "mat1_1": models.Verse(
                book_id=books["마태복음"].id, chapter_num=1, verse_num=1,
                text_ko="아브라함과 다윗의 자손 예수 그리스도의 계보라.",
                text_original="Βίβλος γενέσεως Ἰησοῦ Χριστοῦ υἱοῦ Δαυὶδ υἱοῦ Ἀβραάμ."
            ),
            "rom8_1": models.Verse(
                book_id=books["로마서"].id, chapter_num=8, verse_num=1,
                text_ko="그러므로 이제 그리스도 예수 안에 있는 자에게는 결코 정죄함이 없나니",
                text_original="Οὐδὲν ἄρα νῦν κατάκριμα τοῖς ἐν Χριστῷ Ἰησοῦ..."
            )
        }
        db.add_all(verses.values())
        db.commit()
        for v in verses.values():
            db.refresh(v)

        # 3. 인물(Characters) 등록 및 족보(Genealogy) 연결
        # 계보: 아담 -> 셋 -> 노아 -> 아브라함 -> 다윗 -> 예수
        char_adam = models.Character(name="아담", original_name="אָדָם", era="창조 시대", genealogy_info="첫 인류")
        db.add(char_adam)
        db.commit()
        db.refresh(char_adam)

        char_seth = models.Character(name="셋", original_name="שֵׁת", era="창조 시대", genealogy_info="아담의 셋째 아들", father_id=char_adam.id)
        db.add(char_seth)
        db.commit()
        db.refresh(char_seth)

        char_noah = models.Character(name="노아", original_name="נֹחַ", era="홍수 시대", genealogy_info="방주를 지은 의인", father_id=char_seth.id)
        db.add(char_noah)
        db.commit()
        db.refresh(char_noah)

        char_abraham = models.Character(name="아브라함", original_name="אַבְרָהָם", era="족장 시대", genealogy_info="믿음의 조상", father_id=char_noah.id)
        db.add(char_abraham)
        db.commit()
        db.refresh(char_abraham)

        char_david = models.Character(name="다윗", original_name="דָּוִד", era="통일왕국 시대", genealogy_info="이스라엘의 2대 왕", father_id=char_abraham.id)
        db.add(char_david)
        db.commit()
        db.refresh(char_david)

        char_jesus = models.Character(name="예수", original_name="Ἰησοῦς", era="로마 시대", genealogy_info="메시아, 다윗의 자손", father_id=char_david.id)
        db.add(char_jesus)
        
        char_moses = models.Character(name="모세", original_name="מֹשֶׁה", era="출애굽 시대", genealogy_info="율법의 수여자")
        db.add(char_moses)
        
        db.commit()
        db.refresh(char_jesus)
        db.refresh(char_moses)

        # 인물 - 구절 연결
        char_adam.verses.append(verses["gen1_1"])
        char_adam.verses.append(verses["gen5_1"])
        char_seth.verses.append(verses["gen5_1"])
        char_moses.verses.append(verses["exo3_14"])
        char_abraham.verses.append(verses["mat1_1"])
        char_david.verses.append(verses["mat1_1"])
        char_jesus.verses.append(verses["mat1_1"])
        char_jesus.verses.append(verses["rom8_1"])
        db.commit()

        # 4. 사건(Events) 등록
        events = {
            "creation": models.Event(name="창조", period="태초", historical_background="우주와 생명의 기원에 대한 창세기 선포"),
            "flood": models.Event(name="노아 홍수", period="노아 시대", historical_background="타락한 인류 심판 및 방주 구원 사건"),
            "covenant": models.Event(name="아브라함 언약", period="BC 2000경", historical_background="하나님이 아브라함에게 복과 자손을 약속하신 사건"),
            "exodus": models.Event(name="출애굽", period="BC 1446 혹은 1290경", historical_background="이스라엘 민족의 이집트 탈출 및 해방 사건"),
            "kingdom": models.Event(name="다윗 왕국", period="BC 1010-970", historical_background="통일 왕국의 번영 및 성전 건축 준비"),
            "birth": models.Event(name="예수 탄생", period="BC 4경", historical_background="헤롯 왕 시대 베들레헴 성육신 사건"),
            "cross": models.Event(name="십자가", period="AD 30 혹은 33경", historical_background="예수 그리스도의 인류 죄 대속 죽음"),
            "resurrection": models.Event(name="부활", period="AD 30 혹은 33경", historical_background="사망 권세를 깨뜨리고 삼일 만에 살아나심")
        }
        db.add_all(events.values())
        db.commit()
        for ev in events.values():
            db.refresh(ev)

        # 사건 - 구절 - 인물 연결
        events["creation"].verses.append(verses["gen1_1"])
        events["creation"].characters.append(char_adam)
        
        events["exodus"].verses.append(verses["exo3_14"])
        events["exodus"].characters.append(char_moses)
        
        events["kingdom"].verses.append(verses["mat1_1"])
        events["kingdom"].characters.append(char_david)
        
        events["birth"].verses.append(verses["mat1_1"])
        events["birth"].characters.append(char_jesus)
        
        events["cross"].verses.append(verses["rom8_1"])
        events["cross"].characters.append(char_jesus)
        
        db.commit()

        # 5. 개념(Concepts) 및 교리(Doctrines) 등록
        concepts = {
            "creation": models.Concept(name="창조", definition="우주와 생명이 신성한 절대자에 의해 존재하게 된 행위"),
            "covenant": models.Concept(name="언약", definition="하나님과 그의 백성 사이에 맺어진 구속력 있는 약속"),
            "salvation": models.Concept(name="구원", definition="죄와 죽음으로부터의 해방과 영원한 생명의 부여")
        }
        db.add_all(concepts.values())
        
        doctrines = {
            "trinity": models.Doctrine(name="삼위일체", description="성부, 성자, 성령은 한 본질 안에서 세 위격으로 존재하심"),
            "incarnation": models.Doctrine(name="성육신", description="하나님의 영원한 말씀이 예수 그리스도로 육신이 되심")
        }
        db.add_all(doctrines.values())
        db.commit()
        
        for c in concepts.values():
            db.refresh(c)
        for d in doctrines.values():
            db.refresh(d)
            
        concepts["creation"].doctrines.append(doctrines["incarnation"]) # 연관 연결
        concepts["creation"].verses.append(verses["gen1_1"])
        db.commit()

        # 6. 원어 정보(LanguageData) 등록
        lang_bara = models.LanguageData(word="바라(בָּרָא)", language_type="히브리어", transliteration="Bara", morphology="동사 (Qal perfect 3rd person masculine singular)")
        lang_bara.verses.append(verses["gen1_1"])
        db.add(lang_bara)
        db.commit()

        # 7. 출처 및 라이선스 등록 (오픈 레이어용)
        # 유료/저작권 자료는 collect_open_materials.py / paid_providers.py 경로로만 관리.
        src_calvin = models.Source(
            title="Institutes of the Christian Religion (공개 영역 요약)",
            author="John Calvin",
            publisher="Public Domain / CCEL",
            source_url="https://www.ccel.org/ccel/calvin/institutes.html",
            source_type="Book",
            copyright_owner="Public Domain",
            copyright_status="Public Domain",
            publication_year=1559,
            academic_level="A",
            verification_status="검증됨"
        )
        db.add(src_calvin)
        db.commit()
        db.refresh(src_calvin)

        lic_calvin = models.License(
            source_id=src_calvin.id, license_type="Public Domain", license_url="https://www.ccel.org/ccel/calvin/institutes.html",
            commercial_use=True, modification_allowed=True, redistribution_allowed=True,
            allow_ai_read=True, allow_ai_summary=True, allow_ai_embedding=True, allow_ai_quote=True,
            allow_free_user=True, allow_paid_user=True, allow_institution=True,
            can_view_original=True, can_download=False
        )
        db.add(lic_calvin)
        db.commit()

        # 8. 해석(Interpretations) 등록
        interp1 = models.Interpretation(
            viewpoint="개신교", claim="무로부터의 창조 (Creatio ex nihilo) 선언",
            evidence="하나님께서 아무런 재료 없이 우주를 창조하셨음을 선언한다. 우주의 영원성을 배격하고 창조주의 주권을 증명한다.",
            scholar_name="장 칼뱅", verse_id=verses["gen1_1"].id, source_id=src_calvin.id
        )
        db.add(interp1)
        db.commit()

        # 9. 테스트용 회원 등록 (Free, Paid, Institution)
        user_free = models.User(username="free_user", tier="Free")
        user_paid = models.User(username="paid_user", tier="Paid")
        user_inst = models.User(username="inst_user", tier="Institution")
        db.add_all([user_free, user_paid, user_inst])
        db.commit()

        print("Database Seed completed successfully!")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
