"""Fetch priority WEB chapters that were missing (e.g. Genesis 4)."""
import time
import collect_open_bible as c
from database import SessionLocal

EXTRA = {
    "genesis": list(range(4, 12)),
    "matthew": [2, 3, 4, 7],
    "john": [2, 4],
    "romans": [2, 4, 6, 7],
    "1samuel": [17],
}


def main():
    db = SessionLocal()
    try:
        c.ensure_registry(db)
        for slug, chapters in EXTRA.items():
            ko = next(x[1] for x in c.BOOKS if x[0] == slug)
            testament = next(x[2] for x in c.BOOKS if x[0] == slug)
            book = c.ensure_book(db, ko, testament)
            for ch in chapters:
                try:
                    verses = c.fetch_chapter(slug, ch)
                    for v in verses:
                        c.upsert_verse(
                            db, book, int(v["chapter"]), int(v["verse"]), v["text"].strip()
                        )
                    db.commit()
                    print(f"+ {ko} {ch} ({len(verses)})")
                    time.sleep(0.5)
                except Exception as e:
                    db.rollback()
                    print(f"! {slug} {ch}: {e}")
                    time.sleep(2)
        print("done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
