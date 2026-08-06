"""
ARK AI — 공개(Public Domain / Open License) 신학·원어 자료 수집기

소스:
  1) OpenScriptures Strong's (PD) — 헬라어/히브리어 Strong 번호
  2) STEPBible TBESG / TBESH (CC BY 4.0) — Extended Strong + 어원 요약
  3) Sefaria API — 구약 히브리어/영문 (텍스트별 라이선스 Mixed, 메타 보존)

중복 방지:
  - strong_number UNIQUE
  - lexicon_expansions UNIQUE(strong_number, lexicon_name, source_id)
  - sefaria_passages.ref_key UNIQUE
  - content_hash로 동일 페이로드 스킵

주의:
  - PD ≠ CC0. license_type에 원문 라이선스를 그대로 기록.
  - STEP은 반드시 "STEP Bible" + www.stepbible.org 귀속 표기.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import models
from database import SessionLocal, engine

DATA_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(DATA_DIR, exist_ok=True)

USER_AGENT = "ARK-AI-Collector/0.1 (+research; respectful crawl)"

SOURCES = {
    "STRONGS_OS_GREEK": {
        "code": "STRONGS_OS_GREEK",
        "title": "Strong's Greek Dictionary (OpenScriptures)",
        "author": "James Strong (1890)",
        "publisher": "OpenScriptures",
        "source_url": "https://github.com/openscriptures/strongs",
        "source_type": "Lexicon",
        "copyright_owner": "Public Domain",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "license_url": "https://github.com/openscriptures/strongs",
        "attribution_text": "Strong's Exhaustive Concordance (1890), Public Domain via OpenScriptures.",
        "commercial_use": True,
        "publication_year": 1890,
        "verification_status": "검증됨",
    },
    "STRONGS_OS_HEBREW": {
        "code": "STRONGS_OS_HEBREW",
        "title": "Strong's Hebrew Dictionary (OpenScriptures)",
        "author": "James Strong (1890)",
        "publisher": "OpenScriptures",
        "source_url": "https://github.com/openscriptures/strongs",
        "source_type": "Lexicon",
        "copyright_owner": "Public Domain",
        "copyright_status": "Public Domain",
        "license_type": "Public Domain",
        "license_url": "https://github.com/openscriptures/strongs",
        "attribution_text": "Strong's Exhaustive Concordance (1890), Public Domain via OpenScriptures.",
        "commercial_use": True,
        "publication_year": 1890,
        "verification_status": "검증됨",
    },
    "STEP_TBESG": {
        "code": "STEP_TBESG",
        "title": "TBESG — Translators Brief lexicon of Extended Strongs for Greek",
        "author": "Tyndale House / STEP Bible",
        "publisher": "STEPBible.org",
        "source_url": "https://github.com/STEPBible/STEPBible-Data",
        "source_type": "Lexicon",
        "copyright_owner": "STEP Bible / Tyndale House",
        "copyright_status": "CC BY 4.0",
        "license_type": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution_text": "Data by STEP Bible (www.stepbible.org), based on work at Tyndale House Cambridge (CC BY 4.0).",
        "commercial_use": True,
        "publication_year": 2020,
        "verification_status": "검증됨",
    },
    "STEP_TBESH": {
        "code": "STEP_TBESH",
        "title": "TBESH — Translators Brief lexicon of Extended Strongs for Hebrew",
        "author": "Tyndale House / STEP Bible",
        "publisher": "STEPBible.org",
        "source_url": "https://github.com/STEPBible/STEPBible-Data",
        "source_type": "Lexicon",
        "copyright_owner": "STEP Bible / Tyndale House",
        "copyright_status": "CC BY 4.0",
        "license_type": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution_text": "Data by STEP Bible (www.stepbible.org), based on work at Tyndale House Cambridge (CC BY 4.0). Incorporates abridged BDB linked to extended Strongs.",
        "commercial_use": True,
        "publication_year": 2020,
        "verification_status": "검증됨",
    },
    "SEFARIA": {
        "code": "SEFARIA",
        "title": "Sefaria Project API",
        "author": "Sefaria",
        "publisher": "Sefaria.org",
        "source_url": "https://www.sefaria.org",
        "source_type": "API",
        "copyright_owner": "Various (per text)",
        "copyright_status": "Mixed",
        "license_type": "Per-text (see Sefaria)",
        "license_url": "https://github.com/Sefaria/Sefaria-Export",
        "attribution_text": "Texts via Sefaria Project API (www.sefaria.org). Individual text licenses vary; metadata preserved.",
        "commercial_use": False,
        "publication_year": None,
        "verification_status": "미검증",
    },
}

URLS = {
    "STRONGS_OS_GREEK": "https://raw.githubusercontent.com/openscriptures/strongs/master/greek/strongs-greek-dictionary.js",
    "STRONGS_OS_HEBREW": "https://raw.githubusercontent.com/openscriptures/strongs/master/hebrew/strongs-hebrew-dictionary.js",
    "STEP_TBESG": "https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Lexicons/TBESG%20-%20Translators%20Brief%20lexicon%20of%20Extended%20Strongs%20for%20Greek%20-%20STEPBible.org%20CC%20BY.txt",
    "STEP_TBESH": "https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Lexicons/TBESH%20-%20Translators%20Brief%20lexicon%20of%20Extended%20Strongs%20for%20Hebrew%20-%20STEPBible.org%20CC%20BY.txt",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_strong(num: str, lang: str) -> str:
    num = num.strip().upper().replace(" ", "")
    if num.startswith("G") or num.startswith("H"):
        prefix, digits = num[0], re.sub(r"\D", "", num[1:])
    else:
        prefix = "G" if lang == "Greek" else "H"
        digits = re.sub(r"\D", "", num)
    if not digits:
        raise ValueError(f"bad strong number: {num}")
    return f"{prefix}{int(digits):04d}"


def download(url: str, dest: str, pause: float = 0.5) -> str:
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        print(f"[cache] {dest}")
        return dest
    print(f"[download] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    time.sleep(pause)
    return dest


def upsert_source(db: Session, meta: dict) -> models.SourceRegistry:
    row = db.query(models.SourceRegistry).filter_by(code=meta["code"]).first()
    if row:
        for k, v in meta.items():
            if k != "code":
                setattr(row, k, v)
        db.commit()
        return row
    row = models.SourceRegistry(**meta)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def upsert_strong(
    db: Session,
    *,
    strong_number: str,
    language_type: str,
    source_id: int,
    lemma: Optional[str] = None,
    transliteration: Optional[str] = None,
    pronunciation: Optional[str] = None,
    gloss: Optional[str] = None,
    definition_short: Optional[str] = None,
    definition_full: Optional[str] = None,
    morphology_hint: Optional[str] = None,
    root_word: Optional[str] = None,
) -> Tuple[str, bool]:
    payload = "|".join(
        [
            strong_number,
            lemma or "",
            transliteration or "",
            gloss or "",
            definition_short or "",
            definition_full or "",
        ]
    )
    content_hash = sha256_text(payload)
    existing = db.query(models.StrongEntry).filter_by(strong_number=strong_number).first()
    if existing:
        if existing.content_hash == content_hash:
            return "skip", False
        # 같은 소스면 갱신. OpenScriptures(PD Strong's)는 STEP 스텁보다 우선.
        prefer_os = False
        try:
            new_src = db.query(models.SourceRegistry).filter_by(id=source_id).first()
            old_src = existing.source
            if new_src and new_src.code.startswith("STRONGS_OS"):
                prefer_os = True
            if old_src and old_src.code.startswith("STRONGS_OS") and new_src and not new_src.code.startswith("STRONGS_OS"):
                return "exists_other_source", False
        except Exception:
            pass

        if existing.source_id == source_id or prefer_os:
            existing.lemma = lemma or existing.lemma
            existing.transliteration = transliteration or existing.transliteration
            existing.pronunciation = pronunciation or existing.pronunciation
            existing.gloss = gloss or existing.gloss
            existing.definition_short = definition_short or existing.definition_short
            existing.definition_full = definition_full or existing.definition_full
            existing.morphology_hint = morphology_hint or existing.morphology_hint
            existing.root_word = root_word or existing.root_word
            existing.source_id = source_id if prefer_os else existing.source_id
            existing.content_hash = content_hash
            db.flush()
            return "update", True
        return "exists_other_source", False

    row = models.StrongEntry(
        strong_number=strong_number,
        language_type=language_type,
        lemma=lemma,
        transliteration=transliteration,
        pronunciation=pronunciation,
        gloss=gloss,
        definition_short=definition_short,
        definition_full=definition_full,
        morphology_hint=morphology_hint,
        root_word=root_word,
        source_id=source_id,
        content_hash=content_hash,
    )
    db.add(row)
    try:
        db.flush()
        return "insert", True
    except IntegrityError:
        db.rollback()
        return "race_skip", False


def upsert_expansion(
    db: Session,
    *,
    strong_number: str,
    lexicon_name: str,
    entry_text: str,
    source_id: int,
) -> str:
    content_hash = sha256_text(entry_text)
    existing = (
        db.query(models.LexiconExpansion)
        .filter_by(strong_number=strong_number, lexicon_name=lexicon_name, source_id=source_id)
        .first()
    )
    if existing:
        if existing.content_hash == content_hash:
            return "skip"
        existing.entry_text = entry_text
        existing.content_hash = content_hash
        db.flush()
        return "update"
    row = models.LexiconExpansion(
        strong_number=strong_number,
        lexicon_name=lexicon_name,
        entry_text=entry_text,
        source_id=source_id,
        content_hash=content_hash,
    )
    db.add(row)
    try:
        db.flush()
        return "insert"
    except IntegrityError:
        db.rollback()
        return "race_skip"


def parse_openscriptures_js(path: str) -> Dict[str, dict]:
    """Parse OpenScriptures strongs-*-dictionary.js into { 'G1': {...}, ... }"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # strip JS assignment wrapper
    m = re.search(r"=\s*(\{[\s\S]*\})\s*;?\s*$", text)
    if not m:
        # try JSON-like object after first {
        start = text.find("{")
        end = text.rfind("}")
        raw = text[start : end + 1]
    else:
        raw = m.group(1)
    # keys may be unquoted numbers — normalize to JSON
    raw = re.sub(r"(\n\s*)(\d+)(\s*):", r'\1"\2"\3:', raw)
    raw = raw.replace("'", '"')
    # trailing commas
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # fallback: exec-safe via node-less regex entries
        data = {}
        for mm in re.finditer(
            r'"(\d+)"\s*:\s*\{([^}]*)\}',
            text,
        ):
            num = mm.group(1)
            body = mm.group(2)
            entry = {}
            for km in re.finditer(r'(lemma|xlit|pron|short|long|derivation)\s*:\s*"((?:\\.|[^"\\])*)"', body):
                entry[km.group(1)] = bytes(km.group(2), "utf-8").decode("unicode_escape")
            data[num] = entry
    return data


