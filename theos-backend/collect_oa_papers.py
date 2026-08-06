"""
OpenAlex OA 학술지·논문 수집기 (상업 이용 가능 라이선스만)

원칙 (COLLECT_POLICY / license_gate):
  - Public Domain / CC0 / CC BY 만 (BY-NC·BY-SA·Unknown 거부)
  - 메타 + 공개 초록 + 원문 URL만 (전문 PDF 무단 적재 금지)
  - 주제 기본: 성경·신학·성경학

사용:
  python collect_oa_papers.py
  python collect_oa_papers.py --limit 80
  python collect_oa_papers.py --query "covenant baptism" --limit 40
  python collect_oa_papers.py --dry-run --limit 20
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

from sqlalchemy.orm import Session

import models
from database import SessionLocal
from license_gate import assert_license_or_skip, is_license_allowed

USER_AGENT = "ARK-OA-Collector/1.0 (mailto:ark@localhost; research)"
OPENALEX_WORKS = "https://api.openalex.org/works"

DEFAULT_QUERY = (
    'bible OR theology OR "biblical studies" OR "old testament" OR "new testament"'
)

# OpenAlex concepts: Theology, Biblical studies, Biblical theology, Hebrew Bible
CONCEPT_IDS = (
    "C27206212",   # Theology
    "C194105502",  # Biblical studies
    "C542772349",  # Biblical theology
    "C65264089",   # Hebrew Bible
)

TOPIC_HINTS = (
    "bible", "biblical", "theology", "theological", "testament",
    "scripture", "scriptural", "gospel", "exegesis", "hermeneutic",
    "ot ", "nt ", "hebrew bible", "septuagint", "pauline", "christology",
    "soteriology", "ecclesiology", "liturg", "sermon", "pastoral",
    "신학", "성경", "구약", "신약",
)

# OpenAlex primary_location.license / open_access.oa_url 등에서 추출한 문자열 정규화
LICENSE_ALIASES = {
    "cc-by": "CC BY",
    "cc-by-4.0": "CC BY 4.0",
    "cc-by-3.0": "CC BY 3.0",
    "cc-by-2.0": "CC BY 2.0",
    "cc-by-2.5": "CC BY 2.5",
    "cc-by-1.0": "CC BY 1.0",
    "cc0": "CC0",
    "cc-0": "CC0",
    "cc0-1.0": "CC0-1.0",
    "public-domain": "Public Domain",
    "pd": "Public Domain",
}


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("ascii", "replace"), flush=True)


def http_get_json(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def invert_abstract(inverted: Optional[dict]) -> str:
    """OpenAlex inverted abstract index → plain text."""
    if not inverted or not isinstance(inverted, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        if not isinstance(idxs, list):
            continue
        for i in idxs:
            try:
                positions.append((int(i), str(word)))
            except (TypeError, ValueError):
                continue
    if not positions:
        return ""
    positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in positions)


def normalize_license_label(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = raw.strip()
    # URL form: https://creativecommons.org/licenses/by/4.0/
    m = re.search(r"creativecommons\.org/licenses/([^/\s]+)/([^/\s]+)", s, re.I)
    if m:
        kind, ver = m.group(1).lower(), m.group(2)
        if kind == "by":
            return f"CC BY {ver}"
        if kind == "by-sa":
            return f"CC BY-SA {ver}"
        if kind.startswith("by-nc"):
            return f"CC BY-NC {ver}"
        if kind == "zero" or kind == "cc0":
            return "CC0"
    key = s.lower().replace("_", "-").strip()
    if key in LICENSE_ALIASES:
        return LICENSE_ALIASES[key]
    # already human label
    if is_license_allowed(s):
        return s
    return s


def extract_license(work: dict) -> tuple[str, str]:
    """Returns (license_label, license_url)."""
    candidates: list[tuple[str, str]] = []
    primary = work.get("primary_location") or {}
    if primary.get("license"):
        candidates.append((str(primary["license"]), primary.get("license_id") or ""))
    for loc in work.get("locations") or []:
        if loc.get("license"):
            candidates.append((str(loc["license"]), loc.get("license_id") or ""))
    oa = work.get("open_access") or {}
    # some records put license only on best_oa_location
    best = work.get("best_oa_location") or {}
    if best.get("license"):
        candidates.append((str(best["license"]), best.get("license_id") or ""))

    for raw, lic_id in candidates:
        label = normalize_license_label(raw) or normalize_license_label(lic_id)
        url = ""
        if isinstance(lic_id, str) and lic_id.startswith("http"):
            url = lic_id
        elif "creativecommons.org" in (raw or ""):
            url = raw
        if label and is_license_allowed(label):
            return label, url
        # try raw through gate
        if is_license_allowed(raw):
            return normalize_license_label(raw) or raw, url
    return "", ""


def authors_line(work: dict, limit: int = 5) -> str:
    names = []
    for a in (work.get("authorships") or [])[:limit]:
        author = (a.get("author") or {}).get("display_name") or ""
        if author:
            names.append(author)
    return ", ".join(names) if names else "Unknown"


def landing_url(work: dict) -> str:
    doi = work.get("doi") or ""
    if isinstance(doi, str) and doi.startswith("http"):
        return doi
    if isinstance(doi, str) and doi:
        return f"https://doi.org/{doi.replace('https://doi.org/', '')}"
    best = work.get("best_oa_location") or {}
    if best.get("landing_page_url"):
        return best["landing_page_url"]
    primary = work.get("primary_location") or {}
    if primary.get("landing_page_url"):
        return primary["landing_page_url"]
    ids = work.get("ids") or {}
    if ids.get("openalex"):
        return ids["openalex"]
    return work.get("id") or ""


def dedupe_key(title: str, author: str, doi_or_url: str) -> str:
    blob = f"{(doi_or_url or '').lower()}|{(title or '').lower()}|{(author or '').lower()}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def find_existing(db: Session, title: str, author: str, url: str) -> Optional[models.Source]:
    if url:
        hit = db.query(models.Source).filter(models.Source.source_url == url).first()
        if hit:
            return hit
    return (
        db.query(models.Source)
        .filter(models.Source.title == title[:200], models.Source.author == (author or "")[:100])
        .first()
    )


def ensure_license_row(
    db: Session,
    src: models.Source,
    license_type: str,
    license_url: str,
) -> None:
    existing = db.query(models.License).filter_by(source_id=src.id).first()
    if existing:
        existing.license_type = license_type
        if license_url:
            existing.license_url = license_url
        existing.commercial_use = True
        existing.allow_ai_read = True
        existing.allow_ai_summary = True
        existing.allow_ai_embedding = True
        existing.allow_ai_quote = True
        db.commit()
        return
    lic = models.License(
        source_id=src.id,
        license_type=license_type,
        license_url=license_url or src.source_url or "",
        commercial_use=True,
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


def is_junk_abstract(text: str) -> bool:
    """페이지 찌꺼기/네비게이션 잔여인 초록 감지."""
    if not text:
        return True
    t = text.strip()
    if len(t) < 200:
        return True
    junk_markers = (
        "Get access", "Search for other works", "Oxford Academic",
        "Log in", "Register", "Skip to", "Main menu",
        "Article navigation", "Sign in", "Subscribe", "This article is",
        "Download PDF", "View PDF",
    )
    hits = sum(1 for k in junk_markers if k in t)
    # 단어 수 적거나 마커 2개 이상이면 찌꺼기로 판정
    words = t.count(" ")
    return hits >= 2 or words < 20


def is_journal_as_paper(title: str, journal: str) -> bool:
    """저널 자체가 work로 들어온 항목 — title==journal 이면 스킵."""
    if not title or not journal:
        return False
    return title.strip().lower() == journal.strip().lower()


def upsert_paper(
    db: Session,
    *,
    title: str,
    author: str,
    year: Optional[int],
    url: str,
    license_type: str,
    license_url: str,
    abstract: str,
    journal: str,
    openalex_id: str,
    dry_run: bool,
) -> str:
    title = (title or "").strip()[:200]
    author = (author or "").strip()[:100]
    if not title:
        return "skip_no_title"

    ok, reason = assert_license_or_skip(license_type, license_type)
    if not ok:
        return f"reject:{reason}"

    abstract = (abstract or "").strip()
    if len(abstract) < 40:
        return "skip_no_abstract"

    existing = find_existing(db, title, author, url)
    if existing:
        return "skip_dup"

    desc = (
        f"OA journal article via OpenAlex. "
        f"Journal: {journal or '—'}. "
        f"License: {license_type}. "
        f"Abstract only (no full-text scrape). "
        f"OpenAlex: {openalex_id}"
    )
    tags = (
        f"논문, paper, journal, OA, OpenAlex, 학술, theology, bible, biblical, "
        f"{journal}, {license_type}"
    )[:500]

    if dry_run:
        log(f"  [dry-run] {title[:70]} | {license_type} | {url[:60]}")
        return "dry_run"

    src = models.Source(
        title=title,
        author=author,
        publisher=(journal or "OpenAlex OA")[:100],
        source_url=url[:500],
        source_type="JournalArticle",
        tags=tags,
        description=desc[:2000],
        copyright_owner=author[:100] if author else None,
        copyright_status=license_type[:50],
        publication_year=year,
        academic_level="A",
        verification_status="OpenAlex-OA",
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    ensure_license_row(db, src, license_type, license_url)

    claim = f"{title}"
    evidence = abstract[:4000]
    interp = models.Interpretation(
        viewpoint="학술(OA)",
        claim=claim[:2000],
        evidence=evidence,
        scholar_name=author[:100] if author else "OA author",
        source_id=src.id,
        verse_id=None,
    )
    db.add(interp)
    db.commit()
    return "insert"


def is_topic_relevant(title: str, abstract: str, concepts: list) -> bool:
    """신학·성경학 관련성 — concept 또는 제목/초록 힌트."""
    concept_ids = set()
    for c in concepts or []:
        cid = (c.get("id") or "").split("/")[-1]
        if cid:
            concept_ids.add(cid)
        # also accept if display_name hints theology
        name = (c.get("display_name") or "").lower()
        if any(h in name for h in ("theolog", "biblical", "bible", "scripture", "religion")):
            return True
    if concept_ids.intersection(CONCEPT_IDS):
        return True
    blob = f"{title or ''} {abstract or ''}".lower()
    return any(h in blob for h in TOPIC_HINTS)


def fetch_works(query: str, per_page: int = 50, cursor: Optional[str] = None) -> dict:
    # Concept 필터로 신학·성경학 중심 + is_oa + article
    concept_filter = "|".join(CONCEPT_IDS)
    params = {
        "search": query,
        "filter": f"is_oa:true,type:article,concepts.id:{concept_filter}",
        "per_page": str(per_page),
        "sort": "cited_by_count:desc",
    }
    if cursor:
        params["cursor"] = cursor
    else:
        params["cursor"] = "*"
    url = OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)
    return http_get_json(url)


def collect(db: Session, query: str, limit: int, dry_run: bool) -> dict:
    stats = {"insert": 0, "skip_dup": 0, "skip_no_abstract": 0, "reject": 0, "dry_run": 0, "fail": 0}
    seen_keys: set[str] = set()
    cursor: Optional[str] = None
    fetched = 0
    pages = 0
    max_pages = max(3, (limit // 25) + 3)

    while stats["insert"] + stats["dry_run"] < limit and pages < max_pages:
        pages += 1
        try:
            data = fetch_works(query, per_page=min(50, max(limit, 25)), cursor=cursor)
        except Exception as e:
            log(f"OpenAlex fetch error: {e}")
            stats["fail"] += 1
            break

        results = data.get("results") or []
        if not results:
            log("no more results")
            break

        for work in results:
            if stats["insert"] + stats["dry_run"] >= limit:
                break
            fetched += 1
            try:
                title = (work.get("display_name") or work.get("title") or "").strip()
                author = authors_line(work)
                url = landing_url(work)
                lic_label, lic_url = extract_license(work)
                if not lic_label:
                    stats["reject"] += 1
                    continue
                ok, reason = assert_license_or_skip(lic_label)
                if not ok:
                    stats["reject"] += 1
                    continue

                abstract = invert_abstract(work.get("abstract_inverted_index"))
                year = work.get("publication_year")
                try:
                    year_i = int(year) if year is not None else None
                except (TypeError, ValueError):
                    year_i = None

                primary = work.get("primary_location") or {}
                source = primary.get("source") or {}
                journal = source.get("display_name") or ""
                openalex_id = work.get("id") or ""

                # 저널 자체가 work로 들어온 항목 스킵
                if is_journal_as_paper(title, journal):
                    stats["reject"] += 1
                    continue
                if is_junk_abstract(abstract):
                    stats["skip_no_abstract"] += 1
                    continue

                if not is_topic_relevant(title, abstract, work.get("concepts") or []):
                    stats["reject"] += 1
                    continue

                key = dedupe_key(title, author, url)
                if key in seen_keys:
                    stats["skip_dup"] += 1
                    continue
                seen_keys.add(key)

                status = upsert_paper(
                    db,
                    title=title,
                    author=author,
                    year=year_i,
                    url=url,
                    license_type=lic_label,
                    license_url=lic_url,
                    abstract=abstract,
                    journal=journal,
                    openalex_id=openalex_id,
                    dry_run=dry_run,
                )
                if status == "insert":
                    stats["insert"] += 1
                    log(f"  + {title[:72]}")
                elif status == "dry_run":
                    stats["dry_run"] += 1
                elif status == "skip_dup":
                    stats["skip_dup"] += 1
                elif status == "skip_no_abstract":
                    stats["skip_no_abstract"] += 1
                elif status.startswith("reject"):
                    stats["reject"] += 1
                else:
                    stats["fail"] += 1
            except Exception as e:
                stats["fail"] += 1
                log(f"  fail: {e}")

        meta = data.get("meta") or {}
        next_cursor = meta.get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.2)

    log(f"fetched_candidates≈{fetched} pages={pages}")
    return stats


def main() -> None:
    args = sys.argv[1:]
    limit = 80
    query = DEFAULT_QUERY
    dry_run = "--dry-run" in args
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--query" in args:
        query = args[args.index("--query") + 1]

    log("=== ARK OA Papers Collector (OpenAlex) ===")
    log("Policy: PD/CC0/CC BY only — no BY-NC/BY-SA; abstract+meta only")
    log(f"query={query!r} limit={limit} dry_run={dry_run}")

    db = SessionLocal()
    try:
        stats = collect(db, query=query, limit=limit, dry_run=dry_run)
        n = (
            db.query(models.Source)
            .filter(models.Source.source_type == "JournalArticle")
            .count()
        )
        log(f"DONE JournalArticle sources={n} | stats={stats}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
