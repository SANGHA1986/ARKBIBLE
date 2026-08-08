import math
import re
import os
import json
import hashlib
import requests
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
import models

# Environment loader helper (.env → os.environ; 이미 있는 값은 덮어쓰지 않음)
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

load_env()


def plain_section(title: str) -> str:
    """마크다운(#, **) 없이 섹션 제목만."""
    return f"\n{title}\n"


def strip_answer_markdown(text: str) -> str:
    """답변에서 #/**/> 목록 마크다운 제거."""
    if not text:
        return ""
    t = text
    t = re.sub(r"^#{1,6}\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"^\*\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^>\s?", "", t, flags=re.MULTILINE)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


class RagEngine:
    def __init__(self):
        self.vector_available = False

    def tokenize(self, text):
        """한글 형태소/음절 단위의 매칭을 위한 심플 토크나이저"""
        return re.findall(r'[ㄱ-ㅎㅏ-ㅣ가-힣a-zA-Z0-9]+', text.lower())

    def calculate_similarity(self, q1: str, q2: str) -> float:
        """자카드 유사도를 이용한 유사 질문 대조 매칭 알고리즘"""
        tokens1 = set(self.tokenize(q1))
        tokens2 = set(self.tokenize(q2))
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union)

    def tfidf_search(self, db: Session, query: str, limit: int = 5):
        """가볍고 확실한 키워드 기반 유사 구절 검색. SQL pre-filter로 3만 구절 전체 스캔 회피."""
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        # SQL LIKE pre-filter: 영문 본문·한국어 placeholder·책 이름에서 토큰 포함 구절만
        conditions = []
        for token in query_tokens:
            if not token:
                continue
            pat = f"%{token}%"
            conditions.append(models.Verse.text_en.like(pat))
            conditions.append(models.Verse.text_ko.like(pat))
            conditions.append(models.BibleBook.name.like(pat))

        verses = (
            db.query(models.Verse)
            .join(models.BibleBook)
            .filter(or_(*conditions))
            .limit(200)
            .all()
        )

        scored_verses = []
        for v in verses:
            text = f"{v.text_en or ''} {v.text_ko or ''} {v.book.name} {v.text_original or ''}"
            tokens = self.tokenize(text)
            if not tokens:
                continue
            score = 0
            for token in query_tokens:
                if token in tokens:
                    tf = tokens.count(token) / len(tokens)
                    score += tf + 1.0
            if score > 0:
                scored_verses.append((v, score))

        scored_verses.sort(key=lambda x: x[1], reverse=True)
        return [v[0] for v in scored_verses[:limit]]

    def _citation_from_registry(self, src: models.SourceRegistry) -> dict:
        return {
            "title": src.title,
            "author": src.author,
            "code": src.code,
            "copyright_status": src.copyright_status,
            "license_type": src.license_type,
            "attribution": src.attribution_text,
            "attribution_text": src.attribution_text,
            "source_url": src.source_url,
            "embed_path": f"/study?strong=",
        }

    def _citation_from_source(self, src: models.Source) -> dict:
        lic = getattr(src, "license", None)
        return {
            "title": src.title,
            "author": src.author,
            "copyright_status": src.copyright_status,
            "license_type": (lic.license_type if lic else src.copyright_status) or "Public",
            "license": (lic.license_type if lic else src.copyright_status) or "Public",
            "source_url": src.source_url,
            "attribution": (src.description or "")[:300],
            "attribution_text": (src.description or "")[:300],
            "academic_level": src.academic_level,
            "embed_path": f"/search?q={src.title[:60] if src.title else ''}",
        }

    def _iter_safe_sources(self, db: Session):
        return (
            db.query(models.Source)
            .filter(
                models.Source.copyright_status.notin_(
                    ["Copyrighted", "Unsafe", "None", "Unknown", ""]
                )
            )
            .all()
        )

    def lookup_sources_for_query(self, db: Session, query: str, limit: int = 5):
        """질문·제목·저자·태그로 등록 Source(자료) 매칭.

        제목이 질문에 거의 그대로 있으면 그 자료 1건만 반환(옆 논문·주석 혼입 방지).
        """
        q = query.lower()
        noise = {
            "자료", "설명", "주세요", "등록", "추측", "금지", "내용", "대해", "만", "으로", "에서",
            "explain", "using", "only", "registered", "content", "speculate", "reply", "english",
            "about", "the", "for", "with", "do", "not", "please", "database", "notes", "db",
            "참고", "기록", "해석", "설명해", "주", "세요",
        }
        tokens = [t for t in self.tokenize(query) if len(t) >= 2 and t not in noise]
        scored = []
        for src in self._iter_safe_sources(db):
            lic = getattr(src, "license", None)
            if lic and not getattr(lic, "allow_ai_read", True):
                continue
            title = (src.title or "").lower()
            author = (src.author or "").lower()
            blob = (
                f"{title} {author} {src.source_type or ''} "
                f"{src.tags or ''} {src.description or ''}"
            ).lower()
            score = 0
            if title and len(title) >= 6 and title in q:
                score += 40  # 특정 자료 질문
            elif title and len(title) >= 20:
                # 긴 제목의 핵심 구간이 질문에 포함
                core = title[:48].strip()
                if core and core in q:
                    score += 35
            elif title and any(len(t) >= 4 and t in title for t in tokens):
                score += 8
            if author and author in q:
                score += 6
            for t in tokens:
                if len(t) >= 3 and t in blob:
                    score += 2
            if "institutes" in q and "institutes" in title:
                score += 15
            if ("칼뱅" in query or "calvin" in q) and (
                "calvin" in author or "calvin" in title or "칼뱅" in blob
            ):
                score += 10
            if "catechism" in q and "catechism" in title:
                score += 10
            if score >= 4:
                scored.append((score, src))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            return []
        # 특정 자료(높은 점수)면 1건만 — 출처에 무관 논문/주석이 붙는 문제 방지
        if scored[0][0] >= 30:
            return [scored[0][1]]
        return [s for _, s in scored[:limit]]

    def _source_kind_label(self, src, lang: str = "KO") -> str:
        """목회·신학 독자용 자료 종류 라벨."""
        from book_i18n import normalize_lang
        en = normalize_lang(lang) == "EN"
        st = (src.source_type or "").strip()
        title = src.title or ""
        desc = (src.description or "").lower()
        if st == "JournalArticle" or "journal article" in desc or "openalex" in desc:
            return (
                "Scholarly journal article (abstract only in DB; full text not scraped)"
                if en else
                "학술 논문(저널 기사). DB에는 초록·메타만 등록됨. 전문(PDF 본문)은 수집하지 않음."
            )
        if "summary seed" in title.lower() or "요약 시드" in (src.description or ""):
            return (
                "Summary seed only (not the full commentary text)"
                if en else
                "요약 시드(안내 자료). 교부·주석 전문 본문이 아니라, DB에 넣은 짧은 요지 요약입니다."
            )
        if st == "Patristic":
            return (
                "Patristic source entry"
                if en else
                "교부 문헌 등록 항목"
            )
        if st == "Commentary" or "commentary" in title.lower():
            return "Commentary / 주석 자료" if en else "주석·해설 자료"
        return st or ("Registered source" if en else "등록 자료")

    def build_source_context(self, db: Session, sources, lang: str = "KO"):
        """Source 메타·요약·연결 Interpretation·Commentary를 RAG 컨텍스트로 조립."""
        from book_i18n import normalize_lang, verse_ref_display
        en = normalize_lang(lang) == "EN"
        lines = []
        citations = []
        interpretations = []
        for src in sources:
            citations.append(self._citation_from_source(src))
            kind = self._source_kind_label(src, lang=lang)
            tag = "[Registered Source]" if en else "[등록 자료]"
            lines.append(
                f"{tag}\n"
                f"  Kind: {kind}\n"
                f"  Title: {src.title}\n"
                f"  Author: {src.author or '—'}\n"
                f"  Type: {src.source_type or 'Book'}\n"
                f"  License: {src.copyright_status or '—'}\n"
                f"  Academic: {src.academic_level or '—'}"
            )
            # description에서 Journal 이름 추출 힌트
            if src.description:
                lines.append(f"  Meta/Summary: {src.description.strip()}")
            if src.tags:
                lines.append(f"  Tags: {src.tags}")
            if src.source_url:
                lines.append(f"  URL/DOI: {src.source_url}")

            interps = (
                db.query(models.Interpretation)
                .filter_by(source_id=src.id)
                .limit(12)
                .all()
            )
            for i in interps:
                interpretations.append(i)
                ref = ""
                if i.verse_id and i.verse:
                    ref = verse_ref_display(
                        i.verse.book.name, i.verse.chapter_num, i.verse.verse_num, lang
                    )
                is_paper = (src.source_type or "") == "JournalArticle"
                is_seed = "summary seed" in (src.title or "").lower() or "요약 시드" in (
                    src.description or ""
                )
                if is_paper:
                    iv_tag = "[Abstract — scholarly abstract text]" if en else "[논문 초록 — 학술 초록 원문]"
                elif is_seed:
                    iv_tag = (
                        "[Seed summary — NOT full commentary]"
                        if en else
                        "[요약 시드 요지 — 주석 전문 아님]"
                    )
                else:
                    iv_tag = "[Interpretation]" if en else "[등록 해석]"
                lines.append(
                    f"  {iv_tag} [{i.viewpoint}] {i.scholar_name or '-'}"
                    + (f" ({ref})" if ref else "")
                    + f"\n    claim: {i.claim or '—'}"
                )
                if i.evidence:
                    # 논문 초록은 더 길게
                    lim = 2500 if is_paper else 800
                    lines.append(f"    evidence: {(i.evidence or '')[:lim]}")

            comms = (
                db.query(models.Commentary)
                .filter_by(source_id=src.id)
                .limit(4)
                .all()
            )
            if not comms:
                lines.append(
                    "  [Commentary] none registered for this source"
                    if en else
                    "  [주석 본문] 이 자료에 연결된 Commentary 행 없음"
                )
            for c in comms:
                ctag = "[Commentary]" if en else "[주석]"
                lines.append(
                    f"  {ctag} {c.passage_ref or '—'}\n"
                    f"    {(c.commentary_text or '')[:1000]}"
                )
        return "\n".join(lines), citations, interpretations

    def _grounded_explain_system_prompt(self, lang: str = "KO") -> str:
        from book_i18n import normalize_lang
        en = normalize_lang(lang) == "EN"
        if en:
            return (
                "You are ARK's research assistant for pastors, seminary students, and researchers. "
                "Explain ONLY from the provided DB blocks.\n"
                "Rules:\n"
                "- Use only provided blocks. Do NOT invent facts or Strong numbers.\n"
                "- Write plain text only: no markdown (#, **, >).\n"
                "- Use these section titles exactly:\n"
                "1. Verified Facts\n"
                "2. Traditional Interpretations\n"
                "3. Scholarly Views\n"
                "4. Further Research\n"
                "- Start section 1 by naming WHAT this item is "
                "(journal article abstract / summary seed / commentary / verse).\n"
                "- For JournalArticle: section 1 = what it is + metadata + clear English paraphrase "
                "of the abstract's argument. Sections 2–3 = none in DB unless commentary blocks exist. "
                "Section 4 = DOI/URL/OpenAlex from THIS source only.\n"
                "- For summary seed: say it is NOT full patristic text; quote the short claim without "
                "sermon-style expansion. Do not invent Chrysostom/Henry wording not in blocks.\n"
                "- Do not mention unrelated papers/commentaries that are not in the blocks.\n"
                "- Reply entirely in English."
            )
        return (
            "당신은 한국 교회 목회자·신학생·연구자를 돕는 ARK 연구 보조입니다. "
            "제공된 DB 블록만 근거로 설명하십시오.\n"
            "독자 기준:\n"
            "- 첫 문장에서 「이것이 무엇인지」를 분명히: "
            "학술 논문(초록만) / 요약 시드(전문 아님) / 주석 / 성경 구절.\n"
            "- 학술 용어는 쓰되, 한 줄로 뜻을 풀어 문장이 이어지게 쓰십시오. "
            "영어 초록을 한국어로 옮길 때 주어·목적어가 보이게 자연스럽게.\n"
            "- 「논문인지, 주석인지, 짧은 시드인지」혼동되지 않게 하십시오.\n"
            "규칙:\n"
            "- DB 블록에 있는 내용만. 없는 사실·교리·Strong 금지.\n"
            "- 평문만: #, **, > 금지.\n"
            "- 섹션 제목 고정:\n"
            "1. 확인된 사실\n"
            "2. 전통적 해석\n"
            "3. 학계 다양한 견해\n"
            "4. 추가 연구 자료\n"
            "학술 논문(JournalArticle / [논문 초록])일 때:\n"
            "- 1번: 먼저 「○○ 저널에 실린 학술 논문입니다. DB에는 초록만 있고 전문은 없습니다.」 "
            "이어서 저자·라이선스·DOI. 그다음 「이 논문이 말하는 내용」아래 초록을 "
            "연구 목적→방법→주장 순으로 한국어 문장이 이어지게 요약. "
            "(가)(나)(다) 같은 기호 라벨은 쓰지 마십시오.\n"
            "- 초록이 페이지 찌꺼기면 「초록 미수집, 메타만」.\n"
            "- 2·3번: 주석 없으면 "
            "「논문 초록 등록분이라 전통 주석·비교 견해는 DB에 없습니다.」\n"
            "- 4번: 이 자료 DOI·OpenAlex·URL만 적기 (「없음」이라고 쓰지 말 것).\n"
            "요약 시드([요약 시드 요지])일 때:\n"
            "- 1번에 「교부/주석 전문이 아니라 DB 요약 시드」명시.\n"
            "- 영문 단어 claim/evidence를 그대로 쓰지 말고 "
            "「등록 요지」「근거 메모」로 옮기십시오. 설교체 재해석 금지.\n"
            "- 2번: 「요지 요약만 있음 / 주석 본문 없음」.\n"
            "- Henry·Gill 등 블록에 없는 주석가를 끌어오지 마십시오.\n"
            "- 답변은 한국어로 작성."
        )

    def call_grounded_llm(self, query: str, context: str, lang: str = "KO", timeout: int = 60):
        """DB 컨텍스트만으로 OpenRouter 해석/설명. 실패 시 None."""
        load_env()
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return None
        model_name = os.environ.get("RAG_MODEL", "deepseek/deepseek-v4-flash")
        from book_i18n import normalize_lang
        en = normalize_lang(lang) == "EN"
        user_content = (
            (f"User question: {query}\n\n[Registered DB blocks]\n{context}"
             if en else
             f"사용자 질문: {query}\n\n[등록 DB 블록]\n{context}")
        )
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "ARK",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": self._grounded_explain_system_prompt(lang)},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.15,
                },
                timeout=timeout,
            )
            if response.status_code != 200:
                return None
            choices = (response.json() or {}).get("choices") or []
            if not choices:
                return None
            text = (choices[0].get("message") or {}).get("content") or ""
            text = strip_answer_markdown(text)
            return text or None
        except Exception:
            return None

    def _raw_source_catalog_answer(self, sources, interps, ctx: str, lang: str = "KO") -> str:
        """LLM 실패 시에도 목회·신학 독자가 읽기 쉬운 고정 형식."""
        from book_i18n import normalize_lang
        en = normalize_lang(lang) == "EN"
        src = sources[0] if sources else None
        if not src:
            return ctx
        kind = self._source_kind_label(src, lang=lang)
        is_paper = (src.source_type or "") == "JournalArticle"
        is_seed = "summary seed" in (src.title or "").lower() or "요약 시드" in (
            src.description or ""
        )
        journal = ""
        if src.description and "Journal:" in src.description:
            try:
                journal = src.description.split("Journal:", 1)[1].split(".", 1)[0].strip()
            except Exception:
                journal = ""
        abstract = ""
        claim = ""
        for i in interps:
            if i.evidence:
                abstract = i.evidence.strip()
            if i.claim:
                claim = i.claim.strip()
            break

        if en:
            s1 = plain_section("1. Verified Facts")
            s1 += f"What this is: {kind}\n"
            s1 += f"Title: {src.title}\nAuthor: {src.author or '—'}\n"
            if journal:
                s1 += f"Journal: {journal}\n"
            s1 += f"License: {src.copyright_status or '—'}\n"
            if src.source_url:
                s1 += f"URL/DOI: {src.source_url}\n"
            if is_paper and abstract:
                s1 += "\nWhat the article says (abstract as registered):\n" + abstract + "\n"
            elif is_seed:
                s1 += f"\nRegistered seed claim: {claim or '—'}\nEvidence note: {abstract or '—'}\n"
            else:
                s1 += "\n" + ctx + "\n"
            s2 = plain_section("2. Traditional Interpretations")
            s2 += (
                "Summary seed / abstract only — no full commentary text in DB.\n"
                if (is_paper or is_seed) else
                "See registered blocks above, or none in DB.\n"
            )
            s3 = plain_section("3. Scholarly Views") + "No comparison views registered for this item.\n"
            s4 = plain_section("4. Further Research")
            s4 += (f"URL/DOI: {src.source_url}\n" if src.source_url else "No URL in DB.\n")
            if src.description and "OpenAlex:" in src.description:
                s4 += src.description.strip() + "\n"
            return s1 + s2 + s3 + s4

        s1 = plain_section("1. 확인된 사실")
        if is_paper:
            s1 += (
                f"이것은 학술 논문(저널 기사)입니다. {kind}\n"
                f"제목: {src.title}\n"
                f"저자: {src.author or '—'}\n"
            )
            if journal:
                s1 += f"게재 저널: {journal}\n"
            s1 += f"라이선스: {src.copyright_status or '—'}\n"
            if src.source_url:
                s1 += f"DOI/URL: {src.source_url}\n"
            s1 += "\n이 논문이 말하는 내용(DB 등록 초록):\n"
            s1 += (abstract or "(초록 없음)") + "\n"
            s1 += (
                "\n안내: 위는 영문 초록 원문입니다. "
                "AI 요약이 가능할 때는 한국어로 풀어 설명합니다.\n"
            )
        elif is_seed:
            s1 += (
                f"이것은 주석·교부 전문이 아니라 「요약 시드」입니다. {kind}\n"
                f"제목: {src.title}\n"
                f"저자: {src.author or '—'}\n"
                f"라이선스: {src.copyright_status or '—'}\n"
            )
            if src.source_url:
                s1 += f"출처 URL: {src.source_url}\n"
            s1 += f"\nDB에 등록된 요지: {claim or '—'}\n"
            s1 += f"근거 메모: {abstract or '—'}\n"
        else:
            s1 += f"자료 종류: {kind}\n" + ctx + "\n"

        s2 = plain_section("2. 전통적 해석")
        if is_paper:
            s2 += "이 항목은 논문 초록 등록분이라, 전통 주석 본문은 DB에 없습니다.\n"
        elif is_seed:
            s2 += "등록된 것은 짧은 요지 요약뿐이며, 해당 저자의 주석 전문 본문은 DB에 없습니다.\n"
        else:
            s2 += "연결된 주석 본문이 있으면 위에 표시됩니다. 없으면 DB 미등록.\n"

        s3 = plain_section("3. 학계 다양한 견해")
        s3 += "이 자료 항목에 대한 비교 견해는 DB에 등록되어 있지 않습니다.\n"

        s4 = plain_section("4. 추가 연구 자료")
        if src.source_url:
            s4 += f"DOI/URL: {src.source_url}\n"
        if src.description:
            s4 += f"등록 메타: {src.description.strip()}\n"
        if not src.source_url and not src.description:
            s4 += "DB에 추가 링크가 없습니다.\n"
        return s1 + s2 + s3 + s4

    def build_source_catalog_answer(self, db: Session, query: str, sources, lang: str = "KO"):
        """등록 Source·해석 근거로 설명. LLM 가능 시 요약, 실패 시 raw 목록."""
        from book_i18n import normalize_lang
        en = normalize_lang(lang) == "EN"
        # 설명 요청이면 상위 매칭 1~2건만 (옆 자료 혼입 방지)
        if len(sources) > 2 and self._wants_explain(query):
            sources = sources[:1]
        ctx, citations, interps = self.build_source_context(db, sources, lang=lang)
        raw_answer = self._raw_source_catalog_answer(sources, interps, ctx, lang=lang)

        # 독자 안내를 질문 앞에 붙여 LLM이 형식을 지키게 함
        guided = (
            query
            if en else
            (
                f"{query}\n\n"
                "작성 지시: 한국 목회자·신학생이 바로 이해하게. "
                "첫 문장에 학술논문(초록만)/요약시드/주석 여부를 밝히고, "
                "논문이면 초록 내용을 「이 논문이 말하는 내용」으로 문장 연결해 한국어 요약. "
                "출처·링크는 이 자료만. 다른 논문·주석가를 끌어오지 말 것."
            )
        )
        llm_answer = self.call_grounded_llm(guided, ctx, lang=lang)
        answer = llm_answer if llm_answer else raw_answer
        return {
            "query": query,
            "answer": answer,
            "source_citations": citations,  # 설명 대상 자료만
            "difficulty_level": "Medium" if llm_answer else "Easy",
            "cached": False,
            "reliability": {
                "citation_count": len(citations),
                "source_reliability": "A",
                "is_controversial": False,
                "confidence_score": 0.9 if llm_answer else 0.85,
            },
        }

    def _wants_explain(self, query: str) -> bool:
        q = query.lower()
        return any(
            w in q
            for w in [
                "해석", "설명해", "설명", "풀어", "의미", "뜻풀이", "번역해", "설명해줘",
                "mean", "explain", "interpret", "what does", "what is", "describe",
                "알려", "소개", "tell me", "무엇", "뭐",
            ]
        )

    def _wants_strong_lookup(self, query: str) -> bool:
        """원어/Strong을 사용자가 명시적으로 요청했을 때만."""
        q = query.lower()
        if re.search(r"\b[GgHh]\s*0*\d{1,5}\b", query):
            return True
        return any(
            w in q
            for w in [
                "strong", "원어", "헬라", "히브리", "greek", "hebrew", "lexicon",
                "아가페", "agape", "lemma", "gloss",
            ]
        )

    def build_explain_empty_answer(self, query: str, lang: str = "KO"):
        """설명 요청인데 DB 매칭 없음 — 추측·LLM 없이 안내."""
        from book_i18n import normalize_lang
        en = normalize_lang(lang) == "EN"
        if en:
            answer = (
                plain_section("1. Verified Facts")
                + "No matching records in DB.\n"
                + plain_section("4. Further Research")
                + "Try a verse reference: e.g. John 3:16\n"
            )
        else:
            answer = (
                plain_section("1. 확인된 사실")
                + "질문과 연결된 구절·자료·원어·인물·사건을 DB에서 찾지 못했습니다.\n"
                + plain_section("4. 추가 연구")
                + "구절 형식으로 다시 질문: 예) 요한복음 3:16 설명해 주세요\n"
            )
        return {
            "query": query,
            "answer": answer,
            "source_citations": [],
            "difficulty_level": "Easy",
            "cached": False,
            "reliability": {
                "citation_count": 0,
                "source_reliability": "B",
                "is_controversial": False,
                "confidence_score": 0.4,
            },
        }

    def lookup_event_for_query(self, db: Session, query: str):
        """질문에서 사건명 매칭 (긴 이름 우선)."""
        events = db.query(models.Event).all()
        hits = [ev for ev in events if ev.name and ev.name in query]
        if not hits:
            return None
        hits.sort(key=lambda e: len(e.name or ""), reverse=True)
        return hits[0]

    def build_event_explain_answer(self, db: Session, query: str, ev, lang: str = "KO"):
        """사건 해석 — 등록 배경 + 연결 구절 본문 + (있으면) 주석. 빈 템플릿 금지."""
        from book_i18n import normalize_lang, verse_ref_display

        en = normalize_lang(lang) == "EN"
        citations = []
        verse_lines = []
        ctx_blocks = []

        bg = (ev.historical_background or "").strip()
        chars = [c.name for c in (ev.characters or [])]
        verses = list(ev.verses or [])
        # 연결 구절이 적으면 같은 장에서 보강(최대 8절)
        if verses and len(verses) < 5:
            sample = verses[0]
            more = (
                db.query(models.Verse)
                .filter_by(book_id=sample.book_id, chapter_num=sample.chapter_num)
                .order_by(models.Verse.verse_num)
                .limit(12)
                .all()
            )
            seen = {(v.book_id, v.chapter_num, v.verse_num) for v in verses}
            for v in more:
                key = (v.book_id, v.chapter_num, v.verse_num)
                if key not in seen:
                    verses.append(v)
                    seen.add(key)
                if len(verses) >= 8:
                    break

        for v in verses[:8]:
            ref = verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
            ko = (v.text_ko or "").strip()
            en_txt = (v.text_en or "").strip()
            body = ko if (not en and ko and not ko.startswith("[공개")) else (en_txt or ko or "—")
            verse_lines.append(f"- {ref}: {body}")
            ctx_blocks.append(f"[Verse {ref}]\n{body}")

        # 주석 샘플 (연결 구절 기준)
        comm_lines = []
        for v in verses[:3]:
            comms = (
                db.query(models.Commentary)
                .filter_by(book_id=v.book_id, chapter_num=v.chapter_num)
                .limit(2)
                .all()
            )
            for c in comms:
                src = c.source
                title = src.title if src else "Commentary"
                text = (c.commentary_text or "").strip()[:400]
                if not text:
                    continue
                comm_lines.append(f"- [{title}] {c.passage_ref or ''}: {text}")
                ctx_blocks.append(f"[Commentary {title}]\n{text}")
                if src:
                    citations.append({
                        "title": src.title,
                        "author": src.author or "",
                        "license_type": src.copyright_status or "",
                        "source_url": src.source_url or "",
                        "attribution": src.description or "",
                    })
                if len(comm_lines) >= 4:
                    break
            if len(comm_lines) >= 4:
                break

        # LLM 가능 시 DB 블록만으로 풀어쓰기 (없으면 고정 서술)
        llm_answer = None
        if not en and (bg or verse_lines):
            ctx = (
                f"[Event]\nname={ev.name}\nperiod={ev.period or ''}\nbackground={bg}\n"
                f"characters={', '.join(chars)}\n\n"
                + "\n\n".join(ctx_blocks)
            )
            llm_answer = self.call_grounded_llm(
                query,
                ctx
                + "\n\n규칙: 위 DB 블록만으로 「이 사건이 무엇인지」를 한국어로 설명. "
                "없는 교리 논쟁을 지어내지 말 것. 구절 본문을 인용할 것.",
                lang=lang,
                timeout=50,
            )

        if llm_answer and len(llm_answer) > 80 and "찾을 수 없" not in llm_answer:
            return {
                "query": query,
                "answer": llm_answer,
                "difficulty_level": "Medium",
                "source_citations": citations,
                "cached": False,
                "reliability": {
                    "citation_count": len(citations),
                    "source_reliability": "A" if verse_lines else "B",
                    "is_controversial": False,
                    "confidence_score": 0.88,
                },
            }

        char_txt = ", ".join(chars) if chars else ("none registered" if en else "미등록")
        if en:
            answer = (
                plain_section("1. Verified Facts")
                + f"Event: {ev.name}\n"
                + f"Period: {ev.period or '—'}\n"
                + f"Summary (registered): {bg or '—'}\n"
                + f"People: {char_txt}\n\n"
                + ("Related verses:\n" + "\n".join(verse_lines) + "\n" if verse_lines else "")
                + plain_section("2. Traditional Interpretations")
                + (
                    "Registered commentary excerpts:\n" + "\n".join(comm_lines) + "\n"
                    if comm_lines
                    else "No commentary excerpt loaded for this event seed.\n"
                )
                + plain_section("3. Scholarly Views")
                + "Only open/registered records are asserted here.\n"
                + plain_section("4. Further Research")
                + f"/search?q={ev.name}\n"
            )
        else:
            answer = (
                plain_section("1. 확인된 사실")
                + f"사건: {ev.name}\n"
                + f"시기: {ev.period or '—'}\n"
                + f"등록 요약: {bg or '—'}\n"
                + f"관련 인물: {char_txt}\n\n"
                + (
                    "관련 구절 본문(DB):\n" + "\n".join(verse_lines) + "\n\n"
                    if verse_lines
                    else "연결 구절 본문이 부족합니다.\n\n"
                )
                + plain_section("2. 전통적 해석")
                + (
                    "등록 주석 발췌:\n" + "\n".join(comm_lines) + "\n"
                    if comm_lines
                    else "이 사건 시드에 연결된 주석 발췌가 아직 적습니다. 위 구절 본문을 우선 근거로 보십시오.\n"
                )
                + plain_section("3. 학계 다양한 견해")
                + "여기서는 DB에 등록된 공개 기록 범위만 확정합니다.\n"
                + plain_section("4. 추가 연구")
                + f"통합 검색: /search?q={ev.name}\n"
                + "대표 본문: 사도행전 15장\n"
            )
        return {
            "query": query,
            "answer": answer,
            "difficulty_level": "Medium",
            "source_citations": citations,
            "cached": False,
            "reliability": {
                "citation_count": len(citations) + len(verse_lines),
                "source_reliability": "A" if verse_lines else "B",
                "is_controversial": False,
                "confidence_score": 0.9 if (bg and verse_lines) else 0.75,
            },
        }

    def build_explain_from_db(self, db: Session, query: str, lang: str = "KO"):
        """모든 '설명/해석' 요청의 단일 진입점 — DB 등록분만 근거로 해석(무관 Strong 제외)."""
        # 1) 구절 참조 (최우선)
        ref_verses = self.lookup_verses_by_reference(db, query) or []
        if ref_verses:
            return self.build_verse_explain_answer(db, query, ref_verses, lang=lang)

        # 1b) 사건명 매칭 — 빈 템플릿 대신 구절·배경으로 설명
        ev = self.lookup_event_for_query(db, query)
        if ev:
            return self.build_event_explain_answer(db, query, ev, lang=lang)

        # 2) 등록 자료(Source)
        matched_sources = self.lookup_sources_for_query(db, query)
        if matched_sources:
            return self.build_source_catalog_answer(db, query, matched_sources, lang=lang)

        # 3) 원어 — 명시적 Strong/원어 요청일 때만
        if self._wants_strong_lookup(query):
            strong_hits = self.lookup_strong_entries(db, query, limit=3)
            if strong_hits:
                return self.build_strong_answer(db, query, strong_hits, lang=lang)

        # 4) 자료 카탈로그 키워드
        materials_res = self.handle_materials_query(db, query, lang=lang)
        if materials_res:
            return materials_res

        # 5) 인물·사건 (Strong 끼워 넣지 않음)
        easy_res = self.handle_easy_routing(db, query, lang=lang, skip_strong=True)
        if easy_res:
            return easy_res

        # 6) 주제 → 유사 구절 TF-IDF → 구절 설명 형식
        tfidf_verses = self.tfidf_search(db, query, limit=2)
        if tfidf_verses:
            return self.build_verse_explain_answer(db, query, tfidf_verses, lang=lang)

        return self.build_explain_empty_answer(query, lang=lang)

    def _collect_verse_explain_materials(self, db: Session, verses, lang: str = "KO"):
        """구절 설명용 DB 블록·citation·raw fallback 조립."""
        from book_i18n import book_display, normalize_lang, verse_ref_display

        en = normalize_lang(lang) == "EN"
        citations = []
        seen_cite = set()
        ctx_lines = []
        parts = []
        comm_block = []
        interp_block = []
        xref_block = []

        def add_cite(title, author="", license_type="", source_url="", attribution=""):
            key = title or source_url
            if not key or key in seen_cite:
                return
            seen_cite.add(key)
            citations.append({
                "title": title,
                "author": author,
                "license_type": license_type,
                "license": license_type,
                "copyright_status": license_type,
                "source_url": source_url,
                "attribution": attribution,
                "attribution_text": attribution,
            })

        web = db.query(models.SourceRegistry).filter_by(code="WEB_PD").first()
        if web:
            add_cite(
                web.title, web.author, web.license_type or "Public Domain",
                web.source_url, web.attribution_text or "",
            )

        parts.append(
            plain_section("1. Verified Facts (registered text)")
            if en else plain_section("1. 확인된 사실 (DB 등록 본문)")
        )
        for v in verses:
            ref = verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
            ko = (v.text_ko or "").strip()
            ko_missing = not ko or ko.startswith("[공개 한국어")
            en_text = (v.text_en or "—").strip()
            parts.append(f"{ref} (WEB PD)\n{en_text}")
            if ko_missing:
                parts.append("한국어: DB 미등록" if not en else "Korean: not registered in DB")
                ko_line = "한국어: DB 미등록" if not en else "Korean: not registered"
            else:
                parts.append(f"{'한국어' if not en else 'Korean'}: {ko}")
                ko_line = ko
            parts.append("")
            ctx_lines.append(f"[Verse] {ref}\nEN(WEB): {en_text}\nKO: {ko_line}")

        for v in verses:
            ref = verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
            # 구절 범위 일치 주석 우선, intro(verse_start NULL)는 뒤로
            comms = (
                db.query(models.Commentary, models.Source)
                .join(models.Source, models.Source.id == models.Commentary.source_id)
                .filter(
                    models.Commentary.book_id == v.book_id,
                    models.Commentary.chapter_num == v.chapter_num,
                    (models.Commentary.verse_start.is_(None))
                    | ((models.Commentary.verse_start <= v.verse_num)
                       & (models.Commentary.verse_end >= v.verse_num)),
                )
                .order_by(
                    models.Commentary.verse_start.is_(None),
                    models.Commentary.verse_start.asc(),
                )
                .limit(8)
                .all()
            )
            for c, src in comms:
                lic = getattr(src, "license", None)
                if lic and not getattr(lic, "allow_ai_read", True):
                    continue
                lic_type = (
                    (lic.license_type if lic else None)
                    or src.copyright_status
                    or "Public Domain"
                )
                # 출처는 짧게(저자·라이선스). 본문은 충분한 길이로 전달.
                short_attr = f"{src.author or 'Commentator'} · {lic_type}".strip(" ·")
                add_cite(
                    src.author or src.title,
                    src.author,
                    lic_type,
                    src.source_url,
                    short_attr,
                )
                excerpt = (c.commentary_text or "").strip()
                if len(excerpt) > 8000:
                    excerpt = excerpt[:8000]
                label = src.author or src.title
                comm_block.append(f"[{label}] ({c.passage_ref})\n{excerpt}")
                ctx_lines.append(
                    f"[Commentary] {label} | {c.passage_ref}\n{excerpt}"
                )

            for interp in v.interpretations:
                src = interp.source
                if src:
                    lic = getattr(src, "license", None)
                    if lic and not getattr(lic, "allow_ai_read", True):
                        continue
                    lic_type = (
                        (lic.license_type if lic else None)
                        or src.copyright_status
                        or "Public"
                    )
                    add_cite(src.title, src.author, lic_type, src.source_url, "")
                block = (
                    f"[{interp.viewpoint}] {interp.scholar_name or '—'}\n"
                    f"claim: {interp.claim or '—'}\n"
                    f"evidence: {interp.evidence or '—'}"
                )
                interp_block.append(block)
                ctx_lines.append(f"[Interpretation]\n{block}")

            xrefs = (
                db.query(models.CrossReference, models.BibleBook)
                .join(models.BibleBook, models.BibleBook.id == models.CrossReference.to_book_id)
                .filter(
                    models.CrossReference.from_book_id == v.book_id,
                    models.CrossReference.from_chapter == v.chapter_num,
                    models.CrossReference.from_verse == v.verse_num,
                )
                .order_by(models.CrossReference.votes.desc())
                .limit(8)
                .all()
            )
            if xrefs:
                xref_src = (
                    db.query(models.Source)
                    .filter(models.Source.title.like("%OpenBible%"))
                    .first()
                )
                if xref_src:
                    add_cite(
                        xref_src.title, xref_src.author,
                        xref_src.copyright_status or "CC BY",
                        xref_src.source_url,
                        xref_src.description or "",
                    )
                lines = []
                for cr, tb in xrefs:
                    b = book_display(tb.name, lang)
                    r = f"{b} {cr.to_chapter}:{cr.to_verse_start}"
                    if cr.to_verse_end and cr.to_verse_end != cr.to_verse_start:
                        r += f"-{cr.to_verse_end}"
                    tgt = (
                        db.query(models.Verse)
                        .filter_by(
                            book_id=tb.id,
                            chapter_num=cr.to_chapter,
                            verse_num=cr.to_verse_start,
                        )
                        .first()
                    )
                    snippet = (tgt.text_en or "")[:120].strip() if tgt else ""
                    line = f"- {r}: \"{snippet}…\"" if snippet else f"- {r}"
                    lines.append(line)
                    ctx_lines.append(f"[Cross-ref] {r}" + (f" | {snippet}" if snippet else ""))
                xref_block.append(
                    (f"Cross-refs ({ref}):\n" if en else f"연관 구절 ({ref}):\n")
                    + "\n".join(lines)
                )

        parts.append(
            plain_section("2. Registered commentaries (PD/CC0)")
            if en else plain_section("2. 등록된 주석 (PD/CC0)")
        )
        if comm_block:
            parts.extend(comm_block)
        else:
            book_names = ", ".join({v.book.name for v in verses})
            parts.append(
                f"No public commentary collected yet for {book_names}."
                if en else
                f"이 책({book_names})의 공개 주석이 아직 수집되지 않았습니다."
            )

        parts.append(
            plain_section("3. Registered interpretations")
            if en else plain_section("3. 등록된 해석")
        )
        if interp_block:
            parts.extend(interp_block)
        else:
            parts.append("(none)" if en else "(없음)")

        parts.append(
            plain_section("4. Cross-references (OpenBible CC BY)")
            if en else plain_section("4. 연관 구절 (OpenBible CC BY)")
        )
        if xref_block:
            parts.extend(xref_block)
        else:
            parts.append("(none)" if en else "(없음)")

        parts.append(
            plain_section("5. Further Research")
            if en else plain_section("5. 추가 연구")
        )
        parts.append(
            "Ask Strong numbers separately for lexicon. Korean PD text when verified."
            if en else
            "원어는 Strong 번호로 별도 질문하세요. 한국어 본문은 검증된 PD 역본 적재 후 이용."
        )

        return {
            "context": "\n\n".join(ctx_lines),
            "raw_answer": "\n".join(parts),
            "citations": citations,
            "has_commentary": bool(comm_block),
        }

    def build_verse_explain_answer(self, db: Session, query: str, verses, lang: str = "KO"):
        """구절 설명 — DB 본문·주석·연관구절 근거로 LLM 해석, 실패 시 raw 목록."""
        mat = self._collect_verse_explain_materials(db, verses, lang=lang)
        llm_answer = None
        if mat["context"].strip():
            llm_answer = self.call_grounded_llm(query, mat["context"], lang=lang)
        return {
            "query": query,
            "answer": llm_answer or mat["raw_answer"],
            "source_citations": mat["citations"],
            "difficulty_level": "Medium" if llm_answer else "Easy",
            "cached": False,
            "reliability": {
                "citation_count": len(mat["citations"]),
                "source_reliability": "A" if mat["has_commentary"] else "B",
                "is_controversial": False,
                "confidence_score": 0.9 if llm_answer and mat["has_commentary"] else (
                    0.8 if llm_answer else (0.75 if mat["has_commentary"] else 0.6)
                ),
            },
        }

    def lookup_strong_entries(self, db: Session, query: str, limit: int = 5):
        """공개 수집 Strong/STEP 사전에서 번호·표제어 매칭 (공개 라이선스 소스만)."""
        results = []
        # G0026 / H7225 / G26
        for m in re.finditer(r"\b([GgHh])\s*0*(\d{1,5})\b", query):
            sn = f"{m.group(1).upper()}{int(m.group(2)):04d}"
            row = db.query(models.StrongEntry).filter_by(strong_number=sn).first()
            if row:
                results.append(row)

        q_tokens = self.tokenize(query)
        # 한글/영문 키워드로 gloss·lemma 부분 검색
        if not results and q_tokens:
            candidates = db.query(models.StrongEntry).limit(5000).all()
            scored = []
            for e in candidates:
                blob = f"{e.lemma or ''} {e.gloss or ''} {e.definition_short or ''} {e.transliteration or ''}".lower()
                score = sum(1 for t in q_tokens if t in blob)
                # 아가페 / agape 특례
                if "아가페" in query or "agape" in query.lower():
                    if e.strong_number == "G0026" or (e.lemma and "ἀγάπ" in e.lemma) or (e.lemma and "ἀγάπ" in e.lemma):
                        score += 5
                if score > 0:
                    scored.append((score, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, e in scored[:limit]:
                if e not in results:
                    results.append(e)

        return results[:limit]

    def _strip_lexicon_html(self, text: str) -> str:
        t = re.sub(r"<[^>]+>", " ", text or "")
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _ko_meaning_from_en_gloss(self, gloss: str, definition: str = "") -> str:
        """공개 영문 Strong gloss → 한국어 뜻 (정식 사전 복제 아님, 요약 풀어쓰기)."""
        blob = f"{gloss or ''} {definition or ''}".lower()
        pairs = [
            ("exceeding joy", "넘치는 기쁨, 크게 기뻐함"),
            ("exuberant joy", "넘치는 기쁨, 환희"),
            ("exultation", "환희, 크게 기뻐 날뜀"),
            ("gladness", "기쁨, 즐거움"),
            ("rejoice", "기뻐하다"),
            ("charity", "사랑(아가페적 사랑)"),
            ("beloved", "사랑하는 이"),
            ("welcome", "환영, 기뻐 맞이함"),
            ("joy", "기쁨"),
            ("love", "사랑"),
            ("faith", "믿음"),
            ("hope", "소망"),
            ("grace", "은혜"),
            ("peace", "평안, 평화"),
            ("mercy", "긍휼, 자비"),
            ("truth", "진리"),
            ("spirit", "영, 성령"),
            ("holy", "거룩한"),
            ("sin", "죄"),
            ("salvation", "구원"),
            ("righteousness", "의"),
            ("glory", "영광"),
            ("power", "능력, 권능"),
            ("wisdom", "지혜"),
            ("word", "말씀"),
            ("lord", "주, 주님"),
            ("god", "하나님"),
            ("kingdom", "나라, 왕국"),
            ("gospel", "복음"),
            ("church", "교회"),
            ("covenant", "언약"),
            ("pray", "기도하다"),
            ("prayer", "기도"),
            ("repent", "회개하다"),
            ("forgive", "용서하다"),
            ("bless", "축복하다"),
            ("praise", "찬양"),
            ("worship", "예배, 경배"),
            ("believe", "믿다"),
            ("save", "구원하다"),
            ("life", "생명"),
            ("death", "죽음"),
            ("light", "빛"),
            ("world", "세상"),
            ("heaven", "하늘"),
            ("earth", "땅"),
            ("heart", "마음"),
            ("soul", "영혼"),
            ("flesh", "육체"),
            ("blood", "피"),
            ("cross", "십자가"),
            ("baptism", "세례"),
            ("apostle", "사도"),
            ("prophet", "선지자"),
            ("angel", "천사"),
            ("servant", "종"),
            ("disciple", "제자"),
            ("fear", "경외, 두려움"),
            ("wrath", "진노"),
            ("comfort", "위로"),
            ("affliction", "환난, 고난"),
            ("temptation", "시험"),
            ("miracle", "기적"),
            ("eternal", "영원한"),
            ("everlasting", "영원한"),
            ("beginning", "시작, 태초"),
            ("create", "창조하다"),
            ("redeem", "속량하다"),
            ("sanctify", "거룩하게 하다"),
            ("justify", "의롭다 하다"),
            ("testify", "증언하다"),
            ("proclaim", "선포하다"),
            ("preach", "전파하다"),
            ("know", "알다"),
            ("hear", "듣다"),
            ("see", "보다"),
            ("come", "오다"),
            ("give", "주다"),
            ("call", "부르다"),
            ("send", "보내다"),
            ("follow", "따르다"),
            ("serve", "섬기다"),
            ("abide", "거하다"),
            ("reveal", "계시하다"),
            ("fulfill", "성취하다"),
            ("judge", "심판하다"),
            ("teach", "가르치다"),
            ("good", "선한, 좋은"),
            ("evil", "악한"),
            ("true", "참된"),
            ("false", "거짓된"),
            ("humble", "겸손한"),
            ("proud", "교만한"),
            ("wise", "지혜로운"),
            ("foolish", "어리석은"),
            ("pure", "깨끗한"),
            ("perfect", "완전한"),
            ("great", "큰"),
            ("small", "작은"),
            ("first", "첫째"),
            ("last", "마지막"),
            ("new", "새"),
            ("old", "옛"),
            ("man", "사람"),
            ("woman", "여자"),
            ("son", "아들"),
            ("father", "아버지"),
            ("mother", "어머니"),
            ("brother", "형제"),
            ("sister", "자매"),
            ("people", "백성"),
            ("nation", "민족"),
            ("city", "성읍"),
            ("house", "집"),
            ("temple", "성전"),
            ("altar", "제단"),
            ("sacrifice", "제사, 희생"),
            ("lamb", "어린양"),
            ("shepherd", "목자"),
            ("sheep", "양"),
            ("bread", "떡"),
            ("water", "물"),
            ("wine", "포도주"),
            ("day", "날"),
            ("night", "밤"),
            ("name", "이름"),
            ("way", "길"),
            ("voice", "음성"),
            ("hand", "손"),
            ("eye", "눈"),
            ("ear", "귀"),
            ("body", "몸"),
            ("strength", "힘"),
            ("rest", "안식"),
            ("promise", "약속"),
            ("law", "율법"),
            ("commandment", "계명"),
            ("witness", "증인, 증언"),
            ("king", "왕"),
            ("priest", "제사장"),
            ("feast", "잔치, 절기"),
            ("sabbath", "안식일"),
            ("time", "때"),
            ("age", "시대"),
            ("generation", "세대"),
        ]
        hits = []
        seen = set()
        for en_w, ko_w in pairs:
            if en_w in blob and ko_w not in seen:
                hits.append(ko_w)
                seen.add(ko_w)
            if len(hits) >= 4:
                break
        if hits:
            return ", ".join(hits)
        g = (gloss or definition or "").strip()
        if not g:
            return "등록된 한국어 정식 뜻풀이는 없고, 영문 공개 사전 정의만 있습니다"
        return f"「{g[:90]}」— 영문 공개 사전 요지를 위 문맥으로 이해"

    def _strong_lexicon_system_prompt(self, lang: str = "KO") -> str:
        from book_i18n import normalize_lang
        if normalize_lang(lang) == "EN":
            return (
                "You explain Strong's / STEP lexicon entries for pastors. "
                "Use ONLY the provided lexicon blocks. Plain text, no markdown. "
                "Sections: 1. Verified Facts 2. Traditional Interpretations "
                "3. Scholarly Views 4. Further Research. "
                "Quote the English gloss/definition first; do not invent senses."
            )
        return (
            "당신은 목회자·신학생을 돕는 원어 안내자입니다. "
            "제공된 Strong's/STEP 영문 사전 블록만 근거로 쓰십시오. "
            "평문만 쓰고 마크다운(# ** >)은 금지합니다. "
            "섹션 제목 고정:\n"
            "1. 확인된 사실\n"
            "2. 전통적 해석\n"
            "3. 학계 다양한 견해\n"
            "4. 추가 연구\n"
            "필수(오역 방지):\n"
            "- 1번 맨 앞에 「영문 근거(Strong's): …」를 원문 그대로 두십시오. "
            "영문 gloss/definition을 바꾸거나 늘리지 마십시오.\n"
            "- 그다음 Strong 번호·원어·음역.\n"
            "- 「참고 풀어쓰기(비공식): …」는 영문을 아주 짧게만 옮기고, "
            "「정식 한국어 원어사전이 아님·오역 가능」을 반드시 적으십시오.\n"
            "- 교의·설교 적용·추가 뉘앙스를 지어내지 마십시오.\n"
            "- STEP HTML은 제거하고 영문 핵심만.\n"
            "- 2번: 사전 정의 수준 / 교의는 주석 참고.\n"
            "- 3번: Strong's(1890) 고전 참고, 현대 사전과 다를 수 있음.\n"
            "- 4번: /study?strong=번호\n"
            "- 안내 문장은 한국어, 영문 근거 줄은 영어 유지."
        )

    def build_strong_answer(self, db: Session, query: str, entries, lang: str = "KO"):
        from book_i18n import normalize_lang
        en = normalize_lang(lang) == "EN"
        citations = []
        blocks = []
        for e in entries:
            src = e.source
            if src:
                c = self._citation_from_registry(src)
                c["embed_path"] = f"/study?strong={e.strong_number}"
                c["strong_number"] = e.strong_number
                citations.append(c)
            expansions = (
                db.query(models.LexiconExpansion)
                .filter_by(strong_number=e.strong_number)
                .limit(2)
                .all()
            )
            exp_plain = []
            for ex in expansions:
                if ex.source:
                    citations.append(self._citation_from_registry(ex.source))
                exp_plain.append(
                    f"[{ex.lexicon_name}] {self._strip_lexicon_html(ex.entry_text)[:500]}"
                )
            blocks.append(
                {
                    "e": e,
                    "exp": exp_plain,
                    "gloss": (e.gloss or e.definition_short or "").strip(),
                    "definition": (e.definition_full or "").strip(),
                }
            )

        seen = set()
        unique = []
        for c in citations:
            key = c.get("code") or c.get("title")
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # 오역 방지: 원어 답은 LLM 자유 번역 없이, 영문 근거 우선 고정 템플릿 사용
        parts = []
        for b in blocks:
            e = b["e"]
            if en:
                parts.append(
                    f"{e.strong_number} {e.lemma or ''} ({e.transliteration or ''})\n"
                    f"gloss: {b['gloss'] or '—'}\n"
                    f"definition: {(b['definition'] or '')[:500]}\n"
                    f"root: {e.root_word or '—'}\n"
                    + ("\n".join(b["exp"]) if b["exp"] else "")
                )
            else:
                ko_hint = self._ko_meaning_from_en_gloss(b["gloss"], b["definition"])
                en_gloss = b["gloss"] or "—"
                en_def = (b["definition"] or "")[:300] or "—"
                parts.append(
                    f"영문 근거(Strong's, 우선): {en_gloss}\n"
                    f"영문 정의: {en_def}\n"
                    f"원어: {e.strong_number} {e.lemma or ''} ({e.transliteration or ''})\n"
                    f"어원: {e.root_word or '—'}\n"
                    f"참고 풀어쓰기(비공식·오역 가능): {ko_hint}\n"
                    "※ 한국어 정식 원어사전이 아닙니다. 설교·교의 확정은 영문 근거·주석을 확인하십시오.\n"
                    + (
                        "STEP(영문 요약): " + self._strip_lexicon_html(b["exp"][0])[:280]
                        if b["exp"]
                        else ""
                    )
                )

        if en:
            answer = (
                plain_section("1. Verified Facts")
                + "Entries from public-domain lexicons (Strong's / STEP).\n\n"
                + "\n\n".join(parts)
                + plain_section("2. Traditional Interpretations")
                + "Dictionary definitions; doctrinal interpretation belongs in commentaries.\n"
                + plain_section("3. Scholarly Views")
                + "Strong's (1890) is a classic reference; modern lexicons may differ.\n"
                + plain_section("4. Further Research")
                + f"Lexicon detail: /study?strong={entries[0].strong_number}\n"
            )
        else:
            answer = (
                plain_section("1. 확인된 사실")
                + "공개 영문 원어 사전(Strong's / STEP) 근거입니다. "
                "한국어는 참고 풀어쓰기일 뿐, 정식 번역이 아닙니다.\n\n"
                + "\n\n".join(parts)
                + plain_section("2. 전통적 해석")
                + "위는 사전 정의 수준입니다. 교단별 교의·설교 적용은 주석을 참고하십시오.\n"
                + plain_section("3. 학계 다양한 견해")
                + "Strong's(1890)는 고전 참고용이며, 현대 사전(BDAG 등)과 다를 수 있습니다.\n"
                + plain_section("4. 추가 연구")
                + f"원어 상세(영문): /study?strong={entries[0].strong_number}\n"
            )
        return {
            "query": query,
            "answer": answer,
            "difficulty_level": "Easy",
            "source_citations": unique,
            "cached": False,
            "reliability": {
                "citation_count": len(unique),
                "source_reliability": "A",
                "is_controversial": False,
                "confidence_score": 0.9,
            },
        }

    def build_registered_fallback_answer(
        self, query: str, strong_hits, matched_verses, strong_citations, visible_interpretations,
        commentary_context: str = "", crossref_context: str = "", lang: str = "KO",
        source_context: str = "", source_citations=None,
    ):
        """LLM 호출 실패/중단 시 DB에 등록된 본문·원어·해석·주석·연관 구절을 그대로 제시."""
        from book_i18n import normalize_lang, verse_ref_display
        en = normalize_lang(lang) == "EN"
        parts = []
        if source_context:
            parts.append(
                "### 1. Registered sources (DB)"
                if en
                else "### 1. 등록 자료 (DB)"
            )
            parts.append(source_context.strip())
        if matched_verses:
            parts.append("### 1. Verified Facts (DB text)" if en else "### 1. 확인된 사실 (DB 등록 본문)")
            for v in matched_verses:
                ref = verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                parts.append(
                    f"- {ref}\n"
                    f"  EN(WEB): {(v.text_en or '—').strip()}\n"
                    f"  KO: {(v.text_ko or '—').strip()}"
                )
        if strong_hits:
            parts.append("\n### 2. Lexicon" if en else "\n### 2. 원어 정보")
            for e in strong_hits:
                parts.append(
                    f"- {e.strong_number}: {e.lemma or '—'} / {e.transliteration or '—'}\n"
                    f"  gloss: {e.gloss or e.definition_short or '—'}\n"
                    f"  root: {e.root_word or '—'}"
                )
        if visible_interpretations:
            parts.append("\n### 3. Registered interpretations" if en else "\n### 3. 등록된 해석")
            for interp in visible_interpretations:
                if en:
                    parts.append(
                        f"- [{interp.viewpoint}] {interp.scholar_name or '—'}\n"
                        f"  claim: {interp.claim or '—'}\n"
                        f"  evidence: {interp.evidence or '—'}"
                    )
                else:
                    parts.append(
                        f"- [{interp.viewpoint}] {interp.scholar_name or '—'}\n"
                        f"  주장: {interp.claim or '—'}\n"
                        f"  근거: {interp.evidence or '—'}"
                    )
        if commentary_context:
            parts.append("\n### 4. Public commentaries (PD/CC0)" if en else "\n### 4. 공개 주석 (PD/CC0)")
            parts.append(commentary_context.strip())
        if crossref_context:
            parts.append("\n### 5. Cross-references (OpenBible CC BY)" if en else "\n### 5. 연관 구절 (OpenBible CC BY)")
            parts.append(crossref_context.strip())
        if not parts:
            if en:
                parts.append(
                    "### 1. Verified Facts\n"
                    "No related DB records found.\n\n"
                    "### 6. Further Research\n"
                    "- Verses: search e.g. John 3:16, then ask the assistant.\n"
                    "- Lexicon: `/study?strong=G0026`"
                )
            else:
                parts.append(
                    "### 1. 확인된 사실\n"
                    "연관된 DB 기록이 없습니다.\n\n"
                    "### 6. 추가 연구 자료\n"
                    "- 구절: 「요한복음 3:16」처럼 검색 후 어시스턴트에게 질문하세요.\n"
                    "- 원어: `/study?strong=G0026`"
                )
        if en:
            parts.append(
                "\n### Note\n"
                "LLM response timed out or failed. Above is raw registered data. "
                "Check OpenRouter API key, model, and network—or try again shortly."
            )
        else:
            parts.append(
                "\n### 안내\n"
                "LLM 응답 생성이 지연되거나 실패했습니다. 위는 DB에 등록된 날것 자료입니다. "
                "OpenRouter API 키·모델·네트워크 상태를 확인하거나 잠시 후 다시 시도하세요."
            )
        all_citations = list(source_citations or []) + list(strong_citations or [])
        return {
            "query": query,
            "answer": "\n".join(parts),
            "source_citations": all_citations,
            "difficulty_level": "Easy",
            "cached": False,
            "reliability": {
                "citation_count": len(visible_interpretations or []) + len(source_citations or []),
                "source_reliability": "B",
                "is_controversial": False,
                "confidence_score": 0.6,
            },
        }

    def handle_materials_query(self, db: Session, query: str, lang: str = "KO"):
        """자료·주석 질문 — 등록 Source+Interpretation을 DB 그대로 반환 (추측 금지).

        특정 자료가 매칭되면 LLM으로 넘기지 않는다. (LLM이 '미등록'으로 오답하는 경우 방지)
        구절 참조+해석 요청만 RAG로 넘긴다.
        """
        q = query.lower()
        matched = self.lookup_sources_for_query(db, query)
        wants_explain = any(
            k in q
            for k in [
                "해석", "설명", "explain", "describe", "소개", "알려", "tell me",
                "what is", "무엇", "뭐", "설명해", "풀어", "의미",
            ]
        )
        is_verse_explain = wants_explain and self._query_has_verse_ref(query)

        # 구절 해석 요청이고 자료 제목 매칭이 없으면 자료 경로 스킵
        if is_verse_explain and not matched:
            return None

        material_keywords = [
            "주석", "commentary", "추천", "자료", "source", "서적", "book",
            "칼뱅", "calvin", "교리서", "catechism", "institutes", "material", "library",
        ]
        if not matched and not any(k in q for k in material_keywords):
            return None

        results = matched
        if not results:
            results = []
            for src in self._iter_safe_sources(db):
                lic = getattr(src, "license", None)
                if lic and not getattr(lic, "allow_ai_read", True):
                    continue
                blob = (
                    f"{src.title or ''} {src.author or ''} {src.source_type or ''} "
                    f"{src.tags or ''} {src.description or ''}"
                ).lower()
                if any(t in blob for t in self.tokenize(query)) or q in blob:
                    results.append(src)
        if not results:
            return None
        return self.build_source_catalog_answer(db, query, results, lang=lang)

    def _query_has_verse_ref(self, query: str) -> bool:
        return bool(
            re.search(r"([가-힣A-Za-z0-9]+)\s+(\d+)\s*장\s+(\d+)", query)
            or re.search(r"([가-힣A-Za-z0-9]+)\s+(\d+)\s*[:：]\s*(\d+)", query)
            or re.search(r"([가-힣A-Za-z0-9]+)\s+(\d+)\s+(\d+)", query)
        )

    def handle_easy_routing(self, db: Session, query: str, lang: str = "KO", skip_strong: bool = False):
        """단순 조회: Strong(명시적일 때) · 인물 · 사건."""
        if self._query_has_verse_ref(query):
            return None
        strong_hits = [] if skip_strong else self.lookup_strong_entries(db, query, limit=3)
        if not skip_strong and strong_hits and (
            re.search(r"[GgHh]\s*\d+", query)
            or any(w in query.lower() for w in ["아가페", "agape", "원어", "헬라", "히브리", "strong"])
        ):
            if re.search(r"[GgHh]\s*\d+", query) or any(
                w in query.lower() for w in ["아가페", "agape", "원어", "strong"]
            ):
                return self.build_strong_answer(db, query, strong_hits, lang=lang)

        # 사건/주제 키워드 (구절을 몰라도 검색)
        ev = self.lookup_event_for_query(db, query)
        if ev:
            return self.build_event_explain_answer(db, query, ev, lang=lang)

        characters = db.query(models.Character).all()
        from book_i18n import KO_TO_EN_CHAR, char_display, verse_ref_display, normalize_lang as _nl
        en_mode = _nl(lang) == "EN"
        for char in characters:
            en_alias = KO_TO_EN_CHAR.get(char.name, "")
            name_hit = (
                char.name in query
                or (en_alias and en_alias.lower() in query.lower())
            )
            if name_hit:
                is_complex = any(
                    word in query.lower()
                    for word in ["비교", "대조", "차이", "관계", "논쟁", "compare", "versus", "vs"]
                )
                if len(query) <= 25 and not is_complex:
                    children_names = ", ".join(
                        [char_display(c.name, lang) for c in char.children]
                    ) or ("none" if en_mode else "없음")
                    events_names = ", ".join([e.name for e in char.events]) or (
                        "none" if en_mode else "없음"
                    )
                    father_name = (
                        char_display(char.father.name, lang)
                        if char.father
                        else ("unknown" if en_mode else "미상")
                    )
                    disp = char_display(char.name, lang)

                    citations = []
                    if strong_hits and not skip_strong:
                        built = self.build_strong_answer(db, query, strong_hits[:1], lang=lang)
                        citations = built["source_citations"]

                    if en_mode:
                        answer = (
                            f"### 1. Verified Facts\n"
                            f"- **Name**: {disp} (original: {char.original_name or '—'})\n"
                            f"- **Era**: {char.era or '—'}\n"
                            f"- **Family**: father: {father_name} | children: {children_names}\n"
                            f"- **Notes**: {char.genealogy_info or 'Registered character in the knowledge graph.'}\n\n"
                            f"### 2. Traditional Interpretations\n"
                            f"- Traditions discuss {disp} in redemptive-historical context; compare labels in Explore.\n\n"
                            f"### 3. Scholarly Views\n"
                            f"- Historical and literary readings coexist. We only assert registered open records.\n\n"
                            f"### 4. Further Research\n"
                            f"- **Events**: {events_names}\n"
                            f"- Try `{disp}` in Explore, or Lexicon `/study`"
                        )
                    else:
                        answer = (
                            f"### 1. 확인된 사실\n"
                            f"- **이름**: {char.name} (원어명: {char.original_name or '미상'})\n"
                            f"- **시대**: {char.era or '미상'}\n"
                            f"- **가족 관계**: 아버지: {father_name} | 자녀: {children_names}\n"
                            f"- **활동 및 생애**: {char.genealogy_info or '지식 그래프에 등록된 인물입니다.'}\n\n"
                            f"### 2. 전통적 해석\n"
                            f"- 유대·기독교 전통에서 {char.name}은(는) 구속사적 맥락에서 다루어져 왔습니다.\n\n"
                            f"### 3. 학계 다양한 견해\n"
                            f"- 역사·문학적 해석이 병존합니다. 공개 수집 자료 범위에서만 단정합니다.\n\n"
                            f"### 4. 추가 연구 자료\n"
                            f"- **연관 사건**: {events_names}\n"
                            f"- **추천**: `{char.name}`, 원어 연구 `/study`"
                        )
                    return {
                        "query": query,
                        "answer": answer,
                        "difficulty_level": "Easy",
                        "source_citations": citations,
                        "cached": False,
                        "reliability": {
                            "citation_count": len(citations),
                            "source_reliability": "A",
                            "is_controversial": False,
                            "confidence_score": 1.0,
                        },
                    }
        # Strong만 매칭된 짧은 질문 (설명 요청이 아닐 때)
        if not skip_strong and strong_hits and len(query) <= 30:
            return self.build_strong_answer(db, query, strong_hits, lang=lang)
        return None

    def lookup_verses_by_reference(self, db: Session, query: str, limit: int = 5):
        """요한복음 3:16 / 창세기 1장 1절 형태면 DB 구절을 직접 가져옴."""
        try:
            from search_api import resolve_book_name
        except Exception:
            return []
        q_norm = query.replace("절", " ").strip()
        verse_m = (
            re.search(r"([가-힣A-Za-z0-9]+)\s+(\d+)\s*장\s+(\d+)", q_norm)
            or re.search(r"([가-힣A-Za-z0-9]+)\s+(\d+)\s*[:：]\s*(\d+)", q_norm)
            or re.search(r"([가-힣A-Za-z0-9]+)\s+(\d+)\s+(\d+)", q_norm)
        )
        chapter_m = re.search(r"([가-힣A-Za-z0-9]+)\s+(\d+)\s*장", query)
        out = []
        if verse_m:
            book = resolve_book_name(verse_m.group(1).strip())
            ch, vs = int(verse_m.group(2)), int(verse_m.group(3))
            if book:
                book_row = db.query(models.BibleBook).filter_by(name=book).first()
                if book_row:
                    v = (
                        db.query(models.Verse)
                        .filter_by(book_id=book_row.id, chapter_num=ch, verse_num=vs)
                        .first()
                    )
                    if v:
                        out.append(v)
        elif chapter_m:
            book = resolve_book_name(chapter_m.group(1).strip())
            ch = int(chapter_m.group(2))
            if book:
                book_row = db.query(models.BibleBook).filter_by(name=book).first()
                if book_row:
                    out = (
                        db.query(models.Verse)
                        .filter_by(book_id=book_row.id, chapter_num=ch)
                        .order_by(models.Verse.verse_num)
                        .limit(limit)
                        .all()
                    )
        return out

    def generate_rag_response(self, db: Session, query: str, lang: str = "KO"):
        """
        AI 비용 관리(난이도 라우팅, Jaccard 유사 질문 캐시 매칭) 및 4단계 구조화 답변품질 관리가 적용된 RAG 엔진
        공개 수집(Strong/STEP/Sefaria) 컨텍스트를 항상 우선 주입.
        """
        from book_i18n import book_display, detect_query_lang, normalize_lang, verse_ref_display
        lang = normalize_lang(lang or detect_query_lang(query))
        en = lang == "EN"
        # 매번 .env 재확인 (서버가 키 없이 떠 있어도 이후 로드 가능)
        load_env()

        # ★ Strong 번호 질문이 최우선 — 캐시/LLM보다 먼저 원어 답변
        if self._wants_strong_lookup(query):
            early_strong = self.lookup_strong_entries(db, query, limit=3)
            if early_strong and (
                re.search(r"\b[GgHh]\s*0*\d{1,5}\b", query)
                or any(w in query.lower() for w in ["원어", "strong", "lexicon", "아가페", "agape"])
            ):
                return self.build_strong_answer(db, query, early_strong, lang=lang)

        # ★ 설명/해석 요청 → 항상 DB 등록분만 (LLM 경로 사용 안 함)
        if self._wants_explain(query):
            return self.build_explain_from_db(db, query, lang=lang)

        matched_sources = self.lookup_sources_for_query(db, query)
        material_focused = bool(matched_sources) and not self._query_has_verse_ref(query)
        source_context = ""
        source_citations = []
        source_interps = []
        if matched_sources:
            source_context, source_citations, source_interps = self.build_source_context(
                db, matched_sources, lang=lang
            )

        # 자료 목록 (설명 키워드 없이 자료만 물을 때)
        materials_res = self.handle_materials_query(db, query, lang=lang)
        if materials_res:
            return materials_res

        ref_verses = self.lookup_verses_by_reference(db, query) or []

        # Strong — 구절/자료 질문이 아닐 때만
        skip_strong = material_focused or bool(ref_verses) or self._query_has_verse_ref(query)
        strong_hits = [] if skip_strong else self.lookup_strong_entries(db, query, limit=3)
        strong_context = ""
        strong_citations = []
        if strong_hits:
            for e in strong_hits:
                strong_context += (
                    f"[Strong {e.strong_number}] lemma={e.lemma} gloss={e.gloss} "
                    f"def={(e.definition_full or '')[:300]} source={e.source.code if e.source else ''}\n"
                )
                if e.source:
                    c = self._citation_from_registry(e.source)
                    c["strong_number"] = e.strong_number
                    c["embed_path"] = f"/study?strong={e.strong_number}"
                    strong_citations.append(c)

        # 1. 중복/유사 질문 캐시 검사 (실패·키없음 답변은 재사용하지 않음)
        #    언어가 다르면 캐시 무시 (KO 답변을 EN UI에 주지 않음)
        caches = db.query(models.ResponseCache).all()
        for c in caches:
            ans = c.answer or ""
            if "API 키" in ans or "LLM 확장 답변은 비활성" in ans or "가져올 수 없" in ans:
                continue
            # 빈 DB 시절 캐시(원어 없다고 한 답)는 재사용 금지
            if any(
                bad in ans
                for bad in (
                    "기록이 없습니다",
                    "등록된 자료가 없",
                    "등록되지 않았습니다",
                    "No matching records",
                    "등록되어 있지 않습니다",
                    "확인할 수 없습니다",
                    "서술할 수 없습니다",
                    "탭에서 전통을 구분",
                    "연결된 구절 시드 부족",
                )
            ):
                continue
            hangul = len(re.findall(r"[가-힣]", ans))
            latin = len(re.findall(r"[A-Za-z]", ans))
            ans_lang = "KO" if hangul > latin * 0.5 and hangul >= 8 else "EN"
            if ans_lang != lang and hangul + latin > 20:
                continue
            if self.calculate_similarity(query, c.query) >= 0.8:
                c.use_count += 1
                c.updated_at = datetime.datetime.utcnow()
                db.commit()

                citations = []
                if c.source_citations_json:
                    try:
                        citations = json.loads(c.source_citations_json)
                    except Exception:
                        pass
                return {
                    "query": query,
                    "answer": c.answer,
                    "source_citations": citations,
                    "cached": True,
                    "difficulty_level": c.difficulty_level,
                    "reliability": {
                        "citation_count": c.citation_count,
                        "source_reliability": c.source_reliability,
                        "is_controversial": c.is_controversial,
                        "confidence_score": c.confidence_score
                    }
                }

        # 2. 난이도 라우팅 (비-설명 질문)
        easy_res = self.handle_easy_routing(db, query, lang=lang) if not material_focused else None
        if easy_res:
            # Easy 질문 캐시 등록하여 다음번에 더욱 빠르게 응답
            query_hash = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
            new_cache = models.ResponseCache(
                query_hash=query_hash,
                query=query,
                answer=easy_res["answer"],
                source_citations_json=json.dumps(easy_res.get("source_citations") or [], ensure_ascii=False),
                difficulty_level="Easy",
                citation_count=len(easy_res.get("source_citations") or []),
                source_reliability="A",
                is_controversial=False,
                confidence_score=1.0
            )
            db.add(new_cache)
            try:
                db.commit()
            except Exception:
                db.rollback()
            return easy_res

        # 3. 신학적 복잡도 식별 (Hard: 칭의론, 구원론 등 비교 분석 단어 포함 시)
        is_hard = any(word in query for word in ["비교", "대조", "칭의론", "율법", "대립", "차이점"])
        difficulty = "Hard" if is_hard else "Medium"

        # 4. RAG 관련 지식 그래프 검색 및 컨텍스트 취합
        matched_verses = ref_verses
        if not matched_verses and not material_focused:
            matched_verses = self.tfidf_search(db, query, limit=3)
        context_str = (source_context + "\n" if source_context else "") + strong_context
        visible_interpretations = list(source_interps)
        commentary_context = ""
        crossref_context = ""

        has_protestant = False
        has_catholic = False
        reliability_ratings = []
        for src in matched_sources:
            if src.academic_level:
                reliability_ratings.append(src.academic_level)
        for interp in source_interps:
            if interp.viewpoint == "개신교":
                has_protestant = True
            elif interp.viewpoint == "가톨릭":
                has_catholic = True

        if matched_verses:
            for v in matched_verses:
                ref = verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                if en:
                    context_str += (
                        f"Verse: {ref}\n"
                        f"  EN(WEB PD): \"{(v.text_en or '').strip()}\"\n"
                        f"  KO: \"{(v.text_ko or '').strip()}\"\n"
                        f"  Original field: \"{(v.text_original or '').strip() or 'not registered'}\"\n"
                    )
                else:
                    context_str += (
                        f"구절: {v.book.name} {v.chapter_num}장 {v.verse_num}절\n"
                        f"  EN(WEB PD): \"{(v.text_en or '').strip()}\"\n"
                        f"  KO: \"{(v.text_ko or '').strip()}\"\n"
                        f"  원문필드: \"{(v.text_original or '').strip() or '미등록'}\"\n"
                    )

                # 공개 주석(PD/CC0) 주입 — 구절 특화 주석 우선, 최대 4개 주석가
                comms = (
                    db.query(models.Commentary, models.Source)
                    .join(models.Source, models.Source.id == models.Commentary.source_id)
                    .filter(
                        models.Commentary.book_id == v.book_id,
                        models.Commentary.chapter_num == v.chapter_num,
                        (models.Commentary.verse_start.is_(None))
                        | ((models.Commentary.verse_start <= v.verse_num)
                           & (models.Commentary.verse_end >= v.verse_num)),
                    )
                    .order_by(
                        models.Commentary.verse_start.is_(None),  # 구절 특화 먼저
                        models.Commentary.verse_start.asc(),
                    )
                    .limit(4)
                    .all()
                )
                for c, src in comms:
                    lic = getattr(src, "license", None)
                    if lic and not getattr(lic, "allow_ai_read", True):
                        continue
                    tag = "[Commentary]" if en else "[주석]"
                    label = src.author or src.title
                    body = (c.commentary_text or "").strip()
                    if len(body) > 8000:
                        body = body[:8000]
                    commentary_context += (
                        f"{tag} {label} — {c.passage_ref}\n"
                        f"{body}\n"
                    )

                # 연관 구절(OpenBible CC BY) 주입 — 상위 8개
                xrefs = (
                    db.query(models.CrossReference, models.BibleBook)
                    .join(models.BibleBook, models.BibleBook.id == models.CrossReference.to_book_id)
                    .filter(
                        models.CrossReference.from_book_id == v.book_id,
                        models.CrossReference.from_chapter == v.chapter_num,
                        models.CrossReference.from_verse == v.verse_num,
                    )
                    .order_by(models.CrossReference.votes.desc())
                    .limit(8)
                    .all()
                )
                if xrefs:
                    ref_strs = []
                    for cr, tb in xrefs:
                        b = book_display(tb.name, lang)
                        r = f"{b} {cr.to_chapter}:{cr.to_verse_start}"
                        if cr.to_verse_end and cr.to_verse_end != cr.to_verse_start:
                            r += f"-{cr.to_verse_end}"
                        ref_strs.append(r)
                    src_ref = verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                    if en:
                        crossref_context += f"Cross-refs ({src_ref}): {', '.join(ref_strs)}\n"
                    else:
                        crossref_context += f"연관 구절({src_ref}): {', '.join(ref_strs)}\n"

                for interp in v.interpretations:
                    source = interp.source
                    if source:
                        if source.academic_level:
                            reliability_ratings.append(source.academic_level)
                            
                        # 교파 간 이견 체크
                        if interp.viewpoint == "개신교":
                            has_protestant = True
                        elif interp.viewpoint == "가톨릭":
                            has_catholic = True
                            
                        if source.license:
                            # allow_ai_read = False 일 경우 검색에서 전면 배제 (저작권 LEVEL 3 차단)
                            if not getattr(source.license, "allow_ai_read", True):
                                continue
                            
                            # allow_ai_quote = False 일 경우 주장/근거 원문은 가리고 메타데이터만 힌트로 제공
                            if not getattr(source.license, "allow_ai_quote", True):
                                visible_interpretations.append(interp)
                                context_str += (
                                    f" - 신학관점: [{interp.viewpoint}] 학자/출처: {interp.scholar_name}\n"
                                    f"   [저작권 경고] 직접 인용 불가 자료입니다. 이 출처의 주장/근거는 간접 힌트로만 참고하십시오.\n"
                                )
                                continue
                                
                    visible_interpretations.append(interp)
                    context_str += (
                        f" - 신학관점: [{interp.viewpoint}] 학자/출처: {interp.scholar_name}\n"
                        f"   주장: {interp.claim}\n"
                        f"   근거: {interp.evidence}\n"
                    )

        # 5. OpenRouter API 통신 설정
        api_key = os.environ.get("OPENROUTER_API_KEY")
        model_name = os.environ.get("RAG_MODEL", "deepseek/deepseek-v4-flash")

        if not api_key:
            if matched_sources:
                return self.build_source_catalog_answer(db, query, matched_sources, lang=lang)
            if strong_hits:
                return self.build_strong_answer(db, query, strong_hits, lang=lang)
            verse_bits = []
            for v in matched_verses or []:
                ref = verse_ref_display(v.book.name, v.chapter_num, v.verse_num, lang)
                verse_bits.append(
                    f"- {ref}\n"
                    f"  EN: {(v.text_en or '—')[:400]}\n"
                    f"  KO: {(v.text_ko or '—')[:200]}"
                )
            if verse_bits:
                if en:
                    answer = (
                        "### 1. Verified Facts (registered text)\n"
                        + "\n".join(verse_bits)
                        + "\n\n### 2. Traditional Interpretations\n"
                        "- No paraphrase available: LLM key missing or no registered commentary.\n"
                        "- English WEB text is shown above. Use Strong numbers in `/study` for lexicon.\n\n"
                        "### 4. Further Research\n"
                        "- Example: search `G0026` or open Lexicon\n"
                        "- Load OPENROUTER_API_KEY in `.env` to enable explained answers from registered sources."
                    )
                else:
                    answer = (
                        "### 1. 확인된 사실 (DB 등록 본문)\n"
                        + "\n".join(verse_bits)
                        + "\n\n### 2. 전통적 해석\n"
                        "- 등록된 주석 해석이 없거나 LLM 키가 없어 풀어쓴 해석은 비활성입니다.\n"
                        "- 영문 WEB 본문은 위에 그대로 있습니다. 원어는 Strong 번호로 `/study`에서 조회하세요.\n\n"
                        "### 4. 추가 연구 자료\n"
                        "- 예: `G0026` 검색 또는 원어 연구 탭\n"
                        "- `.env`의 OPENROUTER_API_KEY가 서버에 로드되면 등록된 EN 정의를 한국어로 풀어 설명할 수 있습니다."
                    )
                return {
                    "query": query,
                    "answer": answer,
                    "source_citations": strong_citations,
                    "difficulty_level": "Easy",
                    "cached": False,
                    "reliability": {
                        "citation_count": len(strong_citations),
                        "source_reliability": "B",
                        "is_controversial": False,
                        "confidence_score": 0.55,
                    },
                }
            empty_ans = (
                "### 1. Verified Facts\n"
                "OpenRouter API key is not loaded, so LLM explanation is off. "
                "No direct match in registered sources, Strong/STEP, or verse text.\n\n"
                "### 4. Further Research\n"
                "- Verses: open Explore with e.g. John 3:16.\n"
                "- Materials: `/search?q=calvin` or Library.\n"
                "- Lexicon: `/study?strong=G0026`.\n"
                "- Restart the server after loading `.env` to enable explained answers."
                if en
                else (
                    "### 1. 확인된 사실\n"
                    "현재 OpenRouter API 키가 서버 환경에 로드되지 않아 LLM 해석이 비활성입니다. "
                    "등록 자료·공개 사전(Strong/STEP)·구절 본문에서도 직접 일치 항목을 찾지 못했습니다.\n\n"
                    "### 4. 추가 연구 자료\n"
                    "- 구절: 「요한복음 3장 16」처럼 탐색에서 먼저 본문을 여세요.\n"
                    "- 자료: `/search?q=칼뱅` 또는 자료실.\n"
                    "- 원어: `/study?strong=G0026` 또는 어시스턴트에 `G0026 해석`.\n"
                    "- 서버를 `.env` 로드 후 재시작하면 등록된 EN 자료를 한국어로 풀어 설명할 수 있습니다."
                )
            )
            return {
                "query": query,
                "answer": empty_ans,
                "source_citations": strong_citations,
                "difficulty_level": "Easy",
                "cached": False,
                "reliability": {
                    "citation_count": len(strong_citations),
                    "source_reliability": "B",
                    "is_controversial": False,
                    "confidence_score": 0.5,
                },
            }

        # 보조 설명: DB에 있는 알려진 내용만 (+ 등록된 EN을 사용자 언어로 풀어 설명)
        if en:
            system_prompt = (
                "You are the research assistant for the biblical knowledge platform 'ARK'.\n"
                "Your role is to help search and study registered records—not to preach or invent theology.\n\n"
                "Core rules:\n"
                "- Only state as 'verified facts' what appears in [Reference database information].\n"
                "- [Registered Source] blocks are collected books/materials with linked interpretations.\n"
                "- You may explain registered English definitions/text (Strong, WEB, commentaries) in clear English.\n"
                "- [Commentary] blocks (Matthew Henry, JFB, Clarke, Gill, Wesley, etc., PD/CC0) may be cited by author.\n"
                "- Cross-references may be suggested as Scripture-explains-Scripture links.\n"
                "- If details are not in the reference data, say 'not registered in DB'—do not guess.\n"
                "- Do not treat one denomination as the only answer; label traditions when they differ.\n"
                "- Reply entirely in English.\n\n"
                "Preferred structure:\n\n"
                "### 1. Verified Facts\n"
                "### 2. Traditional Interpretations\n"
                "### 3. Scholarly Views\n"
                "### 4. Further Research\n"
            )
            user_prefix = f"User question: {query}\n\n[Reference database information]\n"
            empty_hint = "No related DB records — do not invent facts; suggest Explore/Lexicon paths only."
        else:
            system_prompt = (
                "당신은 성경 지식 플랫폼 'ARK'의 연구 보조 어시스턴트입니다.\n"
                "역할은 검색·연구 결과를 도와주는 것이며, 설교를 대신 쓰거나 새로운 신학을 창작하는 것이 아닙니다.\n\n"
                "핵심 규칙:\n"
                "- [참고 데이터베이스 정보]에 있는 내용만 ‘확인된 사실’로 서술하십시오.\n"
                "- [등록 자료] 블록은 수집·등록된 서적/자료와 연결된 해석입니다.\n"
                "- Strong/STEP/WEB 등 등록된 영문 정의·본문은 한국어로 풀어서 설명해도 됩니다.\n"
                "- [주석] 블록(PD/CC0)은 해당 주석가의 견해로 명시해 인용·요약할 수 있습니다.\n"
                "- 연관 구절은 참고 자료로 안내할 수 있습니다.\n"
                "- 참고 정보에 없는 내용은 ‘DB에 등록되지 않음’이라고 밝히고 추측하지 마십시오.\n"
                "- 특정 교파를 유일한 정답으로 단정하지 마십시오.\n"
                "- 답변은 한국어로 작성하십시오.\n\n"
                "가능하면 다음 형태로 답하십시오:\n\n"
                "### 1. 확인된 사실 (Verified Facts)\n"
                "### 2. 전통적 해석 (Traditional Interpretations)\n"
                "### 3. 학계 다양한 견해 (Scholarly Views)\n"
                "### 4. 추가 연구 자료 (Further Research)\n"
            )
            user_prefix = f"사용자 질문: {query}\n\n[참고 데이터베이스 정보]\n"
            empty_hint = "연관 DB 기록 없음 — 없는 사실을 만들지 말고, 탐색/원어에서 무엇을 더 찾으면 좋은지만 안내하십시오."

        user_content = (
            user_prefix
            + f"{context_str or empty_hint}"
            + f"{commentary_context}"
            + f"{crossref_context}"
        )

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "ARK"
            }
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=40
            )

            if response.status_code != 200:
                err = f"OpenRouter status {response.status_code}"
                try:
                    err += f": {response.text[:200]}"
                except Exception:
                    pass
                return self.build_registered_fallback_answer(
                    query, strong_hits, matched_verses, strong_citations, visible_interpretations,
                    commentary_context, crossref_context, lang=lang,
                    source_context=source_context, source_citations=source_citations,
                )

            result_json = response.json()
            choices = result_json.get("choices") or []
            if not choices:
                return self.build_registered_fallback_answer(
                    query, strong_hits, matched_verses, strong_citations, visible_interpretations,
                    commentary_context, crossref_context, lang=lang,
                    source_context=source_context, source_citations=source_citations,
                )
            answer_text = choices[0]["message"]["content"]

            # 신뢰도 메타데이터 연산
            citation_count = len(visible_interpretations)
            is_controversial = (has_protestant and has_catholic)

            # 평균 신뢰도 등급 산출 (A=1.0, B=0.8, C=0.6)
            reliability_score = 0.8
            if reliability_ratings:
                scores = {"A": 1.0, "B": 0.8, "C": 0.6}
                avg = sum([scores.get(r, 0.8) for r in reliability_ratings]) / len(reliability_ratings)
                reliability_score = round(avg, 2)

            # 확신도 연산
            confidence = 0.9 if not is_controversial else 0.7
            if reliability_score < 0.8:
                confidence -= 0.1
            confidence_score = max(0.1, min(1.0, confidence))

            # 인용 출처 정보 가공
            citations = list(source_citations)
            for c in strong_citations:
                if c not in citations:
                    citations.append(c)
            for interp in visible_interpretations:
                if interp.source:
                    lic = None
                    try:
                        lic = interp.source.license
                    except Exception:
                        pass
                    citations.append({
                        "title": interp.source.title,
                        "author": interp.source.author,
                        "academic_level": interp.source.academic_level,
                        "license_type": lic.license_type if lic else "Public",
                        "license": lic.license_type if lic else "Public"
                    })

            # 중복 제거
            seen_titles = set()
            unique_citations = []
            for c in citations:
                key = c.get("code") or c.get("title")
                if key not in seen_titles:
                    seen_titles.add(key)
                    unique_citations.append(c)

            # 캐싱 레이어 등록
            query_hash = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
            new_cache = models.ResponseCache(
                query_hash=query_hash,
                query=query,
                answer=answer_text,
                source_citations_json=json.dumps(unique_citations, ensure_ascii=False),
                difficulty_level=difficulty,
                citation_count=citation_count,
                source_reliability="A" if reliability_score >= 0.9 else ("B" if reliability_score >= 0.7 else "C"),
                is_controversial=is_controversial,
                confidence_score=confidence_score
            )
            db.add(new_cache)
            db.commit()

            return {
                "query": query,
                "answer": answer_text,
                "source_citations": unique_citations,
                "cached": False,
                "difficulty_level": difficulty,
                "reliability": {
                    "citation_count": citation_count,
                    "source_reliability": "A" if reliability_score >= 0.9 else ("B" if reliability_score >= 0.7 else "C"),
                    "is_controversial": is_controversial,
                    "confidence_score": confidence_score
                }
            }

        except Exception as e:
            return self.build_registered_fallback_answer(
                query, strong_hits, matched_verses, strong_citations, visible_interpretations,
                commentary_context, crossref_context, lang=lang,
                source_context=source_context, source_citations=source_citations,
            )
