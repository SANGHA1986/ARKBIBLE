"""성경 장/구절 우선 통합 검색."""
from __future__ import annotations

import re
from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

import models
import membership
from rag_engine import RagEngine
from book_i18n import book_display, char_display, verse_ref_display, normalize_lang, KO_TO_EN_CHAR
from search_translate import expand_query_for_search
from license_gate import is_license_allowed

_rag = RagEngine()

BOOK_MAP = {
    "genesis": "창세기",
    "exodus": "출애굽기",
    "leviticus": "레위기",
    "numbers": "민수기",
    "deuteronomy": "신명기",
    "joshua": "여호수아",
    "judges": "사사기",
    "ruth": "룻기",
    "1samuel": "사무엘상",
    "2samuel": "사무엘하",
    "1kings": "열왕기상",
    "2kings": "열왕기하",
    "psalm": "시편",
    "isaiah": "이사야",
    "matthew": "마태복음",
    "mark": "마가복음",
    "luke": "누가복음",
    "john": "요한복음",
    "romans": "로마서",
    "1corinthians": "고린도전서",
    "2corinthians": "고린도후서",
    "galatians": "갈라디아서",
    "ephesians": "에베소서",
    "philippians": "빌립보서",
    "colossians": "골로새서",
    "hebrews": "히브리서",
    "revelation": "요한계시록",
    "acts": "사도행전",
    "1chronicles": "역대상",
    "2chronicles": "역대하",
    "ezra": "에스라",
    "nehemiah": "느헤미야",
    "esther": "에스더",
    "job": "욥기",
    "ecclesiastes": "전도서",
    "songofsolomon": "아가",
    "lamentations": "예레미야애가",
    "ezekiel": "에스겔",
    "daniel": "다니엘",
    "hosea": "호세아",
    "joel": "요엘",
    "amos": "아모스",
    "obadiah": "오바댜",
    "jonah": "요나",
    "micah": "미가",
    "nahum": "나훔",
    "habakkuk": "하박국",
    "zephaniah": "스바냐",
    "haggai": "학개",
    "zechariah": "스가랴",
    "malachi": "말라기",
    "1thessalonians": "데살로니가전서",
    "2thessalonians": "데살로니가후서",
    "1timothy": "디모데전서",
    "2timothy": "디모데후서",
    "titus": "디도서",
    "philemon": "빌레몬서",
    "james": "야고보서",
    "1peter": "베드로전서",
    "2peter": "베드로후서",
    "1john": "요한일서",
    "2john": "요한이서",
    "3john": "요한삼서",
    "jude": "유다서",
    "2samuel": "사무엘하",
    "proverbs": "잠언",
    "jeremiah": "예레미야",
    "창": "창세기",
    "출": "출애굽기",
    "마": "마태복음",
    "요": "요한복음",
    "롬": "로마서",
    "삼상": "사무엘상",
}
for _bn in list(set(BOOK_MAP.values())):
    BOOK_MAP[_bn] = _bn


def resolve_book_name(raw: str):
    if not raw:
        return None
    s = raw.strip()
    if s in BOOK_MAP:
        return BOOK_MAP[s]
    return BOOK_MAP.get(s.lower().replace(" ", ""))


# OSIS slug -> 한글 책명 (OpenChristianData / OpenBible 기준)
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
KO_TO_OSIS = {v: k for k, v in OSIS_TO_KO.items()}


def _fetch_commentaries(db: Session, book_row, chapter: int, verse: int = None, limit: int = 6):
    """해당 구절/장에 달린 공개 주석을 가져온다."""
    out = []
    q = (
        db.query(models.Commentary, models.Source)
        .join(models.Source, models.Source.id == models.Commentary.source_id)
        .filter(
            models.Commentary.book_id == book_row.id,
            models.Commentary.chapter_num == chapter,
        )
    )
    if verse is not None:
        # verse_start가 null(장 전체)이거나 verse 구간이 겹치는 것
        q = q.filter(
            (models.Commentary.verse_start.is_(None))
            | ((models.Commentary.verse_start <= verse) & (models.Commentary.verse_end >= verse))
        )
        # 구절 특화 주석을 장 개요보다 먼저
        q = q.order_by(
            models.Commentary.verse_start.is_(None),
            models.Commentary.verse_start.asc(),
        )
    else:
        q = q.order_by(models.Commentary.verse_start.asc().nullsfirst())
    rows = q.limit(limit).all()
    for c, src in rows:
        lic = getattr(src, "license", None)
        if lic and not getattr(lic, "allow_ai_read", True):
            continue
        author = (src.author or "").strip() or None
        title = (src.title or "").strip() or "Commentary"
        # UI/요약용 짧은 출처 라벨 (본문은 자르지 않음 · 과대 응답만 상한)
        short_cite = author or title
        if author and title and author.lower() not in title.lower():
            short_cite = f"{author} · {title}"
        if len(short_cite) > 72:
            short_cite = short_cite[:69] + "…"
        text = (c.commentary_text or "").strip()
        if len(text) > 12000:
            text = text[:12000]
        out.append({
            "author": author or title,
            "title": title,
            "short_cite": short_cite,
            "passage_ref": c.passage_ref,
            "license": src.copyright_status or (lic.license_type if lic else None) or "Public Domain",
            "text": text,
        })
    return out


