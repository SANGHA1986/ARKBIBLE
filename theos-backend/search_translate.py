"""검색용 질의 번역·키워드 확장 엔진.

사용자(KO/EN) 질의를 양쪽 언어 검색어로 풀어, 영문 위주 DB(WEB·주석·자료)와
한글 메타(인물·사건·개념)를 함께 찾는다.

1) 정적 동의어 사전 (즉시)
2) OpenRouter LLM 키워드 추출 (캐시, 실패 시 사전만)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any

import requests

from book_i18n import KO_TO_EN_CHAR, EN_TO_KO_CHAR, KO_TO_EN_BOOK, detect_query_lang, normalize_lang
from rag_engine import load_env

# KO → EN 검색 키워드
KO_TO_EN_TERMS: dict[str, list[str]] = {
    "언약": ["covenant"],
    "하나님의 언약": ["covenant", "God's covenant"],
    "아브라함 언약": ["Abraham", "covenant", "Abram"],
    "아브라함": ["Abraham", "Abram"],
    "모세": ["Moses"],
    "다윗": ["David"],
    "솔로몬": ["Solomon"],
    "예수": ["Jesus", "Christ"],
    "바울": ["Paul"],
    "베드로": ["Peter"],
    "창조": ["creation", "created", "create"],
    "구원": ["salvation", "saved", "save"],
    "믿음": ["faith", "believe", "believed"],
    "사랑": ["love", "loved", "charity"],
    "율법": ["law", "commandment", "torah"],
    "복음": ["gospel", "good news"],
    "회개": ["repent", "repentance"],
    "은혜": ["grace"],
    "죄": ["sin", "sins", "sinned"],
    "부활": ["resurrection", "risen", "rose"],
    "십자가": ["cross", "crucified"],
    "성령": ["Holy Spirit", "Spirit"],
    "메시아": ["Messiah", "Christ"],
    "왕국": ["kingdom"],
    "심판": ["judgment", "judgement"],
    "약속": ["promise", "promised"],
    "축복": ["bless", "blessed", "blessing"],
    "출애굽": ["exodus", "Egypt"],
    "홍해": ["Red Sea"],
    "시내": ["Sinai"],
    "가나안": ["Canaan"],
    "예루살렘": ["Jerusalem"],
    "이스라엘": ["Israel"],
    "이방인": ["Gentile", "Gentiles", "nations"],
    "칭의": ["justification", "justify", "righteousness"],
    "속죄": ["atonement", "propitiation"],
    "성막": ["tabernacle"],
    "성전": ["temple"],
    "제사장": ["priest", "priesthood"],
    "선지자": ["prophet", "prophets"],
    "사도": ["apostle", "apostles"],
    "교회": ["church"],
    "기도": ["pray", "prayer"],
    "예배": ["worship"],
    "안식일": ["sabbath"],
    "유월절": ["Passover"],
    "침례": ["baptism", "baptize"],
    "세례": ["baptism", "baptize"],
    "성찬": ["Lord's supper", "communion", "eucharist"],
    "종말": ["end times", "last days", "eschatology"],
    "천국": ["heaven", "kingdom of heaven"],
    "지옥": ["hell", "gehenna"],
    "사탄": ["Satan", "devil"],
    "천사": ["angel", "angels"],
    "기적": ["miracle", "miracles", "sign"],
    "비유": ["parable", "parables"],
    "지혜": ["wisdom"],
    "말씀": ["word", "scripture"],
    "성경": ["Bible", "scripture", "scriptures"],
    "주석": ["commentary"],
    "교부": ["church father", "patristic", "fathers"],
    "종교개혁": ["reformation", "reformer"],
}

# EN → KO (역방향)
EN_TO_KO_TERMS: dict[str, list[str]] = {}
for _ko, _ens in KO_TO_EN_TERMS.items():
    for _en in _ens:
        key = _en.lower()
        EN_TO_KO_TERMS.setdefault(key, [])
        if _ko not in EN_TO_KO_TERMS[key]:
            EN_TO_KO_TERMS[key].append(_ko)

# 인물·책명 보강
for _ko, _en in KO_TO_EN_CHAR.items():
    KO_TO_EN_TERMS.setdefault(_ko, [])
    if _en not in KO_TO_EN_TERMS[_ko]:
        KO_TO_EN_TERMS[_ko].append(_en)
    EN_TO_KO_TERMS.setdefault(_en.lower(), [])
    if _ko not in EN_TO_KO_TERMS[_en.lower()]:
        EN_TO_KO_TERMS[_en.lower()].append(_ko)

_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".search_translate_cache.json")
_mem_cache: dict[str, dict] = {}
_cache_loaded = False


def _load_cache() -> None:
    global _cache_loaded
    if _cache_loaded:
        return
    _cache_loaded = True
    try:
        if os.path.exists(_CACHE_PATH):
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _mem_cache.update(data)
    except Exception:
        pass


def _save_cache() -> None:
    try:
        # 최근 500개만 유지
        items = list(_mem_cache.items())[-500:]
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(dict(items), f, ensure_ascii=False)
    except Exception:
        pass


@dataclass
class SearchExpansion:
    query: str
    lang: str
    terms_ko: list[str] = field(default_factory=list)
    terms_en: list[str] = field(default_factory=list)
    all_terms: list[str] = field(default_factory=list)
    source: str = "dictionary"  # dictionary | llm | hybrid
    translated_query_en: str = ""
    translated_query_ko: str = ""

    def to_public(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "lang": self.lang,
            "terms_ko": self.terms_ko[:12],
            "terms_en": self.terms_en[:12],
            "source": self.source,
            "translated_query_en": self.translated_query_en,
            "translated_query_ko": self.translated_query_ko,
        }


def _uniq(seq: list[str], min_len: int = 2) -> list[str]:
    seen = set()
    out = []
    for s in seq:
        t = (s or "").strip()
        if len(t) < min_len:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _tokenize(query: str) -> list[str]:
    return [t for t in re.findall(r"[가-힣A-Za-z0-9']+", query or "") if len(t) >= 2]


def expand_from_dictionary(query: str) -> SearchExpansion:
    """사전만으로 KO↔EN 키워드 확장."""
    q = (query or "").strip()
    lang = detect_query_lang(q)
    tokens = _tokenize(q)
    terms_ko: list[str] = []
    terms_en: list[str] = []

    if lang == "KO":
        terms_ko.append(q)
        terms_ko.extend(tokens)
    else:
        terms_en.append(q)
        terms_en.extend(tokens)

    # 전체 구·부분 매칭
    ql = q.lower()
    for ko, ens in KO_TO_EN_TERMS.items():
        if ko in q or any(t == ko or (len(t) >= 2 and t in ko) for t in tokens):
            terms_ko.append(ko)
            terms_en.extend(ens)
    for en_key, kos in EN_TO_KO_TERMS.items():
        if en_key in ql or any(t.lower() == en_key or en_key in t.lower() for t in tokens):
            terms_en.append(en_key)
            terms_ko.extend(kos)

    # 책명
    for ko, en in KO_TO_EN_BOOK.items():
        if ko in q:
            terms_ko.append(ko)
            terms_en.append(en)
        if en.lower() in ql:
            terms_en.append(en)
            terms_ko.append(ko)

    terms_ko = _uniq(terms_ko)
    terms_en = _uniq(terms_en, min_len=3) if lang == "KO" else _uniq(terms_en)
    # EN 토큰은 2글자도 허용 (예: law)
    if lang != "KO":
        terms_en = _uniq(terms_en, min_len=2)

    all_terms = _uniq(terms_ko + terms_en, min_len=2)
    return SearchExpansion(
        query=q,
        lang=lang,
        terms_ko=terms_ko,
        terms_en=terms_en,
        all_terms=all_terms,
        source="dictionary",
        translated_query_en=" ".join(terms_en[:8]),
        translated_query_ko=" ".join(terms_ko[:8]),
    )


def _llm_expand(query: str, base: SearchExpansion) -> SearchExpansion | None:
    """LLM으로 성경 연구용 검색 키워드를 KO/EN으로 추출. 실패 시 None."""
    load_env()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    cache_key = hashlib.sha256(f"v1|{query.strip().lower()}".encode("utf-8")).hexdigest()
    _load_cache()
    hit = _mem_cache.get(cache_key)
    if hit and isinstance(hit, dict) and hit.get("terms_en"):
        base.terms_ko = _uniq(base.terms_ko + list(hit.get("terms_ko") or []))
        base.terms_en = _uniq(base.terms_en + list(hit.get("terms_en") or []), min_len=2)
        base.all_terms = _uniq(base.terms_ko + base.terms_en, min_len=2)
        base.source = "hybrid"
        base.translated_query_en = hit.get("translated_query_en") or " ".join(base.terms_en[:8])
        base.translated_query_ko = hit.get("translated_query_ko") or " ".join(base.terms_ko[:8])
        return base

    model = os.environ.get("SEARCH_TRANSLATE_MODEL") or os.environ.get(
        "RAG_MODEL", "deepseek/deepseek-v4-flash"
    )
    system = (
        "You extract bilingual search keywords for a biblical research database. "
        "Reply with JSON only, no markdown:\n"
        '{"terms_en":["..."],"terms_ko":["..."],"translated_query_en":"...","translated_query_ko":"..."}\n'
        "Rules: biblical/theological terms only; 3-10 keywords each side; "
        "include proper names; do not invent verse references."
    )
    user = f"User query: {query}"
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "ARK Search Translate",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": 300,
            },
            timeout=6,
        )
        if resp.status_code != 200:
            return None
        content = (((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        # JSON 블록만 추출
        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            return None
        data = json.loads(m.group(0))
        en = [str(x) for x in (data.get("terms_en") or []) if str(x).strip()]
        ko = [str(x) for x in (data.get("terms_ko") or []) if str(x).strip()]
        if not en and not ko:
            return None
        base.terms_en = _uniq(base.terms_en + en, min_len=2)
        base.terms_ko = _uniq(base.terms_ko + ko)
        base.all_terms = _uniq(base.terms_ko + base.terms_en, min_len=2)
        base.translated_query_en = str(data.get("translated_query_en") or "").strip() or " ".join(base.terms_en[:8])
        base.translated_query_ko = str(data.get("translated_query_ko") or "").strip() or " ".join(base.terms_ko[:8])
        base.source = "hybrid"
        _mem_cache[cache_key] = {
            "terms_en": en,
            "terms_ko": ko,
            "translated_query_en": base.translated_query_en,
            "translated_query_ko": base.translated_query_ko,
            "ts": time.time(),
        }
        _save_cache()
        return base
    except Exception:
        return None


def expand_query_for_search(query: str, use_llm: bool = True) -> SearchExpansion:
    """검색 파이프라인 진입점: 사전 우선, 부족할 때만 LLM (캐시되면 즉시)."""
    base = expand_from_dictionary(query)
    if not use_llm:
        return base
    # 이미 KO↔EN이 충분히 풀리면 LLM 생략 (빠른 검색)
    dict_ok = (
        (base.lang == "KO" and len(base.terms_en) >= 2)
        or (base.lang == "EN" and len(base.terms_ko) >= 1 and len(base.terms_en) >= 1)
    )
    if dict_ok:
        return base
    # 사전에 없으면 LLM으로 키워드 추출 (결과 파일 캐시)
    enriched = _llm_expand(query, base)
    return enriched or base
