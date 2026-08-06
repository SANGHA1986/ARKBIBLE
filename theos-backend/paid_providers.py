"""
유료 학술 DB 연동 — 설계 스텁 (구현 보류)

원칙:
  - Proxy 로그인 / 계정 공유 금지. 기관·상용 라이선스만.
  - 모든 적재 레코드는 source_registry FK + 라이선스 메타 필수.
  - 공개(PD/CC) 레이어와 유료 레이어를 쿼리/권한에서 분리.
  - 유료 전문은 클라이언트에 통째로 내보내지 않음 (서버 측 게이트 + 안티 유출).

수집 채널 (유료 도입 시 모두 지원 예정):
  1) JSON/REST API  — 정식 벤더 API (메타·초록·허용된 전문)
  2) PDF 파일       — 라이선스된 파일 입고 → 파싱/페이지 단위 인덱싱
  3) OCR            — 스캔본 PDF/이미지 → 텍스트 추출 후 동일 스키마로 정규화
  ※ 스크래핑·타인 계정 공유로 가져오는 경로는 금지.

안티 유출 (유료 레이어):
  - membership 게이트: Free는 제목/메타(계약 허용 범위)만
  - 전문은 HTML 조각 스트리밍, 일괄 download/export API 없음(또는 감사 로그+쿼터)
  - allow_ai_quote / allow_export / allow_copy 플래그로 AI·복제 차단
  - 사용자·세션 워터마크, 비정상 대량 조회 rate-limit
  - 유료 전문을 공개 검색 인덱스의 통짜 스니펫으로 노출하지 않음

예정 프로바이더 (우선순위는 런칭 후 결정):
  1) DBpia / RISS  — 국내 신학·역사 논문
  2) ATLA Religion Database
  3) JSTOR Religion / Humanities
  4) Brill / Brepols / De Gruyter  — 기관 요금제 고가 티어

이 파일은 NotImplemented. 실제 HTTP/스크래핑 코드 넣지 말 것.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PaidProviderCode(str, Enum):
    DBPIA = "DBPIA"
    RISS = "RISS"
    ATLA = "ATLA"
    JSTOR = "JSTOR"
    BRILL = "BRILL"
    BREPOLS = "BREPOLS"
    DEGRUYTER = "DEGRUYTER"


class IngestChannel(str, Enum):
    """유료/기관 자료 입고 경로."""

    JSON_API = "JSON_API"  # 정식 REST/GraphQL 등
    PDF_FILE = "PDF_FILE"  # 라이선스 PDF 입고
    OCR = "OCR"  # 스캔본 → OCR → 텍스트


# source_registry.code 예약값 (수집 시 이 코드로 등록)
RESERVED_SOURCE_CODES = {
    PaidProviderCode.DBPIA: "PAID_DBPIA",
    PaidProviderCode.RISS: "PAID_RISS",
    PaidProviderCode.ATLA: "PAID_ATLA",
    PaidProviderCode.JSTOR: "PAID_JSTOR",
    PaidProviderCode.BRILL: "PAID_BRILL",
    PaidProviderCode.BREPOLS: "PAID_BREPOLS",
    PaidProviderCode.DEGRUYTER: "PAID_DEGRUYTER",
}


@dataclass
class ContentProtectionPolicy:
    """유료 콘텐츠가 ‘퍼가지 못하게’ 서버에서 강제할 정책 플래그."""

    layer: str = "paid"  # open | paid
    allow_free_preview: bool = False  # 제목·초록 수준
    allow_fulltext_api: bool = False  # 전문 JSON 일괄 제공 금지 기본
    allow_bulk_export: bool = False
    allow_ai_read: bool = False
    allow_ai_quote: bool = False
    allow_client_copy: bool = False  # UI 복사 제한(완전 차단은 불가, 억제)
    watermark_user: bool = True
    max_pages_per_minute: int = 20
    require_auth: bool = True


DEFAULT_PAID_PROTECTION = ContentProtectionPolicy()


@dataclass
class PaidRecord:
    provider: PaidProviderCode
    external_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    landing_url: Optional[str] = None
    license_note: str = "Copyrighted — institutional license required"
    ingest_channel: IngestChannel = IngestChannel.JSON_API
    allow_ai_quote: bool = False
    allow_free_user: bool = False
    protection: ContentProtectionPolicy = field(default_factory=ContentProtectionPolicy)


class PaidProvider(ABC):
    code: PaidProviderCode

    @abstractmethod
    def connect(self, **credentials) -> None:
        """정식 API 키 / 기관 토큰. Proxy·개인 계정 공유 금지."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, *, limit: int = 20) -> List[PaidRecord]:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, external_id: str) -> PaidRecord:
        raise NotImplementedError

    def ingest_from_pdf(self, path: str, *, license_meta: dict) -> PaidRecord:
        """라이선스된 PDF 입고. 구현 시 페이지 단위 인덱싱 + protection 부착."""
        raise NotImplementedError(f"{self.code}: PDF ingest not implemented")

    def ingest_from_ocr(self, image_or_pdf_path: str, *, license_meta: dict) -> PaidRecord:
        """OCR 파이프라인 입고. 텍스트 품질 메타(confidence) 저장 예정."""
        raise NotImplementedError(f"{self.code}: OCR ingest not implemented")

    def ingest_from_json_api(self, payload: dict, *, license_meta: dict) -> PaidRecord:
        """정식 API JSON → ARK 스키마 정규화."""
        raise NotImplementedError(f"{self.code}: JSON API ingest not implemented")