def _fetch_cross_refs(db: Session, book_row, chapter: int, verse: int, limit: int = 12, lang: str = "KO"):
    """해당 구절에서 출발하는 연관 구절을 가져온다 (OpenBible CC BY)."""
    out = []
    rows = (
        db.query(models.CrossReference, models.BibleBook)
        .join(models.BibleBook, models.BibleBook.id == models.CrossReference.to_book_id)
        .filter(
            models.CrossReference.from_book_id == book_row.id,
            models.CrossReference.from_chapter == chapter,
            models.CrossReference.from_verse == verse,
        )
        .order_by(models.CrossReference.votes.desc())
        .limit(limit)
        .all()
    )
    for cr, to_book in rows:
        vs, ve = cr.to_verse_start, cr.to_verse_end or cr.to_verse_start
        b = book_display(to_book.name, lang)
        if ve != vs:
            ref = f"{b} {cr.to_chapter}:{vs}-{ve}"
        else:
            ref = f"{b} {cr.to_chapter}:{vs}"
        out.append({"reference": ref, "votes": cr.votes})
    return out


def _localized_messages(lang: str):
    en = normalize_lang(lang) == "EN"
    if en:
        return {
            "verse_missing": lambda b, c, v: f"{book_display(b, 'EN')} {c}:{v} is not in the DB yet.",
            "chapter_missing": lambda b, c: f"{book_display(b, 'EN')} chapter {c} is not in the DB yet.",
            "reason_char": lambda n: f"Verse linked to {char_display(n, 'EN')}",
            "reason_event": lambda n: f"Verse linked to event '{n}'",
            "reason_loc": lambda n: f"Verse linked to place {n}",
            "reason_concept": lambda n: f"Verse linked to concept {n}",
            "reason_keyword": "Matches search keywords in text",
            "reason_similar": "Similar to search keywords",
            "no_hits": (
                "No related records found. Ask the AI assistant — "
                "it answers from registered DB content only and notes gaps as planned."
            ),
            "partial_hits": (
                "Found related people/events, but natural-language questions need more links. "
                "Select items on the left or ask the AI assistant."
            ),
        }
    return {
        "verse_missing": lambda b, c, v: f"{b} {c}:{v} 본문이 아직 DB에 없습니다.",
        "chapter_missing": lambda b, c: f"{b} {c}장 본문이 아직 DB에 없습니다.",
        "reason_char": lambda n: f"{n}와(과) 관련된 구절",
        "reason_event": lambda n: f"'{n}' 사건 관련 구절",
        "reason_loc": lambda n: f"{n} 장소 관련 구절",
        "reason_concept": lambda n: f"{n} 개념 관련 구절",
        "reason_keyword": "검색 키워드와 본문이 일치",
        "reason_similar": "검색 키워드와 유사한 본문",
        "no_hits": (
            "등록된 연관 자료가 없습니다. AI 어시스턴트에게 문의하세요 — "
            "DB에 있는 기록만 근거로 답하며, 없는 내용은 추가 수집 예정임을 안내합니다."
        ),
        "partial_hits": (
            "연관 인물/사건은 찾았으나, 질문 형태의 추가 구절은 DB 연결만으로 부족합니다. "
            "좌측 인물/구절을 눌러 상세를 보거나, AI 어시스턴트에게 질문 형태로 물어보세요."
        ),
    }


def _verse_payload(v, lang: str, reason: str = ""):
    from book_i18n import normalize_lang

    book_ko = v.book.name
    ko = (v.text_ko or "").strip()
    ko_is_placeholder = not ko or ko.startswith("[공개 한국어")
    en = normalize_lang(lang) == "EN"
    if en:
        translation_en = "World English Bible (WEB) · Public Domain" if v.text_en else None
        translation_ko = (
            None
            if ko_is_placeholder
            else "Korean Revised Hangul (1961) · Public Domain"
        )
    else:
        translation_en = "영문 WEB · 퍼블릭 도메인" if v.text_en else None
        translation_ko = (
            None
            if ko_is_placeholder
            else "개역한글(1961) · 퍼블릭 도메인(등록분)"
        )
    return {
        "reference": verse_ref_display(book_ko, v.chapter_num, v.verse_num, lang),
        "book": book_display(book_ko, lang),
        "book_ko": book_ko,
        "chapter": v.chapter_num,
        "verse": v.verse_num,
        "text_ko": v.text_ko,
        "text_en": v.text_en,
        "text_original": v.text_original,
        "translation_en": translation_en,
        "translation_ko": translation_ko,
        "reason": reason,
    }


