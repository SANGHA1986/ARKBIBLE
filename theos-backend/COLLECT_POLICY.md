# ARK 수집 정책 (COLLECT_POLICY)

## 한 줄 원칙

> **성경·학술지·논문·연구자료·주석·사전이든 — 라이선스가 허용하는 범위 안에서만 사용한다.**  
> 사업(유지비·수익·기부)에도 쓸 수 있는지 확인한다. 애매하면 안 넣는다. 출처는 표기한다.

종류로 예외를 두지 않는다. “학술지라서”, “논문이라서”, “GitHub에 있어서”는 이유가 되지 않는다.

구현 게이트: [`license_gate.py`](license_gate.py)  
차단 유틸: [`block_unsafe_sources.py`](block_unsafe_sources.py)

---

## 등급

| 등급 | 라이선스 | 처리 |
|------|----------|------|
| OK | Public Domain(저작권 만료 포함), CC0 | 적재 + 출처·역본 표시 |
| OK+표기 | CC BY (예: 4.0) | 적재 + attribution 필수 |
| 보류 | CC BY-SA, CC BY-NC, Per-text 혼재, NOTICE 미확인 번들 | 전문 미적재 / 링크·메타만 |
| 금지 | 저작권 유효 유료·현대 역본, Copyrighted, Unsafe, Unknown, 빈 값 | 수집·RAG 주입 금지 |

**허용 문자열 예:** `Public Domain`, `CC0`, `CC0-1.0`, `CC BY`, `CC BY 4.0`, `CC-BY-4.0`  
**거부 예:** `CC BY-SA`, `CC BY-NC`, `Mixed`, `Per-text`, `Copyrighted`, `Unknown`, `Unsafe`, 빈 값

---

## 저작권 만료 번역본 (PD)

보호기간이 끝난 번역은 PD로 보고 직접 이용 가능하다. 필수 조건:

1. **판본명** 명시 (예: 개역한글 1961 — 개역개정과 혼동 금지)
2. NOTICE/공식 근거에 PD로 확인된 디지털 출처만
3. UI에 `역본명 · Public Domain · 출처` 표기
4. 저작권 유효 역본과 같은 필드에 섞지 않음

### 허용 예시

| 역본/자료 | 라이선스 | 수집기 |
|-----------|----------|--------|
| World English Bible (WEB) | PD | `collect_open_bible.py` |
| 개역한글 (1961) | PD (만료) | `collect_ko_pd_bible.py` (검증된 파일만) |
| KJV 등 명백한 PD 영문 | PD | 필요 시 추가 (WEB과 구분 표기) |

### 금지 예시

- 개역개정, 새번역, 현대어 등 **저작권 유효** 한국어 상용 역본 무단 수집

### 개역한글(1961) 검증 체크리스트

- [x] 디지털 파일이 **1961 개역한글**임을 출처 NOTICE/메타에 명시
- [x] 개역개정·혼합 텍스트가 아님을 샘플 구절로 확인
- [x] `Source`/`SourceRegistry`에 `copyright_status=Public Domain`, attribution·source_url 기록
- [x] UI·API에 역본명 `개역한글(1961)` 표시
- [x] crizin/bible-db 등은 **코드 MIT ≠ data 전부 OK** — NOTICE **항목별**로만 채택 (`data/krv`만)

로컬 적재: `data_ko_pd/`에 매니페스트 JSON + 본문 파일을 두고 `python collect_ko_pd_bible.py` 실행.  
일괄 GitHub dump import는 금지.

---

## 1차 허용 목록 (OK)

### 주석 (CC0) — OpenChristianData

- matthew-henry, jamieson-fausset-brown, adam-clarke, john-gill, wesley, keil-delitzsch  
- `collect_open_commentaries.py`

### 원어

- OpenScriptures Strong's — PD — `collect_open_lexicons.py`
- STEPBible TBESG/TBESH — CC BY 4.0 (attribution 필수)

### 연관 구절

- OpenBible.info — CC BY — `collect_cross_references.py`

### 성경 EN

- WEB — PD — `collect_open_bible.py`

### 자료 메타/요지

- `collect_open_materials.py` — PD / CC BY만. “summary seed”는 요약 시드 라벨 유지.

### 학술지·논문 (OA, 상업 이용 가능)

- **허용:** PD / CC0 / CC BY 만 (CC BY-NC·BY-SA·Unknown 거부)
- **적재 범위(1차):** 메타데이터 + 공개 초록(abstract) + 원문 URL — **전문 PDF 무단 적재 금지**
- **출처:** OpenAlex Works API (`is_oa` + 라이선스 게이트)
- **주제(1차):** 성경·신학·성경학 검색어 (이후 `--query`로 확장)
- **수집기:** `python collect_oa_papers.py` (`--limit`, `--query`, `--dry-run`)
- UI: 탐색 「자료·서적」에 `JournalArticle`로 표시, 어시스턴트는 등록 Source+Interpretation만 요약

---

## 보류

- crizin/bible-db `data/` **일괄** import (NOTICE 항목별 확인 전)
- Sefaria Per-text 혼재 → 기본 수집 **비활성** (`--sefaria`로만 메타 실험; 전문 직접 적재 금지)
- CC BY-SA
- CC BY-NC (비상업 — 사업/유지비·수익 모델과 충돌)
- 라이선스 불명 학술지 PDF 스크래핑

---

## 금지

- 개역개정 등 저작권 유효 역본 무단 수집
- 유료 주석/사전 전문·무단 paraphrase
- JSTOR 등 유료 DB 스크래핑
- `copyright_status` ∈ {Copyrighted, Unsafe, Unknown, None, ""}
- NOTICE 없거나 라이선스 불명 dump

---

## Attribution 템플릿

검색·어시스턴트·자료 상세에 가능하면 모두 표시:

```
{title} — {author}
License: {license_type}
{attribution_text}
Source: {source_url}
```

예시:

- Strong's: `Strong's Exhaustive Concordance (1890), Public Domain via OpenScriptures.`
- STEP: `Data by STEP Bible (www.stepbible.org), based on work at Tyndale House Cambridge (CC BY 4.0).`
- WEB: `World English Bible (Public Domain).`
- 개역한글: `개역한글(1961) · Public Domain · {디지털 출처 URL}`
- OpenBible: `Cross references from OpenBible.info (CC BY).`
- OA 논문: `{title} — {author}. License: {CC BY / CC0}. Via OpenAlex. {landing_url}`

---

## 사업 이용 체크리스트 (신규 소스 추가 시)

1. [ ] 공식 라이선스 문구를 확인했는가?
2. [ ] PD / CC0 / CC BY 중 하나인가? (BY-SA·BY-NC·Unknown이면 중단)
3. [ ] 상업·유료 서비스·기부 운영에 명시적으로 허용되는가? (NC가 아닌가?)
4. [ ] attribution / source_url을 DB·UI에 넣을 수 있는가?
5. [ ] 판본·전통(tradition) 라벨이 있는가?
6. [ ] `license_gate.is_license_allowed(...)`를 통과하는가?

---

## 수집 실행 순서

1. CC0 주석 우선 책 — `collect_open_commentaries.py`
2. Lexicon / crossref — `collect_open_lexicons.py` (Sefaria 기본 off), `collect_cross_references.py`
3. WEB 갭 + 검증된 개역한글 PD — `collect_open_bible.py`, `collect_ko_pd_bible.py`
4. Materials 카탈로그 — `collect_open_materials.py`
5. OA 학술지·논문(메타+초록) — `collect_oa_papers.py`

일괄: `collect_open_all.bat` (성경 본문은 별도 `collect_gaps.bat`)
