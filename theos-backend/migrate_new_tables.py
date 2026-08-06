"""Create new tables: commentaries, cross_references."""
from __future__ import annotations

from database import engine, Base
import models


def main():
    # models 모듈 임포트로 메타데이터 등록
    Base.metadata.create_all(bind=engine, tables=[
        models.Commentary.__table__,
        models.CrossReference.__table__,
    ])
    print("OK tables created: commentaries, cross_references")


if __name__ == "__main__":
    main()