def _clean_display_title(title: str, lang: str) -> str:
    """영문 제목에 붙은 한글 괄호 표기 제거 — 언어 혼류 방지."""
    from book_i18n import normalize_lang

    t = (title or "").strip()
    if not t:
        return t
    # 제목 속 한글 부가 표기 제거
    t = re.sub(r"\s*[\(（][^)）]*공개[^)）]*[\)）]", "", t)
    t = re.sub(r"\s*[\(（][^)）]*요약[^)）]*[\)）]", "", t)
    t = re.sub(r"\s*[\(（][^)）]*시드[^)）]*[\)）]", "", t)
    t = re.sub(r"\s*—\s*공개[^\n]*$", "", t)
    if normalize_lang(lang) == "EN":
        # 영문 UI에서는 제목에 한글이 남아 있으면 제거된 영문만
        if re.search(r"[가-힣]", t) and re.search(r"[A-Za-z]", t):
            t = re.sub(r"[가-힣]+", " ", t)
            t = re.sub(r"\s{2,}", " ", t).strip(" -·|/")
    return t.strip() or (title or "").strip()


def _material_payload(src, lang: str = "KO") -> dict:
    lic = getattr(src, "license", None)
    license_label = (
        (lic.license_type if lic else None)
        or src.copyright_status
        or ""
    )
    claim = None
    evidence = None
    viewpoint = None
    try:
        interps = list(src.interpretations or [])
        if interps:
            claim = interps[0].claim
            evidence = interps[0].evidence
            viewpoint = interps[0].viewpoint
    except Exception:
        pass
    return {
        "kind": "source",
        "title": _clean_display_title(src.title or "", lang),
        "author": src.author,
        "type": src.source_type or "Book",
        "source_type": src.source_type or "Book",
        "license": license_label,
        "copyright_status": src.copyright_status,
        "academic_level": src.academic_level,
        "publication_year": getattr(src, "publication_year", None),
        "publisher": getattr(src, "publisher", None),
        "source_url": src.source_url,
        "attribution": (src.description or "")[:400] if src.description else "",
        "description": src.description,
        "claim": claim,
        "evidence": evidence,
        "viewpoint": viewpoint,
    }


def _source_license_ok(src) -> bool:
    """검색 노출용 — 차단 상태·AI 읽기 금지면 False."""
    lic = getattr(src, "license", None)
    if lic and not getattr(lic, "allow_ai_read", True):
        return False
    status = (src.copyright_status or "").strip().lower()
    if status in ("copyrighted", "unsafe", "none", "unknown"):
        return False
    # 빈 status여도 License 행의 license_type이 허용이면 OK
    if not status:
        if lic and is_license_allowed(getattr(lic, "license_type", None)):
            return True
        return False
    # CC BY / PD / CC0 등은 통과
    if is_license_allowed(src.copyright_status) or is_license_allowed(
        getattr(lic, "license_type", None) if lic else None
    ):
        return True
    # 레거시 summary seed 등
    if "public domain" in status or status.startswith("cc"):
        return True
    return False


def _wants_papers(query: str) -> bool:
    q = (query or "").lower().strip()
    keys = (
        "논문", "학술지", "학술", "저널", "오픈액세스",
        "paper", "papers", "journal", "journals", "article", "openalex", "oa ",
        "theology", "theological", "biblical", "exegesis",
        "hermeneut", "신학", "성서학",
    )
    return any(k in q for k in keys)


def _category_browse_mode(query: str) -> Optional[str]:
    """홈 카테고리 단어 → 목록 브라우즈 모드."""
    q = (query or "").strip().lower()
    mapping = {
        "인물": "characters",
        "people": "characters",
        "인물목록": "characters",
        "사건": "events",
        "events": "events",
        "사건목록": "events",
        "장소": "locations",
        "places": "locations",
        "교리": "concepts",
        "doctrine": "concepts",
        "개념": "concepts",
        "성경": "bible_hub",
        "bible": "bible_hub",
        "교부": "fathers",
        "fathers": "fathers",
        "종교개혁": "reformation",
        "reformation": "reformation",
        "논문": "papers",
        "학술지": "papers",
        "papers": "papers",
        "paper": "papers",
        "journals": "papers",
        "주석": "commentary",
        "commentary": "commentary",
        "자료": "sources",
        "sources": "sources",
        "materials": "sources",
        "등록자료": "sources",
    }
    return mapping.get(q)


def _wants_materials_catalog(query: str) -> bool:
    q = (query or "").lower()
    keys = (
        "주석", "자료", "서적", "칼뱅", "calvin", "교리서", "원어",
        "commentary", "institutes", "교부", "자료실",
    )
    return any(k in q for k in keys) or _wants_papers(query)


