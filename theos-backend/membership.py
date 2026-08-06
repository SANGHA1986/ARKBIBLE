"""
멤버십 제어: Free_Trial(7일) → Limited_24h → Blocked
Paid / Institution 은 무제한(구독 만료 시 Blocked).

테스트/오픈베타: ARK_OPEN_BETA=1 (기본)이면 차단·한도 없이 허용.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models

TRIAL_DAYS = 7
LIMITED_HOURS = 24
LIMITED_DAILY_VIEWS = 20

# 테스트/오픈베타: 멤버십 차단 끔 (요금제 준비 전). 끄려면 ARK_OPEN_BETA=0
OPEN_BETA = os.environ.get("ARK_OPEN_BETA", "1").strip() not in ("0", "false", "False", "no")


@dataclass
class AccessDecision:
    allowed: bool
    status: str
    redirect_to_pricing: bool
    message: str
    trial_ends_at: Optional[datetime] = None
    limited_ends_at: Optional[datetime] = None
    remaining_views: Optional[int] = None


def _utcnow() -> datetime:
    return datetime.utcnow()


def ensure_membership_defaults(user: models.User) -> None:
    if not user.membership_status:
        user.membership_status = "Free_Trial"
    if not user.trial_started_at:
        user.trial_started_at = _utcnow()
    if user.daily_view_limit is None:
        user.daily_view_limit = LIMITED_DAILY_VIEWS


def refresh_membership_status(user: models.User, now: Optional[datetime] = None) -> str:
    """상태 전이만 수행. DB commit은 호출측 책임."""
    now = now or _utcnow()
    ensure_membership_defaults(user)

    if user.tier in ("Paid", "Institution") or user.membership_status == "Paid":
        if user.subscribed_until and user.subscribed_until < now:
            user.membership_status = "Blocked"
            user.tier = "Free"
            return user.membership_status
        user.membership_status = "Paid" if user.tier != "Institution" else "Institution"
        return user.membership_status

    if user.membership_status in ("Paid", "Institution"):
        return user.membership_status

    trial_end = user.trial_started_at + timedelta(days=TRIAL_DAYS)

    if user.membership_status == "Free_Trial":
        if now < trial_end:
            return "Free_Trial"
        user.membership_status = "Limited_24h"
        user.limited_started_at = now
        return "Limited_24h"

    if user.membership_status == "Limited_24h":
        started = user.limited_started_at or trial_end
        limited_end = started + timedelta(hours=LIMITED_HOURS)
        if now < limited_end:
            return "Limited_24h"
        user.membership_status = "Blocked"
        return "Blocked"

    return user.membership_status or "Blocked"


def _today_usage(db: Session, user: models.User) -> models.UserUsage:
    today = _utcnow().date().isoformat()
    usage = (
        db.query(models.UserUsage)
        .filter(models.UserUsage.user_id == user.id, models.UserUsage.date == today)
        .first()
    )
    if not usage:
        usage = models.UserUsage(user_id=user.id, date=today, request_count=0)
        db.add(usage)
        db.flush()
    return usage


def evaluate_access(db: Session, user: models.User, *, increment: bool = False) -> AccessDecision:
    if OPEN_BETA:
        ensure_membership_defaults(user)
        return AccessDecision(
            allowed=True,
            status=user.membership_status or "Free_Trial",
            redirect_to_pricing=False,
            message="open_beta",
        )

    status = refresh_membership_status(user)
    now = _utcnow()
    trial_end = (user.trial_started_at or now) + timedelta(days=TRIAL_DAYS)

    if status in ("Paid", "Institution", "Free_Trial"):
        if increment and status == "Free_Trial":
            usage = _today_usage(db, user)
            usage.request_count += 1
        return AccessDecision(
            allowed=True,
            status=status,
            redirect_to_pricing=False,
            message="ok",
            trial_ends_at=trial_end if status == "Free_Trial" else None,
        )

    if status == "Limited_24h":
        started = user.limited_started_at or trial_end
        limited_end = started + timedelta(hours=LIMITED_HOURS)
        usage = _today_usage(db, user)
        limit = user.daily_view_limit or LIMITED_DAILY_VIEWS
        remaining = max(0, limit - usage.request_count)
        if remaining <= 0:
            return AccessDecision(
                allowed=False,
                status=status,
                redirect_to_pricing=True,
                message="오늘 맛보기 조회 한도를 초과했습니다. 요금제를 선택하세요.",
                limited_ends_at=limited_end,
                remaining_views=0,
            )
        if increment:
            usage.request_count += 1
            remaining -= 1
        return AccessDecision(
            allowed=True,
            status=status,
            redirect_to_pricing=False,
            message="limited",
            limited_ends_at=limited_end,
            remaining_views=remaining,
        )

    return AccessDecision(
        allowed=False,
        status="Blocked",
        redirect_to_pricing=True,
        message="모든 자료를 제한 없이 보려면 요금제를 선택하세요.",
    )


def require_access(db: Session, user: models.User) -> AccessDecision:
    decision = evaluate_access(db, user, increment=not OPEN_BETA)
    db.commit()
    if not decision.allowed:
        raise HTTPException(
            status_code=402 if decision.redirect_to_pricing else 403,
            detail={
                "message": decision.message,
                "membership_status": decision.status,
                "redirect_to_pricing": decision.redirect_to_pricing,
                "pricing_path": "/pricing",
            },
        )
    return decision


def get_or_create_user(db: Session, username: str) -> models.User:
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        ensure_membership_defaults(user)
        if not OPEN_BETA:
            refresh_membership_status(user)
        db.commit()
        return user
    user = models.User(
        username=username,
        tier="Free",
        membership_status="Free_Trial",
        trial_started_at=_utcnow(),
        daily_view_limit=LIMITED_DAILY_VIEWS,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def decision_payload(decision: AccessDecision) -> dict:
    return {
        "membership_status": decision.status,
        "redirect_to_pricing": decision.redirect_to_pricing,
        "message": decision.message,
        "trial_ends_at": decision.trial_ends_at.isoformat() + "Z" if decision.trial_ends_at else None,
        "limited_ends_at": decision.limited_ends_at.isoformat() + "Z" if decision.limited_ends_at else None,
        "remaining_views": decision.remaining_views,
    }