def ingest_openscriptures(db: Session, lang: str, limit: Optional[int] = None) -> dict:
    key = "STRONGS_OS_GREEK" if lang == "Greek" else "STRONGS_OS_HEBREW"
    src = upsert_source(db, SOURCES[key])
    path = download(URLS[key], os.path.join(DATA_DIR, f"{key}.js"))
    data = parse_openscriptures_js(path)
    stats = {"insert": 0, "update": 0, "skip": 0, "error": 0}
    prefix = "G" if lang == "Greek" else "H"
    for i, (num, entry) in enumerate(data.items()):
        if limit and i >= limit:
            break
        try:
            strong = normalize_strong(f"{prefix}{num}", lang)
            action, _ = upsert_strong(
                db,
                strong_number=strong,
                language_type=lang,
                source_id=src.id,
                lemma=entry.get("lemma"),
                transliteration=entry.get("xlit"),
                pronunciation=entry.get("pron"),
                gloss=entry.get("short"),
                definition_short=entry.get("short"),
                definition_full=entry.get("long") or entry.get("strongs_def") or entry.get("kjv_def"),
                root_word=entry.get("derivation"),
            )
            stats[action if action in stats else "skip"] = stats.get(action if action in stats else "skip", 0) + 1
            if action == "insert":
                stats["insert"] += 0  # already counted via get
        except Exception as e:
            stats["error"] += 1
            if stats["error"] <= 5:
                print(f"  ! {num}: {e}")
    # recount properly
    print(f"[Strong's {lang}] processed={min(len(data), limit or len(data))} stats~ {stats}")
    return stats