def _material_search_terms(query: str, x_terms, tokens) -> list[str]:
    """논문/자료 매칭용 검색어 — 한글 의도 → 영문 태그 확장."""
    terms = []
    seen = set()
    q = (query or "").strip()
    for t in [q] + list(x_terms or []) + list(tokens or []):
        k = (t or "").strip().lower()
        if k and k not in seen and len(k) >= 2:
            seen.add(k)
            terms.append(k)
    # 한글 의도어 → DB tags/영문 필드에 있는 키워드
    expansions = {
        "논문": ["paper", "journal", "journalarticle", "openalex", "oa", "article"],
        "학술지": ["journal", "journalarticle", "paper", "openalex"],
        "학술": ["journal", "paper", "theology", "academic"],
        "저널": ["journal", "journalarticle"],
        "신학": ["theology", "theological", "biblical"],
        "성서학": ["biblical", "bible", "exegesis"],
        "주석": ["commentary", "henry", "clarke", "gill"],
        "칼뱅": ["calvin", "institutes"],
        "가톨릭": ["catholic", "가톨릭"],
        "천주교": ["catholic", "가톨릭"],
        "개신교": ["protestant", "개신교"],
        "기독교": ["christian", "protestant", "theology"],
    }
    for ko, ens in expansions.items():
        if ko in (query or ""):
            for e in ens:
                if e not in seen:
                    seen.add(e)
                    terms.append(e)
    return terms[:40]


def _match_source_blob(src, terms: list[str], query: str) -> bool:
    blob = (
        f"{src.title or ''} {src.author or ''} {src.source_type or ''} "
        f"{src.tags or ''} {src.description or ''} {src.publisher or ''}"
    ).lower()
    q = (query or "").lower()
    if q and q in blob:
        return True
    if (src.source_type or "") == "JournalArticle" and _wants_papers(query):
        # 「논문」「학술지」단독 → 등록 OA 논문 목록
        if query.strip() in ("논문", "학술지", "학술", "paper", "journal", "journals"):
            return True
    for t in terms:
        if len(t) >= 2 and t in blob:
            return True
    return False


def _collect_materials(db, query: str, x_terms, tokens, limit: int = 24, lang: str = "KO") -> list:
    terms = _material_search_terms(query, x_terms, tokens)
    paper_first = _wants_papers(query)
    if paper_first:
        limit = max(limit, 60)  # 테스트: 논문 노출 (페이지네이션으로 처리)
    out = []
    have = set()

    qsrc = db.query(models.Source)
    if paper_first:
        rows = (
            qsrc.filter(models.Source.source_type == "JournalArticle").all()
            + qsrc.filter(
                (models.Source.source_type.is_(None))
                | (models.Source.source_type != "JournalArticle")
            ).all()
        )
    else:
        rows = qsrc.all()

    for src in rows:
        if src.title in have:
            continue
        if not _source_license_ok(src):
            continue
        if not _match_source_blob(src, terms, query):
            continue
        out.append(_material_payload(src, lang=lang))
        have.add(src.title)
        if len(out) >= limit:
            break
    return out


