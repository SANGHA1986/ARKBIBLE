"""
안전하지 않거나 중복된 Source/Interpretation 정리.
- copyright_status가 허용 목록에 없는 source 삭제
- 관련 interpretation 삭제
- 개인/공개 JSON은 보존 (재수집하면 됨)
"""
from __future__ import annotations

from database import SessionLocal
import models

ALLOWED_STATUS = {
    "Public Domain",
    "Public Domain summary",
    "Public Domain summary seed",
    "CC BY 4.0",
    "CC0",
    "Personal Open",
    "Open",
    "CC BY",
    "MIT",
    "Apache-2.0",
}

# 명시적으로 제거할 기존 시드 (제목 기준)
EXPLICIT_REMOVE_TITLES = {
    "창세기 주석",  # 출처 불분명
    "가톨릭 교회 교리서",  # Copyrighted
    "Institutes of the Christian Religion (발췌 요약)",  # copyright_status None
}


def main():
    db = SessionLocal()
    try:
        # 1) 허용 목록 밖인 source
        bad_sources = []
        for src in db.query(models.Source).all():
            status = (src.copyright_status or "").strip()
            if status and status not in ALLOWED_STATUS:
                bad_sources.append(src)
            elif src.title.strip() in EXPLICIT_REMOVE_TITLES:
                bad_sources.append(src)
            elif not status:
                # 빈 상태도 제거 (안전을 위해)
                bad_sources.append(src)

        removed = 0
        interp_removed = 0
        lic_removed = 0
        for src in bad_sources:
            # 관련 interpretation 먼저 삭제
            interps = db.query(models.Interpretation).filter_by(source_id=src.id).all()
            for interp in interps:
                db.delete(interp)
                interp_removed += 1
            # license 삭제 (source_id NOT NULL)
            lic = db.query(models.License).filter_by(source_id=src.id).first()
            if lic:
                db.delete(lic)
                lic_removed += 1
            db.delete(src)
            removed += 1
            print(f"- removed source: {src.title} | {src.copyright_status or 'NO STATUS'}")

        db.commit()
        print(f"OK removed_sources={removed} removed_interpretations={interp_removed} removed_licenses={lic_removed}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