def ingest_openscriptures_v2(db: Session, lang: str, limit: Optional[int] = None) -> dict:
    key = "STRONGS_OS_GREEK" if lang == "Greek" else "STRONGS_OS_HEBREW"
    src = upsert_source(db, SOURCES[key])
    path = download(URLS[key], os.path.join(DATA_DIR, f"{key}.js"))
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    stats = {"insert": 0, "update": 0, "skip": 0, "exists_other_source": 0, "error": 0}
    # OpenScriptures format: "G26":{"lemma":"...","translit":"...","strongs_def":"..."}
    pattern = re.compile(
        r'"(?P<key>[GH]\d+)"\s*:\s*\{(?P<body>[^{}]+)\}',
        re.MULTILINE,
    )
    count = 0
    for m in pattern.finditer(text):
        if limit and count >= limit:
            break
        key_s = m.group("key")
        body = m.group("body")

        def field(name: str) -> Optional[str]:
            fm = re.search(rf'"{name}"\s*:\s*"((?:\\.|[^"\\])*)"', body)
            if not fm:
                return None
            try:
                return json.loads(f'"{fm.group(1)}"')
            except Exception:
                return fm.group(1)

        try:
            strong = normalize_strong(key_s, lang)
            action, _ = upsert_strong(
                db,
                strong_number=strong,
                language_type=lang,
                source_id=src.id,
                lemma=field("lemma"),
                transliteration=field("translit") or field("xlit"),
                pronunciation=field("pron"),
                gloss=field("kjv_def") or field("short"),
                definition_short=field("kjv_def") or field("short"),
                definition_full=field("strongs_def") or field("long"),
                root_word=field("derivation"),
            )
            stats[action] = stats.get(action, 0) + 1
            count += 1
            if count % 200 == 0:
                db.commit()
                print(f"  ... {lang} {count}", flush=True)
        except Exception as e:
            stats["error"] += 1
            if stats["error"] <= 3:
                print(f"  ! {key_s}: {e}", flush=True)
    db.commit()
    print(f"[Strong's {lang}] count={count} {stats}", flush=True)
    return stats