def _fill_category_browse(db, results: dict, mode: str, lang: str, msg: dict) -> None:
    """홈 카테고리 클릭 시 DB 목록을 직접 채움."""
    from book_i18n import char_display
    from kg_i18n import (
        char_info,
        concept_definition,
        concept_name,
        era_text,
        event_background,
        event_name,
        location_name,
    )

    if mode == "characters":
        for char in db.query(models.Character).order_by(models.Character.id).limit(200).all():
            results["characters"].append(
                {
                    "name": char_display(char.name, lang),
                    "original_name": char.original_name,
                    "era": era_text(char.era, lang),
                    "info": char_info(char.name, char.genealogy_info, lang),
                    "verses": [],
                    "events": [],
                }
            )
        if not results["characters"]:
            results["message"] = (
                "등록된 인물이 아직 없습니다." if lang == "KO" else "No characters registered yet."
            )
    elif mode == "events":
        for ev in db.query(models.Event).order_by(models.Event.id).limit(200).all():
            results["events"].append(
                {
                    "name": event_name(ev.name, lang),
                    "period": era_text(ev.period, lang),
                    "background": event_background(ev.name, ev.historical_background, lang),
                    "characters": [],
                    "locations": [],
                    "verses": [],
                }
            )
        if not results["events"]:
            results["message"] = (
                "등록된 사건이 아직 없습니다." if lang == "KO" else "No events registered yet."
            )
    elif mode == "locations":
        for loc in db.query(models.Location).order_by(models.Location.id).limit(200).all():
            results["locations"].append(
                {
                    "name": location_name(loc.name, lang),
                    "ancient_name": loc.ancient_name,
                    "verses": [],
                    "events": [],
                }
            )
        if not results["locations"]:
            results["message"] = (
                "등록된 장소가 아직 없습니다. (추가 수집 예정)"
                if lang == "KO"
                else "No places registered yet (planned)."
            )
    elif mode == "concepts":
        seen = set()
        for cp in db.query(models.Concept).order_by(models.Concept.id).limit(200).all():
            seen.add(cp.name)
            results["concepts"].append(
                {
                    "name": concept_name(cp.name, lang),
                    "definition": concept_definition(cp.name, cp.definition, lang),
                    "verses": [],
                }
            )
        for d in db.query(models.Doctrine).order_by(models.Doctrine.id).limit(100).all():
            if d.name in seen:
                continue
            results["concepts"].append(
                {
                    "name": concept_name(d.name, lang),
                    "definition": concept_definition(d.name, d.description, lang),
                    "verses": [],
                }
            )
        if not results["concepts"]:
            results["message"] = (
                "등록된 교리/개념이 아직 적습니다." if lang == "KO" else "Few doctrine concepts yet."
            )
    elif mode == "papers":
        out = []
        for src in (
            db.query(models.Source)
            .filter(models.Source.source_type == "JournalArticle")
            .order_by(models.Source.id.desc())
            .limit(80)
            .all()
        ):
            if not _source_license_ok(src):
                continue
            out.append(_material_payload(src, lang=lang))
            if len(out) >= 60:
                break
        results["materials"] = out
        results["message"] = (
            "공개 학술 논문(초록·메타) 목록입니다. 성경 본문·주석과 별개입니다."
            if lang == "KO"
            else "Open-access journal papers (abstract/meta). Separate from Bible text and commentaries."
        )
        if not results["materials"]:
            results["message"] = (
                "등록된 OA 논문이 없습니다." if lang == "KO" else "No OA papers registered."
            )
    elif mode == "commentary":
        out = []
        for src in db.query(models.Source).order_by(models.Source.id).all():
            if not _source_license_ok(src):
                continue
            st = (src.source_type or "").strip().lower()
            if st == "journalarticle":
                continue
            blob = f"{src.title or ''} {src.tags or ''} {src.description or ''} {src.author or ''}".lower()
            if st in ("commentary", "book", "patristic", "catechism") or any(
                k in blob
                for k in (
                    "commentary",
                    "주석",
                    "henry",
                    "clarke",
                    "gill",
                    "jamieson",
                    "tyndale",
                    "wesley",
                    "keil",
                    "institutes",
                )
            ):
                out.append(_material_payload(src, lang=lang))
            if len(out) >= 40:
                break
        results["materials"] = out
        results["message"] = (
            "주석『작품/책』목록입니다(전체 구절 해설 3만건이 아님). 구절별 주석은 구절을 열면 아래에 표시됩니다. 예: 창세기 1:1"
            if lang == "KO"
            else "List of commentary works/books (not 30k verse notes). Open a verse to see its notes. e.g. Genesis 1:1"
        )
        if not results["materials"]:
            results["message"] = (
                "등록된 주석 자료가 없습니다." if lang == "KO" else "No commentaries registered."
            )
    elif mode == "sources":
        out = []
        for src in db.query(models.Source).order_by(models.Source.id).limit(120).all():
            if not _source_license_ok(src):
                continue
            out.append(_material_payload(src, lang=lang))
            if len(out) >= 99:
                break
        results["materials"] = out
        results["message"] = (
            "등록 자료 전체 목록입니다. 논문·주석 작품·요약 시드가 포함됩니다. 「논문」「주석」버튼은 각각 해당 종류만 보여줍니다."
            if lang == "KO"
            else "All registered sources (papers, commentary works, summary seeds). Use Papers/Commentary for filtered lists."
        )
        if not results["materials"]:
            results["message"] = (
                "등록된 자료가 없습니다." if lang == "KO" else "No sources registered."
            )
    elif mode == "fathers":
        father_names = ("어거스틴", "아타나시우스", "크리소스톰", "제롬", "오리겐", "터툴리아누스")
        for ch in (
            db.query(models.Character)
            .filter(models.Character.name.in_(father_names))
            .all()
        ):
            results["characters"].append(
                {
                    "name": char_display(ch.name, lang),
                    "original_name": ch.original_name,
                    "era": era_text(ch.era, lang),
                    "info": char_info(ch.name, ch.genealogy_info, lang),
                    "verses": [],
                }
            )
        results["materials"] = _collect_materials(
            db, "교부", ["교부", "patristic", "fathers", "chrysostom", "augustine"], [], limit=40, lang=lang
        )
    elif mode == "reformation":
        reform_names = ("루터", "칼뱅", "츠빙글리", "멜란히톤", "녹스")
        for ch in (
            db.query(models.Character)
            .filter(models.Character.name.in_(reform_names))
            .all()
        ):
            results["characters"].append(
                {
                    "name": char_display(ch.name, lang),
                    "original_name": ch.original_name,
                    "era": era_text(ch.era, lang),
                    "info": char_info(ch.name, ch.genealogy_info, lang),
                    "verses": [],
                }
            )
        for ev in (
            db.query(models.Event)
            .filter(models.Event.name.contains("종교개혁"))
            .limit(5)
            .all()
        ):
            results["events"].append(
                {
                    "name": event_name(ev.name, lang),
                    "period": era_text(ev.period, lang),
                    "background": event_background(ev.name, ev.historical_background, lang),
                    "verses": [],
                }
            )
        results["materials"] = _collect_materials(
            db, "칼뱅", ["calvin", "institutes", "reformation", "종교개혁", "luther"], [], limit=40, lang=lang
        )
    elif mode == "bible_hub":
        # 대표 구절만 — 성경 카테고리 입구
        for book_name, ch, vs in (
            ("창세기", 1, 1),
            ("출애굽기", 20, 1),
            ("시편", 23, 1),
            ("이사야", 53, 5),
            ("마태복음", 5, 3),
            ("요한복음", 3, 16),
            ("로마서", 8, 28),
            ("요한계시록", 21, 1),
        ):
            book = db.query(models.BibleBook).filter_by(name=book_name).first()
            if not book:
                continue
            v = (
                db.query(models.Verse)
                .filter_by(book_id=book.id, chapter_num=ch, verse_num=vs)
                .first()
            )
            if v:
                results["verses"].append(_verse_payload(v, lang, msg.get("reason_keyword", "")))
        results["message"] = (
            "성경 본문 입구입니다. 구절·장으로 검색하세요. 예: 창세기 1:1, 요한복음 3장"
            if lang == "KO"
            else "Bible text hub. Search by verse/chapter, e.g. Genesis 1:1"
        )