class DBpiaProvider(PaidProvider):
    code = PaidProviderCode.DBPIA

    def connect(self, **credentials) -> None:
        raise NotImplementedError("DBpia: 정식 API/기관계약 후 구현")

    def search(self, query: str, *, limit: int = 20) -> List[PaidRecord]:
        raise NotImplementedError

    def fetch(self, external_id: str) -> PaidRecord:
        raise NotImplementedError


class AtlaProvider(PaidProvider):
    code = PaidProviderCode.ATLA

    def connect(self, **credentials) -> None:
        raise NotImplementedError("ATLA: 정식 라이선스 후 구현")

    def search(self, query: str, *, limit: int = 20) -> List[PaidRecord]:
        raise NotImplementedError

    def fetch(self, external_id: str) -> PaidRecord:
        raise NotImplementedError


class JstorProvider(PaidProvider):
    code = PaidProviderCode.JSTOR

    def connect(self, **credentials) -> None:
        raise NotImplementedError("JSTOR: 정식 라이선스 후 구현")

    def search(self, query: str, *, limit: int = 20) -> List[PaidRecord]:
        raise NotImplementedError

    def fetch(self, external_id: str) -> PaidRecord:
        raise NotImplementedError


PROVIDERS = {
    PaidProviderCode.DBPIA: DBpiaProvider,
    PaidProviderCode.ATLA: AtlaProvider,
    PaidProviderCode.JSTOR: JstorProvider,
}


def get_provider(code: PaidProviderCode) -> PaidProvider:
    cls = PROVIDERS.get(code)
    if not cls:
        raise NotImplementedError(f"Provider stub not registered: {code}")
    return cls()


def gate_paid_payload(record: PaidRecord, *, membership: str) -> dict:
    """
    API 응답용 게이트. 유료 전문이 클라이언트로 통짜 유출되지 않게 축소.
    membership: Free_Trial | Limited_24h | Paid | Institution
    """
    meta = {
        "provider": record.provider.value,
        "external_id": record.external_id,
        "title": record.title,
        "authors": record.authors,
        "year": record.year,
        "doi": record.doi,
        "landing_url": record.landing_url,
        "license_note": record.license_note,
        "layer": "paid",
    }
    if membership in ("Paid", "Institution") and record.protection.allow_fulltext_api:
        meta["abstract"] = record.abstract
        meta["fulltext_available"] = True
    elif record.allow_free_user or record.protection.allow_free_preview:
        meta["abstract"] = record.abstract
        meta["fulltext_available"] = False
    else:
        meta["abstract"] = None
        meta["fulltext_available"] = False
        meta["preview"] = "유료/기관 구독 후 열람"
    return meta