STEP_LINE_RE = re.compile(
    r"^(?P<estrong>[GH]\d+)\s+(?P<dstrong>\S+)\s+=\s+(?P<ustrong>\S+)\s+(?P<rest>.+)$"
)


def ingest_step_brief(db: Session, which: str, limit: Optional[int] = None) -> dict:
    """STEP TBESG/TBESH → lexicon_expansions (+ morph cross-ref hints)."""
    assert which in ("STEP_TBESG", "STEP_TBESH")
    src = upsert_source(db, SOURCES[which])
    path = download(URLS[which], os.path.join(DATA_DIR, f"{which}.txt"))
    lang = "Greek" if "GREEK" in which or which.endswith("TBESG") else "Hebrew"
    lexicon_name = "STEP_TBESG" if which == "STEP_TBESG" else "STEP_TBESH"
    # TBESH includes abridged BDB linkage — also tag as BDB_ABRIDGED_STEP
    bdb_tag = which == "STEP_TBESH"

    stats = {"insert": 0, "update": 0, "skip": 0, "error": 0, "morph": 0}
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if limit and count >= limit:
                break
            line = line.rstrip("\n")
            m = STEP_LINE_RE.match(line)
            if not m:
                continue
            try:
                strong = normalize_strong(m.group("estrong"), lang)
                rest = m.group("rest").strip()
                # crude gloss: first ASCII word cluster after lemma-ish tokens
                gloss_m = re.search(r"\b([A-Za-z][A-Za-z\-']{1,40})\b", rest)
                gloss = gloss_m.group(1) if gloss_m else None
                # ensure base strong row exists (don't overwrite OS definitions)
                existing = db.query(models.StrongEntry).filter_by(strong_number=strong).first()
                if not existing:
                    upsert_strong(
                        db,
                        strong_number=strong,
                        language_type=lang,
                        source_id=src.id,
                        gloss=gloss,
                        definition_short=rest[:500],
                        definition_full=rest,
                    )
                action = upsert_expansion(
                    db,
                    strong_number=strong,
                    lexicon_name=lexicon_name,
                    entry_text=rest,
                    source_id=src.id,
                )
                stats[action] = stats.get(action, 0) + 1
                if bdb_tag:
                    upsert_expansion(
                        db,
                        strong_number=strong,
                        lexicon_name="BDB_ABRIDGED_VIA_STEP",
                        entry_text=rest,
                        source_id=src.id,
                    )
                # dStrong / uStrong cross links
                dstrong = m.group("dstrong")
                ustrong = m.group("ustrong")
                for related, rel in ((dstrong, "dStrong"), (ustrong, "uStrong")):
                    try:
                        rel_n = normalize_strong(re.sub(r"[A-Za-z]$", "", related) if related[-1:].isalpha() and related[-1] not in "GH" else related, lang)
                        if rel_n != strong:
                            link = (
                                db.query(models.MorphologyLink)
                                .filter_by(
                                    strong_number=strong,
                                    related_strong=rel_n,
                                    relation_type=rel,
                                    source_id=src.id,
                                )
                                .first()
                            )
                            if not link:
                                db.add(
                                    models.MorphologyLink(
                                        strong_number=strong,
                                        related_strong=rel_n,
                                        relation_type=rel,
                                        source_id=src.id,
                                    )
                                )
                                db.commit()
                                stats["morph"] += 1
                    except Exception:
                        db.rollback()
                count += 1
                if count % 200 == 0:
                    db.commit()
                    print(f"  ... {which} {count}", flush=True)
            except Exception as e:
                db.rollback()
                stats["error"] += 1
                if stats["error"] <= 3:
                    print(f"  ! STEP line: {e}", flush=True)
    db.commit()
    print(f"[{which}] count={count} {stats}", flush=True)
    return stats


