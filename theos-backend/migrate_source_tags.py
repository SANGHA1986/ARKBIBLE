"""Add Source.tags and Source.description columns if missing."""
from __future__ import annotations

from sqlalchemy import text
from database import engine


def main():
    with engine.begin() as conn:
        for col in ["tags", "description"]:
            try:
                conn.execute(text(f"ALTER TABLE sources ADD COLUMN {col} VARCHAR(500)"))
                print(f"+ added column: {col}")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"= column exists: {col}")
                else:
                    print(f"! {col}: {e}")
    print("OK")


if __name__ == "__main__":
    main()
