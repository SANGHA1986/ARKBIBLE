"""공지사항 · 제보 · 어드민 API."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from database import get_db

router = APIRouter(prefix="/api", tags=["board"])


def _admin_key() -> str:
    return os.environ.get("ARK_ADMIN_KEY", "Hwang1718")


def require_admin(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")):
    if not x_admin_key or x_admin_key != _admin_key():
        raise HTTPException(status_code=401, detail="Admin key required")
    return True


def _notice_dict(n: models.Notice) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "pinned": bool(n.pinned),
        "published": bool(n.published),
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }


def _report_dict(r: models.FeedbackReport) -> dict:
    return {
        "id": r.id,
        "category": r.category,
        "title": r.title,
        "body": r.body,
        "contact": r.contact,
        "page_url": r.page_url,
        "search_query": r.search_query,
        "status": r.status,
        "admin_note": r.admin_note,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


class NoticeIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1)
    pinned: bool = False
    published: bool = True


class NoticePatch(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    pinned: Optional[bool] = None
    published: Optional[bool] = None


class ReportIn(BaseModel):
    category: str = Field(..., description="bug | data | feature")
    title: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1)
    contact: Optional[str] = None
    page_url: Optional[str] = None
    search_query: Optional[str] = None


class ReportStatusIn(BaseModel):
    status: str = Field(..., description="open | in_progress | done")
    admin_note: Optional[str] = None


@router.get("/notices")
def list_notices(
    db: Session = Depends(get_db),
    all: bool = False,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    q = db.query(models.Notice)
    if all:
        if not x_admin_key or x_admin_key != _admin_key():
            raise HTTPException(status_code=401, detail="Admin key required for all=true")
    else:
        q = q.filter(models.Notice.published.is_(True))
    rows = q.order_by(models.Notice.pinned.desc(), models.Notice.created_at.desc()).limit(100).all()
    return {"items": [_notice_dict(n) for n in rows]}


@router.get("/notices/{notice_id}")
def get_notice(notice_id: int, db: Session = Depends(get_db)):
    n = db.query(models.Notice).filter_by(id=notice_id).first()
    if not n or not n.published:
        raise HTTPException(404, "Notice not found")
    return _notice_dict(n)


@router.post("/admin/notices")
def create_notice(
    payload: NoticeIn,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    n = models.Notice(
        title=payload.title.strip(),
        body=payload.body.strip(),
        pinned=payload.pinned,
        published=payload.published,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return _notice_dict(n)


@router.patch("/admin/notices/{notice_id}")
def patch_notice(
    notice_id: int,
    payload: NoticePatch,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    n = db.query(models.Notice).filter_by(id=notice_id).first()
    if not n:
        raise HTTPException(404, "Notice not found")
    if payload.title is not None:
        n.title = payload.title.strip()
    if payload.body is not None:
        n.body = payload.body.strip()
    if payload.pinned is not None:
        n.pinned = payload.pinned
    if payload.published is not None:
        n.published = payload.published
    n.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(n)
    return _notice_dict(n)


@router.delete("/admin/notices/{notice_id}")
def delete_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    n = db.query(models.Notice).filter_by(id=notice_id).first()
    if not n:
        raise HTTPException(404, "Notice not found")
    db.delete(n)
    db.commit()
    return {"ok": True}


@router.post("/reports")
def create_report(payload: ReportIn, db: Session = Depends(get_db)):
    cat = (payload.category or "").strip().lower()
    if cat not in ("bug", "data", "feature"):
        raise HTTPException(400, "category must be bug | data | feature")
    r = models.FeedbackReport(
        category=cat,
        title=payload.title.strip(),
        body=payload.body.strip(),
        contact=(payload.contact or "").strip() or None,
        page_url=(payload.page_url or "").strip() or None,
        search_query=(payload.search_query or "").strip() or None,
        status="open",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"ok": True, "id": r.id}


@router.get("/admin/reports")
def list_reports(
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    status: Optional[str] = None,
):
    q = db.query(models.FeedbackReport)
    if status:
        q = q.filter(models.FeedbackReport.status == status)
    rows = q.order_by(models.FeedbackReport.created_at.desc()).limit(200).all()
    return {"items": [_report_dict(r) for r in rows]}


@router.patch("/admin/reports/{report_id}")
def patch_report(
    report_id: int,
    payload: ReportStatusIn,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    r = db.query(models.FeedbackReport).filter_by(id=report_id).first()
    if not r:
        raise HTTPException(404, "Report not found")
    st = payload.status.strip().lower()
    if st not in ("open", "in_progress", "done"):
        raise HTTPException(400, "status must be open | in_progress | done")
    r.status = st
    if payload.admin_note is not None:
        r.admin_note = payload.admin_note
    r.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(r)
    return _report_dict(r)


@router.get("/admin/ping")
def admin_ping(_: bool = Depends(require_admin)):
    return {"ok": True, "role": "admin"}


def _user_dict(u: models.User, include_admin: bool = True) -> dict:
    from user_profile import normalize_phone

    d = {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "organization": u.organization,
        "activity_region": u.activity_region,
        "occupation": u.occupation,
        "join_purpose": u.join_purpose,
        "phone": u.phone,
        "phone_digits": normalize_phone(u.phone or "") if u.phone else None,
        "withdrawn": bool(u.withdrawn),
        "withdrawn_at": u.withdrawn_at.isoformat() if u.withdrawn_at else None,
        "has_password": bool(u.password_hash),
        "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
    }
    if include_admin:
        d.update(
            {
                "tier": u.tier,
                "membership_status": u.membership_status,
                "daily_view_limit": u.daily_view_limit,
                "trial_started_at": u.trial_started_at.isoformat() if u.trial_started_at else None,
                "limited_started_at": u.limited_started_at.isoformat()
                if u.limited_started_at
                else None,
                "subscribed_until": u.subscribed_until.isoformat()
                if u.subscribed_until
                else None,
            }
        )
    return d


class MemberProfileIn(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    organization: Optional[str] = None
    activity_region: Optional[str] = None
    occupation: Optional[str] = None
    join_purpose: Optional[str] = None
    phone: Optional[str] = None
    tier: Optional[str] = None
    membership_status: Optional[str] = None
    daily_view_limit: Optional[int] = None
    subscribed_until: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class MePatchIn(BaseModel):
    password: Optional[str] = None  # 새 비밀번호 (선택)
    full_name: Optional[str] = None
    organization: Optional[str] = None
    activity_region: Optional[str] = None
    occupation: Optional[str] = None
    join_purpose: Optional[str] = None
    phone: Optional[str] = None


def _apply_profile_fields(u: models.User, data: dict, set_password: bool) -> None:
    from user_profile import hash_password, normalize_phone

    if data.get("full_name") is not None:
        u.full_name = str(data["full_name"]).strip()
    if data.get("organization") is not None:
        u.organization = str(data["organization"]).strip()
    if data.get("activity_region") is not None:
        u.activity_region = str(data["activity_region"]).strip()
    if data.get("occupation") is not None:
        u.occupation = str(data["occupation"]).strip()
    if data.get("join_purpose") is not None:
        u.join_purpose = str(data["join_purpose"]).strip()
    if data.get("phone") is not None:
        u.phone = normalize_phone(str(data["phone"]))
    if set_password and data.get("password"):
        u.password_hash = hash_password(str(data["password"]))


@router.get("/admin/users")
def list_users(
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    include_withdrawn: bool = True,
):
    q = db.query(models.User)
    if not include_withdrawn:
        q = q.filter((models.User.withdrawn.is_(False)) | (models.User.withdrawn.is_(None)))
    rows = q.order_by(models.User.id.desc()).limit(500).all()
    return {"items": [_user_dict(u) for u in rows]}


@router.post("/admin/users")
def create_user(
    payload: MemberProfileIn,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    from user_profile import validate_required_profile

    data = payload.model_dump()
    ok, msg = validate_required_profile(data, require_password=True)
    if not ok:
        raise HTTPException(400, msg)
    name = (payload.username or "").strip()
    if db.query(models.User).filter_by(username=name).first():
        raise HTTPException(400, "아이디가 이미 존재합니다.")
    status = (payload.membership_status or "Free_Trial").strip()
    allowed = {"Free_Trial", "Limited_24h", "Blocked", "Paid", "Institution"}
    if status not in allowed:
        raise HTTPException(400, f"membership_status must be one of {sorted(allowed)}")
    u = models.User(
        username=name,
        tier=(payload.tier or "Free").strip() or "Free",
        membership_status=status,
        daily_view_limit=payload.daily_view_limit if payload.daily_view_limit is not None else 20,
        withdrawn=False,
    )
    _apply_profile_fields(u, data, set_password=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return _user_dict(u)


@router.patch("/admin/users/{user_id}")
def patch_user(
    user_id: int,
    payload: MemberProfileIn,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    from user_profile import validate_phone

    u = db.query(models.User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(404, "User not found")
    data = payload.model_dump(exclude_unset=True)

    profile_keys = (
        "full_name",
        "organization",
        "activity_region",
        "occupation",
        "join_purpose",
        "phone",
    )
    if any(k in data for k in profile_keys) or data.get("password"):
        merged = {
            "full_name": data.get("full_name", u.full_name),
            "organization": data.get("organization", u.organization),
            "activity_region": data.get("activity_region", u.activity_region),
            "occupation": data.get("occupation", u.occupation),
            "join_purpose": data.get("join_purpose", u.join_purpose),
            "phone": data.get("phone", u.phone),
        }
        for label_key, label in [
            ("full_name", "성함"),
            ("organization", "소속"),
            ("activity_region", "활동지역"),
            ("occupation", "직업"),
            ("join_purpose", "가입목적"),
            ("phone", "휴대폰번호"),
        ]:
            if not str(merged.get(label_key) or "").strip():
                raise HTTPException(400, f"필수 항목이 비어 있습니다: {label}. 다시 작성해 주세요.")
        ok_p, msg_p = validate_phone(str(merged.get("phone") or ""))
        if not ok_p:
            raise HTTPException(400, msg_p)
        if data.get("password") and len(str(data["password"])) < 4:
            raise HTTPException(400, "패스워드는 4자 이상이어야 합니다.")

    if "password" in data and data["password"]:
        _apply_profile_fields(u, data, set_password=True)
    else:
        data.pop("password", None)
        _apply_profile_fields(u, data, set_password=False)

    if payload.tier is not None:
        u.tier = payload.tier.strip() or u.tier
    if payload.membership_status is not None:
        status = payload.membership_status.strip()
        allowed = {"Free_Trial", "Limited_24h", "Blocked", "Paid", "Institution"}
        if status not in allowed:
            raise HTTPException(400, f"membership_status must be one of {sorted(allowed)}")
        u.membership_status = status
        if status == "Limited_24h" and not u.limited_started_at:
            u.limited_started_at = datetime.utcnow()
    if payload.daily_view_limit is not None:
        u.daily_view_limit = max(0, int(payload.daily_view_limit))
    if payload.subscribed_until is not None:
        raw = payload.subscribed_until.strip()
        if not raw:
            u.subscribed_until = None
        else:
            try:
                if len(raw) <= 10:
                    u.subscribed_until = datetime.fromisoformat(raw + "T23:59:59")
                else:
                    u.subscribed_until = datetime.fromisoformat(raw.replace("Z", ""))
            except ValueError:
                raise HTTPException(400, "subscribed_until must be ISO date")
    u.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(u)
    return _user_dict(u)


@router.post("/admin/users/{user_id}/withdraw")
def withdraw_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    u = db.query(models.User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(404, "User not found")
    u.withdrawn = True
    u.withdrawn_at = datetime.utcnow()
    u.membership_status = "Blocked"
    u.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(u)
    return _user_dict(u)


@router.post("/admin/users/{user_id}/restore")
def restore_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    u = db.query(models.User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(404, "User not found")
    u.withdrawn = False
    u.withdrawn_at = None
    if u.membership_status == "Blocked":
        u.membership_status = "Free_Trial"
    u.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(u)
    return _user_dict(u)


def _user_from_auth(
    db: Session,
    x_username: Optional[str] = Header(None, alias="X-Username"),
    x_token: Optional[str] = Header(None, alias="X-User-Token"),
) -> models.User:
    from user_profile import verify_session_token

    if not x_username or not x_token:
        raise HTTPException(401, "로그인이 필요합니다.")
    u = db.query(models.User).filter_by(username=x_username.strip()).first()
    if not u or u.withdrawn:
        raise HTTPException(401, "탈퇴했거나 없는 계정입니다.")
    if not verify_session_token(u.username, u.password_hash, x_token):
        raise HTTPException(401, "세션이 만료되었거나 올바르지 않습니다. 다시 로그인해 주세요.")
    return u


@router.post("/auth/login")
def auth_login(payload: LoginIn, db: Session = Depends(get_db)):
    from user_profile import session_token, verify_password

    u = db.query(models.User).filter_by(username=payload.username.strip()).first()
    if not u or u.withdrawn:
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    if not verify_password(payload.password, u.password_hash):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    token = session_token(u.username, u.password_hash or "")
    return {"ok": True, "token": token, "user": _user_dict(u, include_admin=False)}


@router.post("/auth/register")
def auth_register(payload: MemberProfileIn, db: Session = Depends(get_db)):
    """베타 자가 가입 — 관리자 키 없이 Free_Trial 계정 생성."""
    from user_profile import validate_required_profile, session_token

    data = payload.model_dump()
    ok, msg = validate_required_profile(data, require_password=True)
    if not ok:
        raise HTTPException(400, msg)
    name = (payload.username or "").strip()
    if len(name) < 3:
        raise HTTPException(400, "아이디는 3자 이상이어야 합니다.")
    if db.query(models.User).filter_by(username=name).first():
        raise HTTPException(400, "아이디가 이미 존재합니다.")
    u = models.User(
        username=name,
        tier="Free",
        membership_status="Free_Trial",
        daily_view_limit=20,
        withdrawn=False,
    )
    _apply_profile_fields(u, data, set_password=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    token = session_token(u.username, u.password_hash or "")
    return {"ok": True, "token": token, "user": _user_dict(u, include_admin=False)}


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    x_username: Optional[str] = Header(None, alias="X-Username"),
    x_token: Optional[str] = Header(None, alias="X-User-Token"),
):
    u = _user_from_auth(db, x_username, x_token)
    return _user_dict(u, include_admin=False)


@router.patch("/me")
def patch_me(
    payload: MePatchIn,
    db: Session = Depends(get_db),
    x_username: Optional[str] = Header(None, alias="X-Username"),
    x_token: Optional[str] = Header(None, alias="X-User-Token"),
):
    from user_profile import validate_phone, session_token

    u = _user_from_auth(db, x_username, x_token)
    data = payload.model_dump(exclude_unset=True)
    merged = {
        "full_name": data.get("full_name", u.full_name),
        "organization": data.get("organization", u.organization),
        "activity_region": data.get("activity_region", u.activity_region),
        "occupation": data.get("occupation", u.occupation),
        "join_purpose": data.get("join_purpose", u.join_purpose),
        "phone": data.get("phone", u.phone),
    }
    for key, label in [
        ("full_name", "성함"),
        ("organization", "소속"),
        ("activity_region", "활동지역"),
        ("occupation", "직업"),
        ("join_purpose", "가입목적"),
        ("phone", "휴대폰번호"),
    ]:
        if not str(merged.get(key) or "").strip():
            raise HTTPException(400, f"필수 항목이 비어 있습니다: {label}. 다시 작성해 주세요.")
    ok_p, msg_p = validate_phone(str(merged.get("phone") or ""))
    if not ok_p:
        raise HTTPException(400, msg_p)
    if data.get("password"):
        if len(str(data["password"])) < 4:
            raise HTTPException(400, "패스워드는 4자 이상이어야 합니다.")
        _apply_profile_fields(u, data, set_password=True)
    else:
        data.pop("password", None)
        _apply_profile_fields(u, {**merged, **data}, set_password=False)
    u.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(u)
    # 비밀번호 변경 시 토큰 갱신
    new_token = session_token(u.username, u.password_hash or "")
    return {"user": _user_dict(u, include_admin=False), "token": new_token}


@router.post("/me/withdraw")
def me_withdraw(
    db: Session = Depends(get_db),
    x_username: Optional[str] = Header(None, alias="X-Username"),
    x_token: Optional[str] = Header(None, alias="X-User-Token"),
):
    u = _user_from_auth(db, x_username, x_token)
    u.withdrawn = True
    u.withdrawn_at = datetime.utcnow()
    u.membership_status = "Blocked"
    u.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


def seed_default_notice(db: Session) -> None:
    """첫 기동 시 안내 공지 1건 (없을 때만)."""
    if db.query(models.Notice).count() > 0:
        return
    n = models.Notice(
        title="베타 안내 · 번역본·수집 현황",
        body=(
            "ARK 테스트(베타) 안내입니다.\n\n"
            "1) 영문 본문: World English Bible(WEB, Public Domain) 거의 전권 적재.\n"
            "2) 한국어 본문: 개역한글(1961) Public Domain 약 31,101절 적재 "
            "(성경전서 개역한글판 · 대한성서공회 · digital NOTICE 확인분). "
            "개역개정 등 저작권 유효 역본은 미수록.\n"
            "3) 주석·연관구절·OA 논문(초록)은 라이선스 허용분만 단계 수집 중.\n\n"
            "오류·누락·수정안은 「제보하기」로 남겨 주세요."
        ),
        pinned=True,
        published=True,
    )
    db.add(n)
    db.commit()
