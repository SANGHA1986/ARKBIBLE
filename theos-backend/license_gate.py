"""
ARK 수집 라이선스 게이트 — COLLECT_POLICY.md 와 동일 규칙.

허용: Public Domain / CC0 / CC BY (BY-SA·BY-NC 제외)
거부: BY-SA, BY-NC, Mixed, Per-text, Copyrighted, Unknown, Unsafe, 빈 값
"""
from __future__ import annotations

from typing import Optional, Tuple

# 사업(유지·수익·기부) 적재에 허용하는 라이선스 키워드
ALLOWED_SUBSTRINGS = (
    "public domain",
    "cc0",
    "cc-0",
    "cc 0",
    "pddl",
    "cc-by",
    "cc by",
    "ccby",
)

# 명시 거부 (허용 키워드보다 우선) — NC/비상업 포함
DENIED_SUBSTRINGS = (
    "by-sa",
    "by_sa",
    "bysa",
    "cc-by-sa",
    "cc by-sa",
    "cc by sa",
    "by-nc",
    "by_nc",
    "bync",
    "cc-by-nc",
    "cc by-nc",
    "cc by nc",
    "noncommercial",
    "non-commercial",
    "non commercial",
    "non-commerical",  # 흔한 오타
    "copyrighted",
    "all rights reserved",
    "unsafe",
    "unknown",
    "per-text",
    "per text",
    "mixed",
)

# copyright_status 필드용 차단 집합 (block_unsafe_sources 와 맞춤)
BLOCK_STATUS = {"Copyrighted", "None", "Unknown", "Unsafe", ""}

# 한국어 — 저작권 유효로 취급, 무단 수집 금지
FORBIDDEN_KO_VERSION_MARKERS = (
    "개역개정",
    "개정개역",
    "새번역",
    "공동번역",
    "현대인의성경",
    "쉬운성경",
    "우리말성경",
    "바른성경",
    "NRSV",  # 상용 계약 필요할 수 있음 — KO 수집기에서 혼입 방지용은 아님
)


def normalize_license(text: Optional[str]) -> str:
    s = (text or "").strip().lower().replace("_", "-")
    # public-domain / cc-by → 공백 형태로도 매칭
    return s.replace("-", " ")


def is_license_allowed(license_text: Optional[str]) -> bool:
    """라이선스 문자열이 사업 적재 허용인지."""
    s = normalize_license(license_text)
    if not s:
        return False
    # 거부: by-sa / by-nc 등 (공백 정규화 후) — 허용 매칭보다 우선
    compact = s.replace(" ", "")
    for d in DENIED_SUBSTRINGS:
        dn = d.replace("-", " ").replace("_", " ")
        if dn in s or d.replace("-", "") in compact:
            return False
    # NC 단독 표기 (creativecommons.org/.../nc/...)
    if "noncommercial" in compact or compact.endswith("nc") or "/nc/" in s.replace(" ", "/"):
        if "cc" in compact or "creative" in compact:
            return False
    if "sa" in compact and ("ccby" in compact or "creativecommons" in compact):
        # CC BY-SA
        if "ccby" in compact:
            return False
    for a in ALLOWED_SUBSTRINGS:
        an = a.replace("-", " ")
        if an in s or a.replace(" ", "") in compact:
            return True
    return False


def is_status_blocked(copyright_status: Optional[str]) -> bool:
    return (copyright_status or "").strip() in BLOCK_STATUS


def reject_reason(license_text: Optional[str], copyright_status: Optional[str] = None) -> Optional[str]:
    """거부 사유 문자열. 허용이면 None."""
    if copyright_status is not None and is_status_blocked(copyright_status):
        return f"blocked_status={copyright_status!r}"
    s = normalize_license(license_text)
    if not s:
        return "empty_license"
    if not is_license_allowed(license_text):
        return f"not_in_allowlist:{s[:80]}"
    return None


def assert_license_or_skip(
    license_text: Optional[str],
    copyright_status: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Returns (ok, message).
    ok=False 이면 수집기가 해당 항목을 스킵해야 함.
    """
    reason = reject_reason(license_text, copyright_status)
    if reason:
        return False, reason
    return True, "ok"


def looks_like_forbidden_ko_version(blob: str) -> bool:
    """텍스트/파일명에 저작권 유효 한국어 역본 표기가 있으면 True."""
    t = blob or ""
    for m in FORBIDDEN_KO_VERSION_MARKERS:
        if m in t:
            return True
    return False


def attribution_line(
    title: str = "",
    author: str = "",
    license_type: str = "",
    attribution_text: str = "",
    source_url: str = "",
) -> str:
    parts = []
    head = " — ".join(p for p in [title, author] if p)
    if head:
        parts.append(head)
    if license_type:
        parts.append(f"License: {license_type}")
    if attribution_text:
        parts.append(attribution_text)
    if source_url:
        parts.append(f"Source: {source_url}")
    return "\n".join(parts)
