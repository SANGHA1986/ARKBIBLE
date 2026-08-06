"""
안전하지 않거나 출처가 불분명한 Source/Interpretation을 사용 차단.
삭제 대신 license.allow_ai_read=False 등으로 조회·AI 인용에서 제외.

규칙: COLLECT_POLICY.md / license_gate.py
"""
from __future__ import annotations

from database import SessionLocal
import models
from license_gate import BLOCK_STATUS, is_license_allowed

# 명시적으로 차단할 기존 시드 제목
EXPLICIT_BLOCK_TITLES = {
    "창세기 주석",  # 출처 불분명
    "가톨릭 교회 교리서",  # Copyrighted
    "Institutes of the Christian Religion (발췌 요약)",  # license status None
}


def block_source(db, src: models.Source) -> None:
    src.copyright_status = "Unsafe"
    lic = db.query(models.License).filter_by(source_id=src.id).first()
    if not lic:
        lic = models.License(source_id=src.id)
        db.add(lic)
    lic.allow_ai_read = False
    lic.allow_ai_summary = False
    lic.allow_ai_embedding = False
    lic.allow_ai_quote = False
    lic.allow_free_user = False
    lic.allow_paid_user = False
    lic.allow_institution = False
    lic.can_view_original = False
    lic.can_download = False
    lic.visibility_level = "Blocked"


def unblock_source(db, src: models.Source, restore_status: str = "Public Domain") -> None:
    lic = db.query(models.License).filter_by(source_id=src.id).first()
    if lic and is_license_allowed(lic.license_type):
        src.copyright_status = lic.license_type or restore_status
    else:
        src.copyright_status = restore_status
    if not lic:
        return
    lic.allow_ai_read = True
    lic.allow_ai_summary = True
    lic.allow_ai_embedding = True
    lic.allow_ai_quote = True
    lic.allow_free_user = True
    lic.allow_paid_user = True
    lic.allow_institution = True
    lic.can_view_original = True
    lic.visibility_level = "Public"


def main():
    db = SessionLocal()
    try:
        blocked = 0
        restored = 0
        for src in db.query(models.Source).all():
            status = (src.copyright_status or "").strip()
            lic_row = getattr(src, "license", None)
            lic_type = (lic_row.license_type if lic_row else "") or ""
            title = (src.title or "").strip()
            if title in EXPLICIT_BLOCK_TITLES:
                block_source(db, src)
                blocked += 1
                print(f"- blocked: {src.title} | explicit")
                continue
            # 이전에 오차단된 PD/CC BY 복구 (license_type이 허용이면)
            if status == "Unsafe" and is_license_allowed(lic_type):
                unblock_source(db, src)
                restored += 1
                print(f"+ restored: {src.title} | {lic_type}")
                continue
            should_block = False
            if status in BLOCK_STATUS:
                should_block = True
            elif not is_license_allowed(status) and not is_license_allowed(lic_type):
                should_block = True
            if should_block:
                block_source(db, src)
                blocked += 1
                print(f"- blocked: {src.title} | {status or 'NO STATUS'}")
        db.commit()
        print(f"OK blocked_sources={blocked} restored={restored}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