def ingest_sefaria(db: Session, refs: Optional[list] = None) -> dict:
    """Sefaria API — sample OT passages with license-aware metadata."""
    refs = refs or ["Genesis.1.1", "Genesis.1.2", "Exodus.3.14", "Psalms.23.1", "Isaiah.7.14"]
    src = upsert_source(db, SOURCES["SEFARIA"])
    stats = {"insert": 0, "update": 0, "skip": 0, "error": 0}
    for ref in refs:
        try:
            url = f"https://www.sefaria.org/api/texts/{ref}?context=0"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            he = data.get("he")
            en = data.get("text")
            if isinstance(he, list):
                he = "\n".join(he)
            if isinstance(en, list):
                en = "\n".join(en)
            he = he or ""
            en = en or ""
            note = f"license={data.get('license')}; versionTitle={data.get('versionTitle')}; versionSource={data.get('versionSource')}"
            payload = f"{ref}|{he}|{en}|{note}"
            content_hash = sha256_text(payload)
            existing = db.query(models.SefariaPassage).filter_by(ref_key=ref).first()
            if existing:
                if existing.content_hash == content_hash:
                    stats["skip"] += 1
                else:
                    existing.he_text = he
                    existing.en_text = en
                    existing.tradition_note = note
                    existing.title = data.get("ref") or ref
                    existing.content_hash = content_hash
                    db.commit()
                    stats["update"] += 1
            else:
                db.add(
                    models.SefariaPassage(
                        ref_key=ref,
                        title=data.get("ref") or ref,
                        he_text=he,
                        en_text=en,
                        tradition_note=note,
                        source_id=src.id,
                        content_hash=content_hash,
                    )
                )
                db.commit()
                stats["insert"] += 1
            time.sleep(0.4)
        except Exception as e:
            db.rollback()
            stats["error"] += 1
            print(f"  ! Sefaria {ref}: {e}")
    print(f"[Sefaria] {stats}")
    return stats


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # CLI: python collect_open_lexicons.py [--limit N] [--full]
    limit = 200
    if "--full" in sys.argv:
        limit = None
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        limit = int(sys.argv[i + 1])

    print("=== ARK Open Lexicon Collector ===", flush=True)
    print("License gate: COLLECT_POLICY - PD / CC BY only; Sefaria off unless --sefaria", flush=True)
    print(f"limit={limit} (use --full for all)", flush=True)
    try:
        from license_gate import assert_license_or_skip

        for code, meta in SOURCES.items():
            if code == "SEFARIA":
                continue
            ok, reason = assert_license_or_skip(meta.get("license_type"), meta.get("copyright_status"))
            if not ok:
                print(f"BLOCKED source config {code}: {reason}", flush=True)
                return

        ingest_openscriptures_v2(db, "Greek", limit=limit)
        ingest_openscriptures_v2(db, "Hebrew", limit=limit)
        ingest_step_brief(db, "STEP_TBESG", limit=limit)
        ingest_step_brief(db, "STEP_TBESH", limit=limit)
        if "--sefaria" in sys.argv:
            print("WARNING: Sefaria is Mixed/Per-text — metadata experiment only (COLLECT_POLICY: hold)", flush=True)
            ingest_sefaria(db)
        else:
            print("skip Sefaria (pass --sefaria to enable; not for commercial bulk ingest)", flush=True)
        total = db.query(models.StrongEntry).count()
        exp = db.query(models.LexiconExpansion).count()
        sef = db.query(models.SefariaPassage).count()
        print(f"DONE strong_entries={total} expansions={exp} sefaria={sef}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
