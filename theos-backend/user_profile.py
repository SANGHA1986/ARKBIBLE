"""회원 프로필·비밀번호·휴대폰 검증."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from typing import Optional, Tuple

# 연속 숫자(오름/내림) 4자리 이상
_ASC = "0123456789"
_DESC = "9876543210"
_FORBIDDEN_PHONE_CHUNKS = ("0000", "1000", "2222")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(8)
    dig = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}${dig}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored)


def session_token(username: str, password_hash: str) -> str:
    secret = os.environ.get("ARK_ADMIN_KEY", "Hwang1718")
    raw = f"{username}|{password_hash}|{secret}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_session_token(username: str, password_hash: Optional[str], token: str) -> bool:
    if not password_hash or not token:
        return False
    return hmac.compare_digest(session_token(username, password_hash), token)


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def validate_phone(phone: str) -> Tuple[bool, str]:
    """
    휴대폰 규칙:
    - 숫자만(하이픈 제거) 10~11자리
    - 0000 / 1000 / 2222 포함 불가
    - 연속된 숫자 4자리(1234, 5678, 9876 등) 불가
    """
    digits = normalize_phone(phone)
    if len(digits) < 10 or len(digits) > 11:
        return False, "휴대폰 번호는 숫자 10~11자리여야 합니다."
    if not digits.startswith(("010", "011", "016", "017", "018", "019")):
        return False, "휴대폰 번호 형식이 올바르지 않습니다."
    for chunk in _FORBIDDEN_PHONE_CHUNKS:
        if chunk in digits:
            return False, f"휴대폰 번호에 '{chunk}' 패턴을 쓸 수 없습니다. 다시 입력해 주세요."
    for i in range(len(digits) - 3):
        part = digits[i : i + 4]
        if part in _ASC or part in _DESC:
            return False, "연속된 숫자(예: 1234, 9876)는 사용할 수 없습니다. 다시 입력해 주세요."
    return True, ""


REQUIRED_PROFILE_FIELDS = (
    ("username", "아이디"),
    ("password", "패스워드"),
    ("full_name", "성함"),
    ("organization", "소속"),
    ("activity_region", "활동지역"),
    ("occupation", "직업"),
    ("join_purpose", "가입목적"),
    ("phone", "휴대폰번호"),
)


def validate_required_profile(data: dict, require_password: bool = True) -> Tuple[bool, str]:
    """하나라도 비어 있으면 재작성 요구."""
    checks = [
        ("username", "아이디"),
        ("full_name", "성함"),
        ("organization", "소속"),
        ("activity_region", "활동지역"),
        ("occupation", "직업"),
        ("join_purpose", "가입목적"),
        ("phone", "휴대폰번호"),
    ]
    if require_password:
        checks.insert(1, ("password", "패스워드"))
    missing = []
    for key, label in checks:
        val = data.get(key)
        if val is None or str(val).strip() == "":
            missing.append(label)
    if missing:
        return False, f"필수 항목이 비어 있습니다: {', '.join(missing)}. 다시 작성해 주세요."
    ok, msg = validate_phone(str(data.get("phone") or ""))
    if not ok:
        return False, msg
    pw = str(data.get("password") or "")
    if require_password and len(pw) < 4:
        return False, "패스워드는 4자 이상이어야 합니다."
    uname = str(data.get("username") or "").strip()
    if require_password and (len(uname) < 2 or not re.match(r"^[A-Za-z0-9_\-.]+$", uname)):
        return False, "아이디는 영문·숫자·_-. 만 사용 (2자 이상)."
    return True, ""