def unified_search(q: str, username: str = "free_user", db: Session = None, lang: str = "KO"):
    """장/구절 본문 우선. 성경 검색 시 사건 오탐 방지."""
    if db is None:
        raise HTTPException(status_code=500, detail="db required")
    lang = normalize_lang(lang)
    msg = _localized_messages(lang)
    user = membership.get_or_create_user(db, username)
    membership.require_access(db, user)

    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="q required")

    verse_ref_seen: set[tuple[int, int, int]] = set()
    results = {
        "query": query,
        "mode": "topic",
        "verse": None,
        "chapter": None,
        "verses": [],
        "characters": [],
        "events": [],
        "locations": [],
        "concepts": [],
        "strong": [],
        "suggested_verses": [],
        "materials": [],
        "commentaries": [],
        "cross_references": [],
        "message": None,
        "query_expansion": None,
        "membership": membership.decision_payload(
            membership.evaluate_access(db, user, increment=False)
        ),
    }

    # 홈 카테고리(인물/사건/논문 등) → DB 목록 직접 연결
    browse = _category_browse_mode(query)
    if browse:
        _fill_category_browse(db, results, browse, lang, msg)
        results["mode"] = "topic"
        results["browse"] = browse
        return results

    q_norm = query.replace("절", " ").strip()
    scripture_hit = False

    # 구절: 요한복음 4장 1절 / 요한복음 4:1 / 요한복음 4 1
    verse_m = (
        re.search(r"^(.+?)\s+(\d+)\s*장\s+(\d+)\s*$", q_norm)
        or re.search(r"^(.+?)\s+(\d+)\s*[:：]\s*(\d+)\s*$", q_norm)
        or re.search(r"^(.+?)\s+(\d+)\s+(\d+)\s*$", q_norm)
    )
    # 장: 요한복음 4장 / 요한복음 4
    chapter_m = re.search(r"^(.+?)\s+(\d+)\s*장\s*$", query.strip()) or re.search(
        r"^(.+?)\s+(\d+)\s*장\s*$", q_norm
    )

    if verse_m:
        book = resolve_book_name(verse_m.group(1).strip())
        chapter, verse = int(verse_m.group(2)), int(verse_m.group(3))
        if book:
            book_row = db.query(models.BibleBook).filter(models.BibleBook.name == book).first()
            if book_row:
                v = (
                    db.query(models.Verse)
                    .filter(
                        models.Verse.book_id == book_row.id,
                        models.Verse.chapter_num == chapter,
                        models.Verse.verse_num == verse,
                    )
                    .first()
                )
                if v:
                    scripture_hit = True
                    results["mode"] = "verse"
                    results["verse"] = _verse_payload(v, lang)
                    results["commentaries"] = _fetch_commentaries(db, book_row, chapter, verse)
                    results["cross_references"] = _fetch_cross_refs(db, book_row, chapter, verse, lang=lang)
                else:
                    scripture_hit = True
                    results["mode"] = "verse"
                    results["message"] = msg["verse_missing"](book, chapter, verse)

    elif chapter_m:
        book = resolve_book_name(chapter_m.group(1).strip())
        chapter = int(chapter_m.group(2))
        if book:
            book_row = db.query(models.BibleBook).filter(models.BibleBook.name == book).first()
            if book_row:
                rows = (
                    db.query(models.Verse)
                    .filter(
                        models.Verse.book_id == book_row.id,
                        models.Verse.chapter_num == chapter,
                    )
                    .order_by(models.Verse.verse_num)
                    .all()
                )
                scripture_hit = True
                results["mode"] = "chapter"
                results["chapter"] = {"book": book_display(book, lang), "book_ko": book, "chapter": chapter}
                results["verses"] = [
                    _verse_payload(v, lang)
                    for v in rows
                ]
                if not rows:
                    results["message"] = msg["chapter_missing"](book, chapter)
                else:
                    results["commentaries"] = _fetch_commentaries(db, book_row, chapter, verse=None, limit=4)

    if scripture_hit:
        return results

    q_lower = query.lower()
    tokens = [t for t in re.findall(r"[가-힣a-zA-Z0-9]+", query) if len(t) >= 2]

    book_only = resolve_book_name(query.replace(" ", ""))
    if book_only and query.replace(" ", "") == book_only:
        book_row = db.query(models.BibleBook).filter(models.BibleBook.name == book_only).first()
        if book_row:
            chapters = [
                c[0]
                for c in db.query(models.Verse.chapter_num)
                .filter(models.Verse.book_id == book_row.id)
                .distinct()
                .order_by(models.Verse.chapter_num)
                .all()
            ]
            results["mode"] = "book"
            results["chapter"] = {"book": book_display(book_only, lang), "book_ko": book_only, "chapter": None}
            if normalize_lang(lang) == "EN":
                b = book_display(book_only, lang)
                results["suggested_verses"] = [f"{b} {c}" for c in chapters[:40]]
            else:
                results["suggested_verses"] = [f"{book_only} {c}장" for c in chapters[:40]]
            if chapters:
                first_ch = chapters[0]
                rows = (
                    db.query(models.Verse)
                    .filter(
                        models.Verse.book_id == book_row.id,
                        models.Verse.chapter_num == first_ch,
                    )
                    .order_by(models.Verse.verse_num)
                    .limit(20)
                    .all()
                )
                results["verses"] = [_verse_payload(v, lang) for v in rows]
            return results

    # 토픽 검색: 번역·키워드 확장 (사전 + LLM 캐시)
    expansion = expand_query_for_search(query, use_llm=True)
    results["query_expansion"] = expansion.to_public()

    # 번역 확장어 (KO+EN) — 인물/사건/개념/본문/자료 공통
    x_terms = expansion.all_terms
    x_ko = set(t.lower() for t in expansion.terms_ko)
    x_en = set(t.lower() for t in expansion.terms_en)

    def _term_hit(text: str) -> bool:
        if not text:
            return False
        tl = text.lower()
        if text in query or tl in q_lower:
            return True
        for t in x_terms:
            if len(t) >= 2 and (t.lower() in tl or t in text):
                return True
        return False

    matched_entity_ids = set()
    from kg_i18n import (
        char_info,
        concept_definition,
        concept_name,
        era_text,
        event_background,
        event_name,
        location_name,
    )
    for char in db.query(models.Character).all():
        en_alias = KO_TO_EN_CHAR.get(char.name, "")
        if (
            char.name in tokens
            or (len(char.name) >= 2 and char.name in query)
            or (char.original_name and char.original_name in query)
            or (en_alias and en_alias.lower() in q_lower)
            or (en_alias and en_alias.lower() in x_en)
            or char.name.lower() in x_ko
            or _term_hit(char.name)
            or (en_alias and _term_hit(en_alias))
        ):
            matched_entity_ids.add(char.id)
            results["characters"].append(
                {
                    "name": char_display(char.name, lang),
                    "original_name": char.original_name,
                    "era": era_text(char.era, lang),
                    "info": char_info(char.name, char.genealogy_info, lang),
                    "verses": [
                        verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                        for v in char.verses[:20]
                    ],
                    "events": [event_name(e.name, lang) for e in char.events[:8]],
                }
            )
            for v in char.verses[:20]:
                key = (v.book_id, v.chapter_num, v.verse_num)
                if key not in verse_ref_seen:
                    verse_ref_seen.add(key)
                    results["verses"].append(_verse_payload(v, lang, msg["reason_char"](char.name)))

    for ev in db.query(models.Event).all():
        if _term_hit(ev.name) or any(t in ev.name for t in tokens if len(t) >= 2):
            results["events"].append(
                {
                    "name": event_name(ev.name, lang),
                    "period": era_text(ev.period, lang),
                    "background": event_background(ev.name, ev.historical_background, lang),
                    "verses": [
                        verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                        for v in ev.verses[:8]
                    ],
                    "characters": [
                        char_display(c.name, lang) for c in ev.characters[:8]
                    ],
                    "locations": [location_name(loc.name, lang) for loc in ev.locations[:8]],
                    "source_note": (
                        "Registered DB record"
                        if normalize_lang(lang) == "EN"
                        else "DB에 등록된 기록"
                    ),
                }
            )
            for v in ev.verses[:12]:
                key = (v.book_id, v.chapter_num, v.verse_num)
                if key not in verse_ref_seen:
                    verse_ref_seen.add(key)
                    results["verses"].append(_verse_payload(v, lang, msg["reason_event"](ev.name)))

    for loc in db.query(models.Location).all():
        if _term_hit(loc.name) or (loc.ancient_name and _term_hit(loc.ancient_name)):
            results["locations"].append(
                {
                    "name": location_name(loc.name, lang),
                    "ancient_name": loc.ancient_name,
                    "verses": [
                        verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                        for v in loc.verses[:8]
                    ],
                }
            )
            for v in loc.verses[:8]:
                key = (v.book_id, v.chapter_num, v.verse_num)
                if key not in verse_ref_seen:
                    verse_ref_seen.add(key)
                    results["verses"].append(_verse_payload(v, lang, msg["reason_loc"](loc.name)))

    for cp in db.query(models.Concept).all():
        if _term_hit(cp.name) or cp.name in query:
            results["concepts"].append(
                {
                    "name": concept_name(cp.name, lang),
                    "definition": concept_definition(cp.name, cp.definition, lang),
                    "verses": [
                        verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                        for v in cp.verses[:8]
                    ],
                }
            )
            for v in cp.verses[:8]:
                key = (v.book_id, v.chapter_num, v.verse_num)
                if key not in verse_ref_seen:
                    verse_ref_seen.add(key)
                    results["verses"].append(_verse_payload(v, lang, msg["reason_concept"](cp.name)))

    strong_m = re.search(r"\b([GgHh])\s*0*(\d{1,5})\b", query)
    if strong_m:
        sn = f"{strong_m.group(1).upper()}{int(strong_m.group(2)):04d}"
        row = db.query(models.StrongEntry).filter_by(strong_number=sn).first()
        if row:
            results["strong"].append(
                {
                    "strong_number": row.strong_number,
                    "lemma": row.lemma,
                    "gloss": row.gloss,
                    "study_path": f"/study?strong={row.strong_number}",
                }
            )
            results["mode"] = "strong"
    elif len(query) <= 24 and ("원어" in query or "agape" in q_lower or "아가페" in query):
        hits = _rag.lookup_strong_entries(db, query, limit=5)
        for row in hits:
            results["strong"].append(
                {
                    "strong_number": row.strong_number,
                    "lemma": row.lemma,
                    "gloss": row.gloss,
                    "study_path": f"/study?strong={row.strong_number}",
                }
            )

    if _wants_materials_catalog(query) or _wants_papers(query):
        results["materials"] = _collect_materials(db, query, x_terms, tokens, limit=24, lang=lang)

    # 번역 확장 키워드로 KO/EN 본문·책명 LIKE 검색
    if results["mode"] == "topic" and len(results["verses"]) < 12:
        try:
            like_verses = []
            uniq_terms = []
            seen_terms = set()
            for t in list(x_terms) + tokens:
                k = (t or "").lower()
                if k and k not in seen_terms and len(t) >= 2:
                    seen_terms.add(k)
                    uniq_terms.append(t)

            for token in uniq_terms[:16]:
                pat = f"%{token}%"
                like_verses += (
                    db.query(models.Verse)
                    .join(models.BibleBook)
                    .filter(
                        (models.Verse.text_ko.like(pat))
                        | (models.Verse.text_en.ilike(pat))
                        | (models.BibleBook.name.like(pat))
                    )
                    .limit(24)
                    .all()
                )
            seen = set(verse_ref_seen)
            for v in like_verses:
                key = (v.book_id, v.chapter_num, v.verse_num)
                if key in seen:
                    continue
                seen.add(key)
                verse_ref_seen.add(key)
                results["verses"].append(_verse_payload(v, lang, msg["reason_keyword"]))
                if len(results["verses"]) >= 16:
                    break
        except Exception:
            pass

    # TF-IDF: 원 질의 + 영문 확장어로 추가 검색
    if results["mode"] == "topic" and len(results["verses"]) < 10:
        try:
            tfidf_q = " ".join([query] + expansion.terms_en[:6])
            rag_hits = _rag.tfidf_search(db, tfidf_q, limit=10)
            for v in rag_hits:
                key = (v.book_id, v.chapter_num, v.verse_num)
                if key not in verse_ref_seen:
                    verse_ref_seen.add(key)
                    results["verses"].append(_verse_payload(v, lang, msg["reason_similar"]))
                if len(results["verses"]) >= 16:
                    break
        except Exception:
            pass

    # 공개 자료: 확장 키워드로 재스캔 (인물/사건 유무와 무관)
    if results["mode"] == "topic":
        have_titles = {m.get("title") for m in results["materials"]}
        extra = _collect_materials(db, query, x_terms, tokens, limit=24, lang=lang)
        for m in extra:
            if m.get("title") in have_titles:
                continue
            results["materials"].append(m)
            have_titles.add(m.get("title"))
            if len(results["materials"]) >= 24:
                break

    if results["mode"] == "topic":
        has_hits = any(
            [
                results["verse"],
                results["verses"],
                results["characters"],
                results["events"],
                results["locations"],
                results["concepts"],
                results["strong"],
                results["materials"],
                results["suggested_verses"],
            ]
        )
        if not has_hits and not results.get("message"):
            results["message"] = msg["no_hits"]
        # 구절이 충분히 채워졌으면 partial 안내 생략
        elif len(results["verses"]) >= 3:
            results["message"] = None
        elif has_hits and len(results["verses"]) < 3 and not results.get("message"):
            results["message"] = msg["partial_hits"]

    return results
