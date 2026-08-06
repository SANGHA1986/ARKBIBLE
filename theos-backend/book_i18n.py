"""성경 책명·인물명 KO/EN 표시."""
from __future__ import annotations

import re

KO_TO_EN_BOOK = {
    "창세기": "Genesis", "출애굽기": "Exodus", "레위기": "Leviticus", "민수기": "Numbers",
    "신명기": "Deuteronomy", "여호수아": "Joshua", "사사기": "Judges", "룻기": "Ruth",
    "사무엘상": "1 Samuel", "사무엘하": "2 Samuel", "열왕기상": "1 Kings", "열왕기하": "2 Kings",
    "역대상": "1 Chronicles", "역대하": "2 Chronicles", "에스라": "Ezra", "느헤미야": "Nehemiah",
    "에스더": "Esther", "욥기": "Job", "시편": "Psalms", "잠언": "Proverbs",
    "전도서": "Ecclesiastes", "아가": "Song of Solomon", "이사야": "Isaiah", "예레미야": "Jeremiah",
    "예레미야애가": "Lamentations", "에스겔": "Ezekiel", "다니엘": "Daniel", "호세아": "Hosea",
    "요엘": "Joel", "아모스": "Amos", "오바댜": "Obadiah", "요나": "Jonah",
    "미가": "Micah", "나훔": "Nahum", "하박국": "Habakkuk", "스바냐": "Zephaniah",
    "학개": "Haggai", "스가랴": "Zechariah", "말라기": "Malachi",
    "마태복음": "Matthew", "마가복음": "Mark", "누가복음": "Luke", "요한복음": "John",
    "사도행전": "Acts", "로마서": "Romans", "고린도전서": "1 Corinthians", "고린도후서": "2 Corinthians",
    "갈라디아서": "Galatians", "에베소서": "Ephesians", "빌립보서": "Philippians", "골로새서": "Colossians",
    "데살로니가전서": "1 Thessalonians", "데살로니가후서": "2 Thessalonians",
    "디모데전서": "1 Timothy", "디모데후서": "2 Timothy", "디도서": "Titus",
    "빌레몬서": "Philemon", "히브리서": "Hebrews", "야고보서": "James",
    "베드로전서": "1 Peter", "베드로후서": "2 Peter",
    "요한일서": "1 John", "요한이서": "2 John", "요한삼서": "3 John",
    "유다서": "Jude", "요한계시록": "Revelation",
}
EN_TO_KO_BOOK = {v: k for k, v in KO_TO_EN_BOOK.items()}

KO_TO_EN_CHAR = {
    "모세": "Moses", "아론": "Aaron", "다윗": "David", "솔로몬": "Solomon",
    "아브라함": "Abraham", "아담": "Adam", "노아": "Noah", "셋": "Seth",
    "예수": "Jesus", "바울": "Paul", "베드로": "Peter", "요한": "John",
    "사울": "Saul", "엘리야": "Elijah", "엘리사": "Elisha", "야곱": "Jacob", "요셉": "Joseph",
}
EN_TO_KO_CHAR = {v: k for k, v in KO_TO_EN_CHAR.items()}


def normalize_lang(lang: str | None) -> str:
    return "EN" if (lang or "").upper().startswith("EN") else "KO"


def book_display(ko_name: str, lang: str = "KO") -> str:
    if normalize_lang(lang) == "EN":
        return KO_TO_EN_BOOK.get(ko_name, ko_name)
    return ko_name


def char_display(ko_name: str, lang: str = "KO") -> str:
    if normalize_lang(lang) == "EN":
        return KO_TO_EN_CHAR.get(ko_name, ko_name)
    return ko_name


def verse_ref_display(book_ko: str, chapter: int, verse: int, lang: str = "KO") -> str:
    b = book_display(book_ko, lang)
    if normalize_lang(lang) == "EN":
        return f"{b} {chapter}:{verse}"
    return f"{book_ko} {chapter}:{verse}"


def detect_query_lang(query: str) -> str:
    """질문이 주로 영문이면 EN, 아니면 KO."""
    if not query:
        return "KO"
    latin = len(re.findall(r"[A-Za-z]", query))
    hangul = len(re.findall(r"[가-힣]", query))
    if latin > hangul * 2 and latin >= 8:
        return "EN"
    if hangul >= 2:
        return "KO"
    if latin >= 4:
        return "EN"
    return "KO"
