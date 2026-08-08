"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Search,
  Book,
  History,
  MessageSquare,
  Database,
  ArrowRight,
  Library,
  AlertCircle,
  Users,
  Sparkles,
  Star,
  ChevronDown,
  ChevronUp,
  MapPin,
  GitBranch,
} from "lucide-react";
import { useLang } from "../LangContext";
import { isScrapped, toggleScrap, type ScrapItem } from "../../lib/libraryStore";

import { API } from "../../lib/api";

function StarBtn({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      title={label}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors ${
        active
          ? "bg-ark-brown text-white border-ark-brown"
          : "bg-white text-ark-brown border-ark-brown/40 hover:bg-ark-brown/10"
      }`}
    >
      <Star className={`w-3.5 h-3.5 ${active ? "fill-current" : ""}`} />
      {label}
    </button>
  );
}

function SearchInner() {
  const { lang } = useLang();
  const params = useSearchParams();
  const router = useRouter();

  const [data, setData] = useState<any>(null);
  const [topic, setTopic] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [verseExtras, setVerseExtras] = useState<{
    commentaries?: any[];
    crossReferences?: any[];
  }>({});
  const [expandedComments, setExpandedComments] = useState<Set<number>>(new Set());
  const [, setScrapTick] = useState(0);
  const [resultPage, setResultPage] = useState(1);
  const RESULTS_PER_PAGE = 6;

  const refreshScrap = () => setScrapTick((n) => n + 1);

  const t =
    lang === "KO"
      ? {
          placeholder: "예: 창세기 4장, 요한복음 3:16, 블레셋의 침공",
          kgLive: "검색 준비",
          loading: "검색 중...",
          original: "원문",
          translated: "번역",
          graph: "관련 연결",
          events: "관련 사건",
          characters: "관련 인물",
          interpretations: "전통별 해석",
          noInterp: "이 구절에 대한 해당 전통의 해석이 없습니다.",
          debate: "이 관점에 대한 의견이 있으신가요?",
          suggest: "제안하기",
          welcomeTitle: "탐색",
          welcomeBody:
            "구절(예: 창세기 9:16), 인물·사건, 주제, 공개 논문·학술지를 검색할 수 있습니다. 논문은 「논문」「학술지」「신학」으로 찾으세요. 칼뱅 요약 등은 서적 시드입니다.",
          tryExample: "예: 블레셋의 침공",
          tryVerse: "예: 창세기 4장",
          tryPapers: "예: 논문",
          tryTheology: "예: 신학",
          searchTipsTitle: "검색 안내",
          searchTipsPapers:
            "논문·학술지: 「논문」「학술지」「신학」「성서학」— 결과는 자료 목록에서 논문으로 표시됩니다. (공개 초록·메타, 제목은 원문 언어 그대로일 수 있음)",
          searchTipsBooks:
            "서적·요약 시드: 「칼뱅」「교부」등 — 논문과 별개입니다.",
          searchTipsTradition:
            "교파 용어: 가톨릭(천주교)은 보통 「하느님」, 개신교(한국에서 흔히 기독교)는 「하나님」. 질문할 때 관점을 밝혀 주시면 혼동을 줄입니다. 역본에 따라 구절 표현이 다를 수 있습니다.",
          topicHits: "검색 결과",
          suggested: "관련 구절",
          noHits: "등록된 연관 자료가 없습니다.",
          noHitsAssist:
            "AI 어시스턴트에게 문의하세요. DB에 있는 기록만 근거로 답하며, 없는 내용은 추가 수집 예정이라고 안내합니다.",
          askAssistSearch: "어시스턴트에게 이 주제 문의",
          strong: "원어",
          scrap: "스크랩",
          scrapped: "저장됨",
          detail: "상세",
          period: "시기",
          background: "기록된 배경",
          relatedPeople: "관련 인물",
          relatedVerses: "연결된 구절",
          askAi: "AI에게 이 항목 설명 요청",
          openStudy: "원어 연구로",
          openLibrary: "내 서재 보기",
          selectHint: "왼쪽 항목을 선택하면 상세가 표시됩니다.",
          knownNote: "검색 결과는 DB에 있는 내용입니다.",
          materials: "자료·서적·논문",
          paperBadge: "논문/학술지",
          bookBadge: "서적·자료",
          textEn: "영문",
          textKo: "한국어",
          askAssistInterp: "어시스턴트로 이 구절·해석 설명",
          chapterVerses: "구절 목록",
          emptyChapter: "이 장 본문이 아직 없습니다.",
          chapterFull: "장 전체",
          dbCoverageNote: "성경 본문은 단계적으로 적재 중입니다. 없는 장은 곧 추가됩니다.",
          pageOf: "페이지",
          prev: "이전",
          next: "다음",
          places: "장소",
          doctrines: "교리·개념",
          definition: "정의",
          ancientName: "고대명",
          dbSeedNote: "아래는 DB에 등록된 목록입니다. 전체 성경 인물·장소가 아니라 단계적으로 채우는 중입니다.",
        }
      : {
          placeholder: "Search verse, person, event, paper, topic…",
          kgLive: "Ready to search",
          loading: "Searching…",
          original: "Original",
          translated: "Translation",
          graph: "Related links",
          events: "Events",
          characters: "People",
          interpretations: "Interpretations by tradition",
          noInterp: "No interpretation for this tradition.",
          debate: "Share a view?",
          suggest: "Suggest",
          welcomeTitle: "Explore",
          welcomeBody:
            "Search verses, people, events — and open-access papers. Try 「paper」「journal」or English topics (theology, biblical). Calvin summaries are book seeds, not journal articles.",
          tryExample: "Try: Philistine invasion",
          tryVerse: "Try: Genesis 1:1",
          tryPapers: "Try: paper",
          tryTheology: "Try: theology",
          searchTipsTitle: "Search tips",
          searchTipsPapers:
            "Papers/journals: paper, journal, theology, biblical — shown as JournalArticle under Materials. OA abstract/meta only (mostly English titles).",
          searchTipsBooks:
            "Book seeds: Calvin, Institutes, Fathers — separate from journal articles.",
          searchTipsTradition:
            "Tradition wording: Catholic often uses 하느님; Korean Protestant (often called 기독교) uses 하나님. Name the viewpoint in your question. Verse wording may differ by translation.",
          topicHits: "Results",
          suggested: "Related verses",
          noHits: "No related records in the database.",
          noHitsAssist:
            "Ask the AI assistant — answers use registered records only; missing topics are noted as planned.",
          askAssistSearch: "Ask assistant about this topic",
          strong: "Lexicon",
          scrap: "Save",
          scrapped: "Saved",
          detail: "Detail",
          period: "Period",
          background: "Recorded background",
          relatedPeople: "Related people",
          relatedVerses: "Linked verses",
          askAi: "Ask AI about this",
          openStudy: "Open lexicon",
          openLibrary: "Open Library",
          selectHint: "Select an item on the left for details.",
          knownNote: "Results come from the database as registered.",
          materials: "Materials / books / papers",
          paperBadge: "Journal article",
          bookBadge: "Book / material",
          textEn: "English",
          textKo: "Korean",
          askAssistInterp: "Ask assistant about this verse / interpretation",
          chapterVerses: "Verses",
          emptyChapter: "This chapter is not in the DB yet.",
          chapterFull: "Full chapter",
          dbCoverageNote: "Scripture text is being loaded in stages. Missing chapters will be added.",
          pageOf: "Page",
          prev: "Prev",
          next: "Next",
          places: "Places",
          doctrines: "Doctrine / Concepts",
          definition: "Definition",
          ancientName: "Ancient name",
          dbSeedNote:
            "Showing what is registered in DB so far — not every biblical name. Lists grow as we seed.",
        };

  const doScrap = (partial: Omit<ScrapItem, "id" | "savedAt">) => {
    toggleScrap(partial);
    refreshScrap();
  };

  const loadVerseExtras = async (book: string, chapter: number, verse: number) => {
    try {
      const res = await fetch(
        `${API}/api/bible/${encodeURIComponent(book)}/${chapter}/${verse}?lang=${encodeURIComponent(lang)}`
      );
      if (!res.ok) return;
      const json = await res.json();
      setVerseExtras({
        commentaries: json.commentaries || [],
        crossReferences: json.cross_references || [],
      });
      setExpandedComments(new Set());
    } catch {
      /* keep previous extras */
    }
  };

  const fetchVerse = async (book: string, chapter: number, verse: number) => {
    const bookKey = book;
    const res = await fetch(
      `${API}/api/bible/${encodeURIComponent(bookKey)}/${chapter}/${verse}?lang=${encodeURIComponent(lang)}`
    );
    if (!res.ok) throw new Error(lang === "KO" ? "구절 없음" : "Verse not found");
    const json = await res.json();
    setData(json);
    setTopic(null);
    setSelected(null);
    setVerseExtras({
      commentaries: json.commentaries || [],
      crossReferences: json.cross_references || [],
    });
    setExpandedComments(new Set());
    if (json.interpretations?.length > 0) {
      setActiveTab(json.interpretations[0].viewpoint);
    }
  };

  const selectVerseRow = async (v: any) => {
    setSelected({ type: "verse_row", data: v });
    const bookKey = v.book_ko || v.book;
    if (bookKey && v.chapter != null && v.verse != null) {
      await loadVerseExtras(bookKey, v.chapter, v.verse);
    }
  };

  const runSearch = async (query: string) => {
    setLoading(true);
    setError(null);
    setHasSearched(true);
    setData(null);
    setTopic(null);
    setSelected(null);
    try {
      const res = await fetch(
        `${API}/api/search?q=${encodeURIComponent(query)}&username=free_user&lang=${lang}`
      );
      const json = await res.json();
      if (!res.ok) {
        throw new Error(typeof json?.detail === "string" ? json.detail : "Search failed");
      }

      if (json.mode === "verse" && json.verse) {
        setVerseExtras({
          commentaries: json.commentaries || [],
          crossReferences: json.cross_references || [],
        });
        const bookKey = json.verse.book_ko || json.verse.book;
        await fetchVerse(bookKey, json.verse.chapter, json.verse.verse);
        return;
      }

      if (json.mode === "chapter" || json.mode === "book") {
        setVerseExtras({
          commentaries: json.commentaries || [],
          crossReferences: [],
        });
        setError(null);
        setTopic(json);
        if (json.mode === "chapter" && json.verses?.length) {
          setSelected({ type: "chapter_all", data: json });
        } else if (json.verses?.[0]) {
          await selectVerseRow(json.verses[0]);
        } else {
          setSelected(null);
        }
        return;
      }

      if (json.message && !json.browse) {
        setError(json.message);
      } else {
        setError(null);
      }

      setTopic(json);
      setResultPage(1);
      const browse = json.browse as string | undefined;
      if (browse === "commentary" || browse === "papers" || browse === "fathers" || browse === "sources") {
        if (json.materials?.[0]) {
          setSelected({ type: "material", data: json.materials[0] });
        } else if (json.characters?.[0]) {
          setSelected({ type: "character", data: json.characters[0] });
        } else {
          setSelected(null);
        }
      } else if (browse === "bible_hub" && json.verses?.[0]) {
        await selectVerseRow(json.verses[0]);
      } else if (json.characters?.[0]) {
        setSelected({ type: "character", data: json.characters[0] });
      } else if (json.events?.[0]) {
        setSelected({ type: "event", data: json.events[0] });
      } else if (json.locations?.[0]) {
        setSelected({ type: "location", data: json.locations[0] });
      } else if (json.concepts?.[0]) {
        setSelected({ type: "concept", data: json.concepts[0] });
      } else if (json.materials?.[0]) {
        setSelected({ type: "material", data: json.materials[0] });
      } else if (json.strong?.[0]) {
        setSelected({ type: "strong", data: json.strong[0] });
      } else if (json.verses?.[0]) {
        await selectVerseRow(json.verses[0]);
      } else {
        setSelected(null);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const aiPrompt = (ko: string, en: string) => (lang === "KO" ? ko : en);

  useEffect(() => {
    const q = params.get("q");
    if (!q && !hasSearched) return;
    const query = q || searchQuery.trim();
    if (!query) return;
    if (q) setSearchQuery(q);
    runSearch(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, params]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    runSearch(searchQuery.trim());
  };

  const openSuggested = (ref: string) => {
    const normalized = ref.replace(":", " ");
    setSearchQuery(normalized);
    runSearch(normalized);
  };

  const askAiAbout = (text: string, context?: string) => {
    try {
      sessionStorage.setItem("ark_assistant_prefill", text);
      if (context) sessionStorage.setItem("ark_assistant_context", context);
      else sessionStorage.removeItem("ark_assistant_context");
      window.dispatchEvent(new Event("ark-assistant-prefill"));
    } catch {
      /* ignore */
    }
  };

  const koMissingLabel = (langCode: string) =>
    langCode === "KO"
      ? "이 절 번호는 개역한글(1961) 절 체계에 없어 한국어 본문이 없습니다. 영문 WEB을 참고하세요."
      : "No Korean (개역한글 1961) for this verse number (versification may differ). See English WEB.";

  const displayKoText = (raw: string | null | undefined, langCode: string) => {
    const ko = (raw || "").trim();
    if (ko && !ko.startsWith("[공개")) return ko;
    return koMissingLabel(langCode);
  };

  const verseAssistContext = (opts: {
    reference: string;
    textEn?: string;
    textKo?: string;
    original?: string;
    interps?: string;
  }) => {
    const ko =
      opts.textKo && !String(opts.textKo).startsWith("[공개") ? opts.textKo : "";
    const parts = [
      opts.textEn ? `EN(WEB PD): ${opts.textEn}` : "",
      ko ? `KO: ${ko}` : "",
      opts.original ? `Original: ${opts.original}` : "",
      opts.interps ? `Interpretations:\n${opts.interps}` : "",
    ].filter(Boolean);
    return parts.join("\n") || "(no registered text)";
  };

  const materialAssistContext = (m: {
    title?: string;
    author?: string;
    type?: string;
    license?: string;
    viewpoint?: string;
    claim?: string;
    evidence?: string;
    description?: string;
    source_url?: string;
    attribution?: string;
  }) => {
    const parts = [
      m.title ? `Title: ${m.title}` : "",
      m.author ? `Author: ${m.author}` : "",
      m.type ? `Type: ${m.type}` : "",
      m.license ? `License: ${m.license}` : "",
      m.source_url ? `Source URL: ${m.source_url}` : "",
      m.attribution ? `Attribution: ${m.attribution}` : "",
      m.description ? `Summary: ${m.description}` : "",
      m.viewpoint ? `Viewpoint: ${m.viewpoint}` : "",
      m.claim ? `Registered claim: ${m.claim}` : "",
      m.evidence ? `Evidence: ${m.evidence}` : "",
    ].filter(Boolean);
    return parts.join("\n") || "(registered material metadata)";
  };

  const groupedInterpretations =
    data?.interpretations?.reduce((acc: any, curr: any) => {
      if (!acc[curr.viewpoint]) acc[curr.viewpoint] = [];
      acc[curr.viewpoint].push(curr);
      return acc;
    }, {}) || {};
  const availableViewpoints = Object.keys(groupedInterpretations);

  return (
    <div className="w-full max-w-6xl mx-auto px-4 flex flex-col pt-8 pb-32">
      <form
        onSubmit={handleSearch}
        className="w-full flex flex-col md:flex-row md:items-center gap-4 mb-6"
      >
        <div className="relative flex-1 flex items-center bg-white border border-[#E8E2D9] rounded-xl shadow-soft overflow-hidden">
          <div className="pl-4 text-ark-grey">
            <Search className="w-5 h-5" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={
              lang === "KO"
                ? "구절·인물·주제·논문(학술지) 검색…"
                : t.placeholder
            }
            className="w-full bg-transparent border-none outline-none text-ark-navy px-4 py-3 text-sm font-medium"
          />
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-2 bg-ark-bg border border-[#E8E2D9] rounded-lg text-ark-brown text-xs font-semibold">
            <Database className="w-4 h-4" />
            <span>{t.kgLive}</span>
          </div>
          <a
            href="/library"
            className="px-3 py-2 rounded-lg border border-ark-brown text-ark-brown text-xs font-bold hover:bg-ark-brown hover:text-white transition-colors"
          >
            {t.openLibrary}
          </a>
        </div>
      </form>

      {!hasSearched && !loading && (
        <div className="text-center py-12 px-4 border border-dashed border-[#E8E2D9] rounded-2xl bg-white">
          <h2 className="font-serif text-2xl font-bold text-ark-navy mb-3">{t.welcomeTitle}</h2>
          <p className="text-ark-grey text-sm max-w-2xl mx-auto mb-6 leading-relaxed">
            {t.welcomeBody}
          </p>
          <div className="flex flex-wrap gap-2 justify-center mb-8">
            <button
              type="button"
              onClick={() => {
                const q = lang === "KO" ? "블레셋 침공" : "Moses";
                setSearchQuery(q);
                runSearch(q);
              }}
              className="px-4 py-2 rounded-lg bg-ark-brown text-white text-sm font-semibold"
            >
              {t.tryExample}
            </button>
            <button
              type="button"
              onClick={() => {
                const q = lang === "KO" ? "창세기 1 1" : "Genesis 1 1";
                setSearchQuery(q);
                runSearch(q);
              }}
              className="px-4 py-2 rounded-lg border border-ark-brown text-ark-brown text-sm font-semibold"
            >
              {t.tryVerse}
            </button>
            <button
              type="button"
              onClick={() => {
                const q = lang === "KO" ? "논문" : "paper";
                setSearchQuery(q);
                runSearch(q);
              }}
              className="px-4 py-2 rounded-lg border border-ark-navy text-ark-navy text-sm font-semibold"
            >
              {t.tryPapers}
            </button>
            <button
              type="button"
              onClick={() => {
                const q = lang === "KO" ? "신학" : "theology";
                setSearchQuery(q);
                runSearch(q);
              }}
              className="px-4 py-2 rounded-lg border border-ark-navy text-ark-navy text-sm font-semibold"
            >
              {t.tryTheology}
            </button>
            <button
              type="button"
              onClick={() => {
                const q = lang === "KO" ? "칼뱅" : "calvin";
                setSearchQuery(q);
                runSearch(q);
              }}
              className="px-4 py-2 rounded-lg border border-[#E8E2D9] text-ark-grey text-sm font-semibold"
            >
              {lang === "KO" ? "예: 칼뱅(서적)" : "Try: Calvin (book)"}
            </button>
          </div>
          <div className="max-w-2xl mx-auto text-left space-y-3 text-xs text-ark-grey leading-relaxed bg-ark-bg/80 rounded-xl border border-[#E8E2D9] p-4">
            <div className="font-semibold text-ark-navy text-sm">{t.searchTipsTitle}</div>
            <p>{t.searchTipsPapers}</p>
            <p>{t.searchTipsBooks}</p>
            <p>{t.searchTipsTradition}</p>
          </div>
        </div>
      )}

      {loading && (
        <div className="w-full flex flex-col items-center justify-center py-20">
          <div className="w-10 h-10 border-4 border-ark-gold/30 border-t-ark-brown rounded-full animate-spin mb-4" />
          <p className="text-ark-grey font-medium">{t.loading}</p>
        </div>
      )}

      {error && !loading && (
        <div className="w-full p-6 bg-red-50 border border-red-200 rounded-2xl flex items-center gap-3 text-red-700">
          <AlertCircle className="w-6 h-6" />
          <span className="font-semibold">{error}</span>
        </div>
      )}

      {!loading && !error && topic && !data && topic.mode === "chapter" && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
          {t.dbCoverageNote}
        </p>
      )}

      {/* Topic results — list + detail */}
      {!loading && !error && topic && !data && (
        <div className="space-y-4">
          <p className="text-xs text-ark-grey leading-relaxed">{t.knownNote}</p>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            <div className="lg:col-span-5 space-y-4">
              <h2 className="font-serif text-xl font-bold text-ark-navy">{t.topicHits}</h2>
              {topic.query_expansion &&
                (topic.query_expansion.terms_en?.length > 0 ||
                  topic.query_expansion.terms_ko?.length > 0) && (
                  <p className="text-[11px] text-ark-grey mt-1 leading-relaxed">
                    {lang === "KO" ? "검색어 확장" : "Query expanded"}
                    {topic.query_expansion.translated_query_en
                      ? `: ${topic.query_expansion.translated_query_en}`
                      : ""}
                    {topic.query_expansion.terms_ko?.length
                      ? ` · ${(topic.query_expansion.terms_ko as string[]).slice(0, 6).join(", ")}`
                      : ""}
                    {topic.query_expansion.source
                      ? ` (${topic.query_expansion.source})`
                      : ""}
                  </p>
                )}

              {(topic.mode === "chapter" || topic.mode === "book" || !!topic.verses?.length) && (
                <section className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft">
                  <div className="flex items-center gap-2 text-ark-brown mb-3">
                    <Book className="w-4 h-4" />
                    <h3 className="font-bold text-sm">
                      {t.chapterVerses}
                      {topic.chapter?.book && topic.chapter?.chapter
                        ? lang === "KO"
                          ? ` · ${topic.chapter.book} ${topic.chapter.chapter}장`
                          : ` · ${topic.chapter.book} ${topic.chapter.chapter}`
                        : topic.chapter?.book
                          ? ` · ${topic.chapter.book}`
                          : ""}
                    </h3>
                  </div>
                  {topic.message && (
                    <p className="text-sm text-ark-grey mb-2">{topic.message}</p>
                  )}
                  {topic.mode === "topic" && topic.message && topic.message.includes("AI") && (
                    <button
                      type="button"
                      onClick={() =>
                        askAiAbout(
                          aiPrompt(
                            `「${searchQuery}」에 대해 DB에 등록된 내용만 근거로 설명해 주세요. 없는 자료는 추가 수집 예정임을 알려 주세요.`,
                            `Explain "${searchQuery}" using only registered DB records. Note any gaps as planned for future collection. Reply in English.`
                          )
                        )
                      }
                      className="mt-2 inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-ark-brown text-white hover:opacity-90"
                    >
                      <MessageSquare className="w-3.5 h-3.5" />
                      {lang === "KO" ? "AI 어시스턴트에게 물어보기" : "Ask AI assistant"}
                    </button>
                  )}
                  {!topic.verses?.length ? (
                    <p className="text-sm text-ark-grey">{t.emptyChapter}</p>
                  ) : (
                    <div className="space-y-1 max-h-[70vh] overflow-y-auto">
                      {topic.verses.map((v: any, i: number) => {
                        const active =
                          (selected?.type === "verse_row" &&
                            selected?.data?.reference === v.reference) ||
                          (selected?.type === "chapter_all" && i === 0);
                        return (
                          <button
                            key={i}
                            type="button"
                            onClick={() => selectVerseRow(v)}
                            className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
                              active
                                ? "border-ark-brown bg-ark-brown/5"
                                : "border-transparent hover:bg-ark-bg"
                            }`}
                          >
                            <span className="font-bold text-sm text-ark-brown">{v.reference}</span>
                            {v.reason && (
                              <span className="block text-[10px] text-ark-grey mt-0.5">{v.reason}</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </section>
              )}

              {!!topic.events?.length && (
                <section className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft">
                  <div className="flex items-center gap-2 text-ark-brown mb-3">
                    <History className="w-4 h-4" />
                    <h3 className="font-bold text-sm">{t.events}</h3>
                    <span className="ml-auto text-[10px] text-ark-grey">{topic.events.length}</span>
                  </div>
                  <p className="text-[10px] text-ark-grey mb-2 leading-relaxed">{t.dbSeedNote}</p>
                  <div className="space-y-2">
                    {topic.events
                      .slice((resultPage - 1) * RESULTS_PER_PAGE, resultPage * RESULTS_PER_PAGE)
                      .map((ev: any, i: number) => {
                      const active = selected?.type === "event" && selected?.data?.name === ev.name;
                      const saved = isScrapped("event", ev.name);
                      return (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setSelected({ type: "event", data: ev })}
                          className={`w-full text-left p-3 rounded-xl border transition-colors ${
                            active
                              ? "border-ark-brown bg-ark-brown/5"
                              : "border-[#E8E2D9] hover:border-ark-brown/50"
                          }`}
                        >
                          <div className="font-serif font-bold text-ark-navy">{ev.name}</div>
                          <div className="text-[11px] text-ark-grey mt-1 line-clamp-2">
                            {ev.background}
                          </div>
                          <div className="mt-2 flex justify-end">
                            <StarBtn
                              active={saved}
                              label={saved ? t.scrapped : t.scrap}
                              onClick={() =>
                                doScrap({
                                  kind: "event",
                                  title: ev.name,
                                  subtitle: ev.period,
                                  body: ev.background,
                                  query: searchQuery,
                                  href: `/search?q=${encodeURIComponent(ev.name)}`,
                                })
                              }
                            />
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  {topic.events.length > RESULTS_PER_PAGE && (
                    <div className="flex items-center justify-center gap-2 mt-3 pt-3 border-t border-[#E8E2D9]">
                      <button
                        type="button"
                        disabled={resultPage <= 1}
                        onClick={() => setResultPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.prev}
                      </button>
                      <span className="text-xs text-ark-grey">
                        {resultPage} / {Math.ceil(topic.events.length / RESULTS_PER_PAGE)}
                      </span>
                      <button
                        type="button"
                        disabled={resultPage * RESULTS_PER_PAGE >= topic.events.length}
                        onClick={() =>
                          setResultPage((p) =>
                            p * RESULTS_PER_PAGE >= topic.events.length ? p : p + 1
                          )
                        }
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.next}
                      </button>
                    </div>
                  )}
                </section>
              )}

              {!!topic.characters?.length && (
                <section className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft">
                  <div className="flex items-center gap-2 text-ark-brown mb-3">
                    <Users className="w-4 h-4" />
                    <h3 className="font-bold text-sm">{t.characters}</h3>
                    <span className="ml-auto text-[10px] text-ark-grey">
                      {topic.characters.length}
                    </span>
                  </div>
                  <p className="text-[10px] text-ark-grey mb-2 leading-relaxed">{t.dbSeedNote}</p>
                  <div className="space-y-2">
                    {topic.characters
                      .slice((resultPage - 1) * RESULTS_PER_PAGE, resultPage * RESULTS_PER_PAGE)
                      .map((c: any, i: number) => {
                      const active =
                        selected?.type === "character" && selected?.data?.name === c.name;
                      const saved = isScrapped("character", c.name);
                      return (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setSelected({ type: "character", data: c })}
                          className={`w-full text-left p-3 rounded-xl border transition-colors ${
                            active
                              ? "border-ark-brown bg-ark-brown/5"
                              : "border-[#E8E2D9] hover:border-ark-brown/50"
                          }`}
                        >
                          <div className="font-bold text-ark-navy">
                            {c.name}{" "}
                            <span className="text-ark-grey font-normal text-sm">
                              {c.original_name}
                            </span>
                          </div>
                          <div className="text-[11px] text-ark-grey mt-1 line-clamp-2">{c.info}</div>
                          <div className="mt-2 flex justify-end">
                            <StarBtn
                              active={saved}
                              label={saved ? t.scrapped : t.scrap}
                              onClick={() =>
                                doScrap({
                                  kind: "character",
                                  title: c.name,
                                  subtitle: c.era,
                                  body: c.info,
                                  href: `/search?q=${encodeURIComponent(c.name)}`,
                                })
                              }
                            />
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  {topic.characters.length > RESULTS_PER_PAGE && (
                    <div className="flex items-center justify-center gap-2 mt-3 pt-3 border-t border-[#E8E2D9]">
                      <button
                        type="button"
                        disabled={resultPage <= 1}
                        onClick={() => setResultPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.prev}
                      </button>
                      <span className="text-xs text-ark-grey">
                        {resultPage} / {Math.ceil(topic.characters.length / RESULTS_PER_PAGE)}
                      </span>
                      <button
                        type="button"
                        disabled={resultPage * RESULTS_PER_PAGE >= topic.characters.length}
                        onClick={() =>
                          setResultPage((p) =>
                            p * RESULTS_PER_PAGE >= topic.characters.length ? p : p + 1
                          )
                        }
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.next}
                      </button>
                    </div>
                  )}
                </section>
              )}

              {!!topic.locations?.length && (
                <section className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft">
                  <div className="flex items-center gap-2 text-ark-brown mb-3">
                    <MapPin className="w-4 h-4" />
                    <h3 className="font-bold text-sm">{t.places}</h3>
                    <span className="ml-auto text-[10px] text-ark-grey">
                      {topic.locations.length}
                    </span>
                  </div>
                  <p className="text-[10px] text-ark-grey mb-2 leading-relaxed">{t.dbSeedNote}</p>
                  <div className="space-y-2">
                    {topic.locations
                      .slice((resultPage - 1) * RESULTS_PER_PAGE, resultPage * RESULTS_PER_PAGE)
                      .map((loc: any, i: number) => {
                        const active =
                          selected?.type === "location" && selected?.data?.name === loc.name;
                        return (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setSelected({ type: "location", data: loc })}
                            className={`w-full text-left p-3 rounded-xl border transition-colors ${
                              active
                                ? "border-ark-brown bg-ark-brown/5"
                                : "border-[#E8E2D9] hover:border-ark-brown/50"
                            }`}
                          >
                            <div className="font-bold text-ark-navy text-sm">{loc.name}</div>
                            {loc.ancient_name && (
                              <div className="text-[11px] text-ark-grey mt-1">
                                {t.ancientName}: {loc.ancient_name}
                              </div>
                            )}
                          </button>
                        );
                      })}
                  </div>
                  {topic.locations.length > RESULTS_PER_PAGE && (
                    <div className="flex items-center justify-center gap-2 mt-3 pt-3 border-t border-[#E8E2D9]">
                      <button
                        type="button"
                        disabled={resultPage <= 1}
                        onClick={() => setResultPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.prev}
                      </button>
                      <span className="text-xs text-ark-grey">
                        {resultPage} / {Math.ceil(topic.locations.length / RESULTS_PER_PAGE)}
                      </span>
                      <button
                        type="button"
                        disabled={resultPage * RESULTS_PER_PAGE >= topic.locations.length}
                        onClick={() =>
                          setResultPage((p) =>
                            p * RESULTS_PER_PAGE >= topic.locations.length ? p : p + 1
                          )
                        }
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.next}
                      </button>
                    </div>
                  )}
                </section>
              )}

              {!!topic.concepts?.length && (
                <section className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft">
                  <div className="flex items-center gap-2 text-ark-brown mb-3">
                    <GitBranch className="w-4 h-4" />
                    <h3 className="font-bold text-sm">{t.doctrines}</h3>
                    <span className="ml-auto text-[10px] text-ark-grey">
                      {topic.concepts.length}
                    </span>
                  </div>
                  <p className="text-[10px] text-ark-grey mb-2 leading-relaxed">{t.dbSeedNote}</p>
                  <div className="space-y-2">
                    {topic.concepts
                      .slice((resultPage - 1) * RESULTS_PER_PAGE, resultPage * RESULTS_PER_PAGE)
                      .map((cp: any, i: number) => {
                        const active =
                          selected?.type === "concept" && selected?.data?.name === cp.name;
                        return (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setSelected({ type: "concept", data: cp })}
                            className={`w-full text-left p-3 rounded-xl border transition-colors ${
                              active
                                ? "border-ark-brown bg-ark-brown/5"
                                : "border-[#E8E2D9] hover:border-ark-brown/50"
                            }`}
                          >
                            <div className="font-bold text-ark-navy text-sm">{cp.name}</div>
                            <div className="text-[11px] text-ark-grey mt-1 line-clamp-2">
                              {cp.definition}
                            </div>
                          </button>
                        );
                      })}
                  </div>
                  {topic.concepts.length > RESULTS_PER_PAGE && (
                    <div className="flex items-center justify-center gap-2 mt-3 pt-3 border-t border-[#E8E2D9]">
                      <button
                        type="button"
                        disabled={resultPage <= 1}
                        onClick={() => setResultPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.prev}
                      </button>
                      <span className="text-xs text-ark-grey">
                        {resultPage} / {Math.ceil(topic.concepts.length / RESULTS_PER_PAGE)}
                      </span>
                      <button
                        type="button"
                        disabled={resultPage * RESULTS_PER_PAGE >= topic.concepts.length}
                        onClick={() =>
                          setResultPage((p) =>
                            p * RESULTS_PER_PAGE >= topic.concepts.length ? p : p + 1
                          )
                        }
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40"
                      >
                        {t.next}
                      </button>
                    </div>
                  )}
                </section>
              )}

              {!!topic.strong?.length && (
                <section className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft">
                  <div className="flex items-center gap-2 text-ark-brown mb-3">
                    <Sparkles className="w-4 h-4" />
                    <h3 className="font-bold text-sm">{t.strong}</h3>
                  </div>
                  {topic.strong.map((s: any, i: number) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setSelected({ type: "strong", data: s })}
                      className="w-full text-left p-3 rounded-xl border border-[#E8E2D9] mb-2 hover:border-ark-brown/50"
                    >
                      <span className="font-bold">{s.strong_number}</span> {s.lemma} — {s.gloss}
                    </button>
                  ))}
                </section>
              )}

              {!!topic.materials?.length && (
                <section className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft">
                  <div className="flex items-center gap-2 text-ark-brown mb-3">
                    <Library className="w-4 h-4" />
                    <h3 className="font-bold text-sm">
                      {topic.browse === "commentary"
                        ? lang === "KO"
                          ? "주석 작품 목록"
                          : "Commentary works"
                        : topic.browse === "papers"
                          ? lang === "KO"
                            ? "논문·학술지"
                            : "Papers / Journals"
                          : topic.browse === "sources"
                            ? lang === "KO"
                              ? "등록 자료 전체"
                              : "All sources"
                            : t.materials}
                    </h3>
                    <span className="ml-auto text-[10px] text-ark-grey">
                      {topic.materials.length} · {t.pageOf} {resultPage}/{Math.max(1, Math.ceil(topic.materials.length / RESULTS_PER_PAGE))}
                    </span>
                  </div>
                  {topic.message &&
                    (topic.browse === "commentary" ||
                      topic.browse === "papers" ||
                      topic.browse === "sources") && (
                    <p className="text-xs text-ark-grey mb-3 leading-relaxed">{topic.message}</p>
                  )}
                  <div className="space-y-2">
                    {topic.materials
                      .slice(
                        (resultPage - 1) * RESULTS_PER_PAGE,
                        resultPage * RESULTS_PER_PAGE
                      )
                      .map((m: any, i: number) => {
                      const isPaper =
                        (m.type || m.source_type || "").toLowerCase() === "journalarticle";
                      return (
                      <button
                        key={i}
                        type="button"
                        onClick={() => setSelected({ type: "material", data: m })}
                        className="w-full text-left p-3 rounded-xl border border-[#E8E2D9] hover:border-ark-brown/50"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="font-bold text-ark-navy text-sm">{m.title}</div>
                          <span className="shrink-0 text-[10px] font-semibold text-ark-navy">
                            {isPaper ? t.paperBadge : t.bookBadge}
                          </span>
                        </div>
                        <div className="text-[11px] text-ark-grey mt-1">
                          {[m.author, m.license, m.publication_year].filter(Boolean).join(" · ")}
                        </div>
                        {m.claim && (
                          <p className="text-xs text-ark-navy/80 mt-1 line-clamp-2">{m.claim}</p>
                        )}
                      </button>
                      );
                    })}
                  </div>
                  {topic.materials.length > RESULTS_PER_PAGE && (
                    <div className="flex items-center justify-center gap-2 mt-3 pt-3 border-t border-[#E8E2D9]">
                      <button
                        type="button"
                        disabled={resultPage <= 1}
                        onClick={() => setResultPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40 hover:bg-ark-bg"
                      >
                        {t.prev}
                      </button>
                      <span className="text-xs text-ark-grey">
                        {resultPage} / {Math.ceil(topic.materials.length / RESULTS_PER_PAGE)}
                      </span>
                      <button
                        type="button"
                        disabled={resultPage * RESULTS_PER_PAGE >= topic.materials.length}
                        onClick={() =>
                          setResultPage((p) =>
                            p * RESULTS_PER_PAGE >= topic.materials.length ? p : p + 1
                          )
                        }
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] disabled:opacity-40 hover:bg-ark-bg"
                      >
                        {t.next}
                      </button>
                    </div>
                  )}
                </section>
              )}

              {!topic.events?.length &&
                !topic.characters?.length &&
                !topic.locations?.length &&
                !topic.concepts?.length &&
                !topic.strong?.length &&
                !topic.materials?.length &&
                !topic.verses?.length &&
                topic.mode === "topic" && (
                  <div className="bg-ark-bg border border-[#E8E2D9] rounded-2xl p-4 space-y-3">
                    <p className="text-ark-navy text-sm font-medium">{t.noHits}</p>
                    {topic.message && (
                      <p className="text-ark-grey text-sm leading-relaxed">{topic.message}</p>
                    )}
                    <p className="text-ark-grey text-xs leading-relaxed">{t.noHitsAssist}</p>
                    <button
                      type="button"
                      onClick={() =>
                        askAiAbout(
                          aiPrompt(
                            `「${searchQuery}」에 대해 DB에 등록된 내용만 근거로 설명해 주세요. 없는 자료는 추가 수집 예정임을 알려 주세요.`,
                            `Explain "${searchQuery}" using only registered DB records. Note any gaps as planned for future collection. Reply in English.`
                          )
                        )
                      }
                      className="px-4 py-2 rounded-lg text-sm font-semibold bg-ark-brown text-white hover:opacity-90"
                    >
                      {t.askAssistSearch}
                    </button>
                  </div>
                )}
            </div>

            {/* Detail panel */}
            <div className="lg:col-span-7 bg-white border border-[#E8E2D9] rounded-2xl p-6 shadow-soft min-h-[420px] max-h-[80vh] overflow-y-auto">
              <h3 className="font-serif text-lg font-bold text-ark-navy mb-4">{t.detail}</h3>
              {!selected && !topic.verses?.length && (
                <p className="text-sm text-ark-grey">{t.selectHint}</p>
              )}

              {selected?.type === "chapter_all" && topic.verses?.length > 0 && (
                <div className="space-y-6">
                  <h2 className="font-serif text-2xl font-bold text-ark-navy">
                    {topic.chapter?.book} {topic.chapter?.chapter}
                    {lang === "KO" ? "장" : ""}
                  </h2>
                  {topic.verses.map((v: any) => (
                    <article
                      key={v.reference}
                      className="border-b border-[#E8E2D9] pb-4 last:border-0"
                    >
                      <div className="font-bold text-ark-brown text-sm mb-1">{v.reference}</div>
                      {v.text_original && (
                        <p className="text-base font-serif text-right mb-2" dir="rtl">
                          {v.text_original}
                        </p>
                      )}
                      {v.text_ko && !String(v.text_ko).startsWith("[공개") ? (
                        <p className="text-base font-serif leading-relaxed mb-1">{v.text_ko}</p>
                      ) : (
                        <p className="text-xs text-ark-grey mb-1 italic">{koMissingLabel(lang)}</p>
                      )}
                      {v.text_en && (
                        <p className="text-sm text-ark-navy/90 leading-relaxed">{v.text_en}</p>
                      )}
                      {!v.text_en && (!v.text_ko || String(v.text_ko).startsWith("[공개")) && (
                        <p className="text-xs text-ark-grey">—</p>
                      )}
                    </article>
                  ))}
                </div>
              )}

              {selected?.type === "verse_row" && (
                <div className="space-y-4">
                  {topic.mode === "chapter" && (
                    <button
                      type="button"
                      onClick={() => setSelected({ type: "chapter_all", data: topic })}
                      className="text-xs font-semibold text-ark-brown hover:underline"
                    >
                      ← {t.chapterFull}
                    </button>
                  )}
                  <h2 className="font-serif text-2xl font-bold text-ark-navy">
                    {selected.data.reference}
                  </h2>
                  {selected.data.text_original && (
                    <div>
                      <div className="text-xs font-bold uppercase text-ark-grey">{t.original}</div>
                      <p className="text-lg font-serif mt-1 text-right" dir="rtl">
                        {selected.data.text_original}
                      </p>
                    </div>
                  )}
                  {lang === "EN" ? (
                    <>
                      {selected.data.text_en && (
                        <div>
                          <div className="text-xs font-bold uppercase text-ark-grey">{t.textEn}</div>
                          <p className="text-base font-serif mt-1 leading-relaxed">
                            {selected.data.text_en}
                          </p>
                        </div>
                      )}
                      {selected.data.text_ko &&
                        !String(selected.data.text_ko).startsWith("[공개") && (
                          <div>
                            <div className="text-xs font-bold uppercase text-ark-grey">{t.textKo}</div>
                            <p className="text-base font-serif mt-1 leading-relaxed">
                              {displayKoText(selected.data.text_ko, lang)}
                            </p>
                          </div>
                        )}
                    </>
                  ) : (
                    <>
                      <div>
                        <div className="text-xs font-bold uppercase text-ark-grey">{t.textKo}</div>
                        <p className="text-base font-serif mt-1 leading-relaxed">
                          {displayKoText(selected.data.text_ko, lang)}
                        </p>
                      </div>
                      {selected.data.text_en && (
                        <div>
                          <div className="text-xs font-bold uppercase text-ark-grey">{t.textEn}</div>
                          <p className="text-base font-serif mt-1 leading-relaxed">
                            {selected.data.text_en}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                  <div className="flex flex-wrap gap-2 pt-2">
                    <StarBtn
                      active={isScrapped("verse", selected.data.reference)}
                      label={
                        isScrapped("verse", selected.data.reference) ? t.scrapped : t.scrap
                      }
                      onClick={() =>
                        doScrap({
                          kind: "verse",
                          title: selected.data.reference,
                          body: selected.data.text_en || selected.data.text_ko,
                          href: `/search?q=${encodeURIComponent(
                            selected.data.reference.replace(":", " ")
                          )}`,
                        })
                      }
                    />
                    <button
                      type="button"
                      onClick={() =>
                        fetchVerse(
                          selected.data.book_ko || selected.data.book,
                          selected.data.chapter,
                          selected.data.verse
                        )
                      }
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9]"
                    >
                      {lang === "KO" ? "연결·해석 더 보기" : "More links"}
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        askAiAbout(
                          aiPrompt(
                            `${selected.data.reference} 구절을 DB 등록 자료만으로 설명해 주세요.`,
                            `Explain ${selected.data.reference} using registered DB sources only. Reply in English.`
                          ),
                          verseAssistContext({
                            reference: selected.data.reference,
                            textEn: selected.data.text_en,
                            textKo: selected.data.text_ko,
                            original: selected.data.text_original,
                          })
                        )
                      }
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9]"
                    >
                      {t.askAi}
                    </button>
                  </div>
                  {!!verseExtras.commentaries?.length && (
                    <div className="pt-4 border-t border-[#E8E2D9] space-y-3">
                      <div className="flex items-center gap-2">
                        <Library className="w-4 h-4 text-ark-brown" />
                        <h3 className="font-serif font-bold text-base text-ark-navy">
                          {lang === "KO" ? "이 구절 공개 주석" : "Commentaries for this verse"}
                        </h3>
                        <span className="text-[10px] text-ark-grey ml-auto">
                          {verseExtras.commentaries.length}
                          {lang === "KO" ? "건 · 영문 PD" : " · English PD"}
                        </span>
                      </div>
                      {verseExtras.commentaries.map((c: any, idx: number) => {
                        const isExpanded = expandedComments.has(idx);
                        return (
                          <div key={idx} className="p-3 bg-ark-bg rounded-lg border border-[#E8E2D9]">
                            <div className="font-bold text-sm text-ark-brown">
                              {c.short_cite || c.author}
                            </div>
                            <div className="text-[10px] text-ark-grey mb-2">
                              {c.license} · {c.passage_ref}
                            </div>
                            <p
                              className={`text-xs text-ark-navy/85 leading-relaxed whitespace-pre-line ${
                                isExpanded ? "" : "line-clamp-6"
                              }`}
                            >
                              {c.text}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-3">
                              {c.text && c.text.length > 260 && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedComments((prev) => {
                                      const next = new Set(prev);
                                      if (next.has(idx)) next.delete(idx);
                                      else next.add(idx);
                                      return next;
                                    })
                                  }
                                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-ark-brown hover:opacity-80"
                                >
                                  {isExpanded ? (
                                    <>
                                      <ChevronUp className="w-3.5 h-3.5" />
                                      {lang === "KO" ? "접기" : "Collapse"}
                                    </>
                                  ) : (
                                    <>
                                      <ChevronDown className="w-3.5 h-3.5" />
                                      {lang === "KO" ? "펼쳐보기" : "Show more"}
                                    </>
                                  )}
                                </button>
                              )}
                              {lang === "KO" && c.text && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    askAiAbout(
                                      `${c.author} 주석(${c.passage_ref})을 한국어로 짧게 요약해 주세요. 등록된 영문 PD/CC0 본문만 근거로 하고 추측하지 마세요.`,
                                      `Author: ${c.author}\nLicense: ${c.license}\nPassage: ${c.passage_ref}\n\n${String(c.text || "")}`
                                    )
                                  }
                                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-ark-brown hover:opacity-80"
                                >
                                  <MessageSquare className="w-3.5 h-3.5" />
                                  한국어 요약 요청
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {!verseExtras.commentaries?.length && selected.data.book_ko && (
                    <p className="text-[11px] text-ark-grey pt-2">
                      {lang === "KO"
                        ? "이 구절에 연결된 공개 주석을 불러오는 중이거나, 아직 등록분이 없습니다."
                        : "Loading verse commentaries, or none registered for this verse yet."}
                    </p>
                  )}
                </div>
              )}

              {selected?.type === "event" && (
                <div className="space-y-4">
                  <h2 className="font-serif text-2xl font-bold text-ark-navy">
                    {selected.data.name}
                  </h2>
                  <div>
                    <div className="text-xs font-bold uppercase tracking-wide text-ark-grey">
                      {t.period}
                    </div>
                    <p className="text-sm text-ark-navy mt-1">{selected.data.period || "—"}</p>
                  </div>
                  <div>
                    <div className="text-xs font-bold uppercase tracking-wide text-ark-grey">
                      {t.background}
                    </div>
                    <p className="text-sm text-ark-navy/90 mt-2 leading-relaxed whitespace-pre-wrap">
                      {selected.data.background || "—"}
                    </p>
                    {selected.data.source_note && (
                      <p className="text-[11px] text-ark-grey mt-2">{selected.data.source_note}</p>
                    )}
                  </div>
                  {!!selected.data.locations?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wide text-ark-grey mb-2">
                        {lang === "KO" ? "관련 장소" : "Places"}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.locations.map((n: string) => (
                          <span
                            key={n}
                            className="px-3 py-1 rounded-full border border-[#E8E2D9] text-xs"
                          >
                            {n}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {!!selected.data.characters?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wide text-ark-grey mb-2">
                        {t.relatedPeople}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.characters.map((n: string) => (
                          <button
                            key={n}
                            type="button"
                            onClick={() => {
                              setSearchQuery(n);
                              runSearch(n);
                            }}
                            className="px-3 py-1 rounded-full border border-[#E8E2D9] text-xs font-semibold hover:border-ark-brown"
                          >
                            @{n}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {!!selected.data.verses?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wide text-ark-grey mb-2">
                        {t.relatedVerses}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.verses.map((ref: string) => (
                          <button
                            key={ref}
                            type="button"
                            onClick={() => openSuggested(ref)}
                            className="px-3 py-1.5 rounded-full bg-ark-bg border border-[#E8E2D9] text-xs font-semibold"
                          >
                            {ref}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="pt-4 flex flex-wrap gap-2">
                    <StarBtn
                      active={isScrapped("event", selected.data.name)}
                      label={
                        isScrapped("event", selected.data.name) ? t.scrapped : t.scrap
                      }
                      onClick={() =>
                        doScrap({
                          kind: "event",
                          title: selected.data.name,
                          subtitle: selected.data.period,
                          body: selected.data.background,
                          href: `/search?q=${encodeURIComponent(selected.data.name)}`,
                        })
                      }
                    />
                    <button
                      type="button"
                      onClick={() =>
                        askAiAbout(
                          aiPrompt(
                            `「${selected.data.name}」에 대해 해석이 필요하십니까?`,
                            `Please explain "${selected.data.name}" using registered DB records. Reply in English.`
                          )
                        )
                      }
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9] hover:border-ark-brown"
                    >
                      {t.askAi}
                    </button>
                  </div>
                </div>
              )}

              {selected?.type === "character" && (
                <div className="space-y-4">
                  <h2 className="font-serif text-2xl font-bold text-ark-navy">
                    {selected.data.name}{" "}
                    <span className="text-lg text-ark-grey font-normal">
                      {selected.data.original_name}
                    </span>
                  </h2>
                  <p className="text-sm text-ark-grey">{selected.data.era}</p>
                  <p className="text-sm text-ark-navy/90 leading-relaxed whitespace-pre-wrap">
                    {selected.data.info}
                  </p>
                  {!!selected.data.events?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase text-ark-grey mb-2">
                        {t.events}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.events.map((n: string) => (
                          <span
                            key={n}
                            className="px-3 py-1 rounded-full border border-[#E8E2D9] text-xs"
                          >
                            {n}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {!!selected.data.verses?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase text-ark-grey mb-2">
                        {t.relatedVerses}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.verses.map((ref: string) => (
                          <button
                            key={ref}
                            type="button"
                            onClick={() => openSuggested(ref)}
                            className="px-3 py-1.5 rounded-full bg-ark-bg border text-xs font-semibold"
                          >
                            {ref}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <StarBtn
                    active={isScrapped("character", selected.data.name)}
                    label={
                      isScrapped("character", selected.data.name) ? t.scrapped : t.scrap
                    }
                    onClick={() =>
                      doScrap({
                        kind: "character",
                        title: selected.data.name,
                        subtitle: selected.data.era,
                        body: selected.data.info,
                        href: `/search?q=${encodeURIComponent(selected.data.name)}`,
                      })
                    }
                  />
                </div>
              )}

              {selected?.type === "location" && (
                <div className="space-y-4">
                  <h2 className="font-serif text-2xl font-bold text-ark-navy">
                    {selected.data.name}
                  </h2>
                  {selected.data.ancient_name && (
                    <p className="text-sm text-ark-grey">
                      {t.ancientName}: {selected.data.ancient_name}
                    </p>
                  )}
                  {!!selected.data.events?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase text-ark-grey mb-2">
                        {t.events}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.events.map((n: string) => (
                          <span
                            key={n}
                            className="px-3 py-1 rounded-full border border-[#E8E2D9] text-xs"
                          >
                            {n}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {!!selected.data.verses?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase text-ark-grey mb-2">
                        {t.relatedVerses}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.verses.map((ref: string) => (
                          <button
                            key={ref}
                            type="button"
                            onClick={() => openSuggested(ref)}
                            className="px-3 py-1.5 rounded-full bg-ark-bg border text-xs font-semibold"
                          >
                            {ref}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {selected?.type === "concept" && (
                <div className="space-y-4">
                  <h2 className="font-serif text-2xl font-bold text-ark-navy">
                    {selected.data.name}
                  </h2>
                  <div>
                    <div className="text-xs font-bold uppercase text-ark-grey mb-2">
                      {t.definition}
                    </div>
                    <p className="text-sm text-ark-navy/90 leading-relaxed">
                      {selected.data.definition}
                    </p>
                  </div>
                  {!!selected.data.verses?.length && (
                    <div>
                      <div className="text-xs font-bold uppercase text-ark-grey mb-2">
                        {t.relatedVerses}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selected.data.verses.map((ref: string) => (
                          <button
                            key={ref}
                            type="button"
                            onClick={() => openSuggested(ref)}
                            className="px-3 py-1.5 rounded-full bg-ark-bg border text-xs font-semibold"
                          >
                            {ref}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {selected?.type === "strong" && (
                <div className="space-y-3">
                  <h2 className="font-serif text-2xl font-bold">
                    {selected.data.strong_number} {selected.data.lemma}
                  </h2>
                  <p className="text-ark-brown font-medium">{selected.data.gloss}</p>
                  <button
                    type="button"
                    onClick={() => router.push(selected.data.study_path)}
                    className="px-4 py-2 rounded-lg bg-ark-navy text-white text-sm font-semibold"
                  >
                    {t.openStudy}
                  </button>
                </div>
              )}

              {selected?.type === "material" && (
                <div className="space-y-3">
                  <div className="text-[10px] font-bold uppercase text-ark-brown">
                    {selected.data.kind || "material"}
                  </div>
                  <h2 className="font-serif text-2xl font-bold text-ark-navy">
                    {selected.data.title}
                  </h2>
                  <p className="text-sm text-ark-grey">
                    {[selected.data.author, selected.data.type, selected.data.license]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {selected.data.source_url && (
                    <a
                      href={selected.data.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-ark-brown underline break-all"
                    >
                      {selected.data.source_url}
                    </a>
                  )}
                  {(selected.data.attribution || selected.data.description) && (
                    <p className="text-xs text-ark-grey leading-relaxed">
                      {selected.data.attribution || selected.data.description}
                    </p>
                  )}
                  {selected.data.viewpoint && (
                    <p className="text-xs font-semibold text-ark-brown">
                      {selected.data.viewpoint}
                    </p>
                  )}
                  {selected.data.claim && (
                    <p className="text-sm text-ark-navy leading-relaxed">{selected.data.claim}</p>
                  )}
                  <button
                    type="button"
                    onClick={() =>
                      askAiAbout(
                        aiPrompt(
                          `"${selected.data.title}" 자료에 대해 DB에 등록된 내용만 설명해 주세요. 추측 금지.`,
                          `Explain "${selected.data.title}" using only registered DB content. Do not speculate. Reply in English.`
                        ),
                        materialAssistContext(selected.data)
                      )
                    }
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9]"
                  >
                    {t.askAi}
                  </button>
                </div>
              )}

              {!!topic.suggested_verses?.length && (
                <div className="mt-8 pt-6 border-t border-[#E8E2D9]">
                  <h4 className="font-bold text-sm text-ark-navy mb-2">{t.suggested}</h4>
                  <div className="flex flex-wrap gap-2">
                    {topic.suggested_verses.map((ref: string) => (
                      <button
                        key={ref}
                        type="button"
                        onClick={() => openSuggested(ref)}
                        className="px-3 py-1.5 rounded-full border text-xs font-semibold hover:border-ark-brown"
                      >
                        {ref}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-white rounded-2xl border border-[#E8E2D9] shadow-soft p-6 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-ark-brown" />
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 text-ark-brown">
                  <Book className="w-5 h-5" />
                  <h2 className="font-serif font-bold text-lg text-ark-navy">{data.reference}</h2>
                </div>
                <StarBtn
                  active={isScrapped("verse", data.reference)}
                  label={isScrapped("verse", data.reference) ? t.scrapped : t.scrap}
                  onClick={() =>
                    doScrap({
                      kind: "verse",
                      title: data.reference,
                      body: data.translated_text,
                      href: `/search?q=${encodeURIComponent(data.reference.replace(":", " "))}`,
                    })
                  }
                />
              </div>
              <div className="space-y-4">
                {data.original_text && (
                  <div>
                    <span className="text-xs font-semibold text-ark-grey uppercase tracking-wider mb-2 block">
                      {t.original}
                    </span>
                    <p
                      className="text-2xl font-serif text-ark-navy leading-relaxed text-right"
                      dir="rtl"
                    >
                      {data.original_text}
                    </p>
                  </div>
                )}
                <div className="pt-2 border-t border-[#E8E2D9]">
                  <span className="text-xs font-semibold text-ark-grey uppercase tracking-wider mb-2 block">
                    {t.textKo}
                  </span>
                  <p className="text-lg font-serif text-ark-navy leading-relaxed font-medium">
                    {displayKoText(data.text_ko || data.translated_text, lang)}
                  </p>
                </div>
                {data.text_en && (
                  <div className="pt-2 border-t border-[#E8E2D9]">
                    <span className="text-xs font-semibold text-ark-grey uppercase tracking-wider mb-2 block">
                      {t.textEn}
                    </span>
                    <p className="text-base font-serif text-ark-navy/90 leading-relaxed">
                      {data.text_en}
                    </p>
                  </div>
                )}
                {lang === "KO" && data.translation_ko && (
                  <p className="text-[11px] text-ark-brown">{data.translation_ko}</p>
                )}
                {lang === "EN" && data.translation_en && (
                  <p className="text-[11px] text-ark-brown">{data.translation_en}</p>
                )}
                {data.translation_note && (
                  <p className="text-[11px] text-ark-grey">{data.translation_note}</p>
                )}
              </div>
            </div>

            {!!data.related_verses?.length && (
              <div className="bg-white rounded-2xl border border-[#E8E2D9] shadow-soft p-6">
                <h2 className="font-serif font-bold text-lg text-ark-navy mb-3">
                  {t.relatedVerses}
                </h2>
                <div className="space-y-2">
                  {data.related_verses.map((rv: any, idx: number) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => openSuggested(rv.reference)}
                      className="w-full text-left p-3 rounded-xl border border-[#E8E2D9] hover:border-ark-brown/50"
                    >
                      <div className="font-bold text-sm text-ark-brown">{rv.reference}</div>
                      <div className="text-[11px] text-ark-grey mt-0.5">{rv.reason}</div>
                      {rv.snippet && (
                        <p className="text-xs text-ark-navy/80 mt-1 line-clamp-2">{rv.snippet}</p>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!!verseExtras.crossReferences?.length && (
              <div className="bg-white rounded-2xl border border-[#E8E2D9] shadow-soft p-6">
                <div className="flex items-center gap-2 mb-3">
                  <ArrowRight className="w-4 h-4 text-ark-brown" />
                  <h2 className="font-serif font-bold text-lg text-ark-navy">
                    {lang === "KO" ? "연관 구절" : "Cross References"}
                  </h2>
                  <span className="text-[10px] text-ark-grey ml-auto">
                    {lang === "KO" ? "OpenBible CC BY" : "OpenBible CC BY"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {verseExtras.crossReferences.map((cr: any, idx: number) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => openSuggested(cr.reference.replace(":", " "))}
                      className="px-3 py-1.5 rounded-lg border border-ark-brown/30 bg-ark-bg hover:bg-ark-brown/10 text-xs font-semibold text-ark-brown"
                      title={`votes: ${cr.votes ?? 0}`}
                    >
                      {cr.reference}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!!verseExtras.commentaries?.length && (
              <div className="bg-white rounded-2xl border border-[#E8E2D9] shadow-soft p-6">
                <div className="flex items-center gap-2 mb-3">
                  <Library className="w-4 h-4 text-ark-brown" />
                  <h2 className="font-serif font-bold text-lg text-ark-navy">
                    {lang === "KO" ? "공개 주석" : "Public Commentaries"}
                  </h2>
                  <span className="text-[10px] text-ark-grey ml-auto">
                    {lang === "KO"
                      ? "영문 공개 주석 · 한국어 요약은 아래에서 요청"
                      : "English public-domain notes · ask AI for a Korean summary"}
                  </span>
                </div>
                <div className="space-y-3">
                  {verseExtras.commentaries.map((c: any, idx: number) => {
                    const isExpanded = expandedComments.has(idx);
                    return (
                      <div key={idx} className="p-3 bg-ark-bg rounded-lg border border-[#E8E2D9]">
                        <div className="font-bold text-sm text-ark-brown">
                          {c.short_cite || c.author}
                        </div>
                        <div className="text-[10px] text-ark-grey mb-2">
                          {c.license} · {c.passage_ref}
                        </div>
                        <p
                          className={`text-xs text-ark-navy/85 leading-relaxed whitespace-pre-line ${
                            isExpanded ? "" : "line-clamp-6"
                          }`}
                        >
                          {c.text}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-3">
                          {c.text && c.text.length > 260 && (
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedComments((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(idx)) next.delete(idx);
                                  else next.add(idx);
                                  return next;
                                })
                              }
                              className="inline-flex items-center gap-1 text-[11px] font-semibold text-ark-brown hover:opacity-80"
                            >
                              {isExpanded ? (
                                <>
                                  <ChevronUp className="w-3.5 h-3.5" />
                                  {lang === "KO" ? "접기" : "Collapse"}
                                </>
                              ) : (
                                <>
                                  <ChevronDown className="w-3.5 h-3.5" />
                                  {lang === "KO" ? "펼쳐보기" : "Show more"}
                                </>
                              )}
                            </button>
                          )}
                          {lang === "KO" && c.text && (
                            <button
                              type="button"
                              onClick={() =>
                                askAiAbout(
                                  `${c.author} 주석(${c.passage_ref})을 한국어로 짧게 요약해 주세요. 등록된 영문 PD/CC0 본문만 근거로 하고 추측하지 마세요.`,
                                  `Author: ${c.author}\nLicense: ${c.license}\nPassage: ${c.passage_ref}\n\n${String(c.text || "")}`
                                )
                              }
                              className="inline-flex items-center gap-1 text-[11px] font-semibold text-ark-navy hover:text-ark-brown"
                            >
                              <Sparkles className="w-3.5 h-3.5" />
                              한국어 요약
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {!!data.materials?.length && (
              <div className="bg-white rounded-2xl border border-[#E8E2D9] shadow-soft p-6">
                <h2 className="font-serif font-bold text-lg text-ark-navy mb-3">{t.materials}</h2>
                {data.materials.map((m: any, idx: number) => {
                  const isPaper =
                    (m.type || m.source_type || "").toLowerCase() === "journalarticle";
                  return (
                  <div key={idx} className="p-3 bg-ark-bg rounded-lg border mb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-bold text-sm">{m.title}</div>
                      <span
                        className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
                          isPaper
                            ? "border-ark-navy text-ark-navy"
                            : "border-[#E8E2D9] text-ark-grey"
                        }`}
                      >
                        {isPaper ? t.paperBadge : t.bookBadge}
                      </span>
                    </div>
                    <div className="text-[11px] text-ark-grey">
                      {[m.author, m.viewpoint, m.license, m.publication_year]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                    {m.claim && <p className="text-xs mt-1 leading-relaxed">{m.claim}</p>}
                    <button
                      type="button"
                      onClick={() =>
                        askAiAbout(
                          aiPrompt(
                            `"${m.title}" 자료에 대해 DB에 등록된 내용만 설명해 주세요.`,
                            `Explain "${m.title}" using only registered DB content. Reply in English.`
                          ),
                          materialAssistContext(m)
                        )
                      }
                      className="mt-2 px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E8E2D9]"
                    >
                      {t.askAi}
                    </button>
                  </div>
                  );
                })}
              </div>
            )}

            <div className="bg-white rounded-2xl border border-[#E8E2D9] shadow-soft p-6">
              <div className="flex items-center gap-2 text-ark-navy mb-4">
                <History className="w-5 h-5" />
                <h2 className="font-serif font-bold text-lg">{t.graph}</h2>
              </div>
              {data.related_events?.map((event: any, idx: number) => (
                <div key={idx} className="p-3 bg-ark-bg rounded-lg border border-[#E8E2D9] mb-2">
                  <span className="font-bold text-ark-brown font-serif block mb-1">
                    ■ {event.name}
                  </span>
                  <p className="text-xs text-ark-grey leading-relaxed">
                    {event.historical_background}
                  </p>
                </div>
              ))}
              {data.related_characters?.length > 0 && (
                <div className="flex gap-2 flex-wrap mt-3">
                  {data.related_characters.map((char: any, idx: number) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-white border border-[#E8E2D9] rounded-full text-xs font-bold"
                    >
                      @{char.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-7 bg-white rounded-2xl border border-[#E8E2D9] shadow-soft flex flex-col overflow-hidden">
            <div className="p-6 border-b border-[#E8E2D9] bg-ark-bg/50 flex flex-col md:flex-row justify-between items-center gap-4">
              <div className="flex items-center gap-2 text-ark-navy">
                <Library className="w-5 h-5 text-ark-brown" />
                <h2 className="font-serif font-bold text-lg">{t.interpretations}</h2>
              </div>
              <div className="flex flex-wrap gap-1 bg-[#E8E2D9]/60 p-1 rounded-lg">
                {availableViewpoints.map((vp) => (
                  <button
                    key={vp}
                    onClick={() => setActiveTab(vp)}
                    className={`px-4 py-1.5 rounded-md text-sm font-bold ${
                      activeTab === vp ? "bg-white text-ark-brown shadow-sm" : "text-ark-grey"
                    }`}
                  >
                    {vp}
                  </button>
                ))}
              </div>
            </div>
            <div className="p-6">
              {groupedInterpretations[activeTab]?.map((interp: any, idx: number) => (
                <div key={idx} className="mb-6">
                  <h3 className="font-bold text-ark-navy mb-2 text-lg">{interp.claim}</h3>
                  <div className="border-l-4 border-ark-gold/50 pl-4 py-2 bg-ark-bg rounded-r-lg">
                    <p className="text-sm leading-relaxed mb-3">&ldquo;{interp.evidence}&rdquo;</p>
                    <div className="text-xs text-ark-grey">
                      {interp.scholar} · {interp.source?.title || "—"}
                    </div>
                  </div>
                </div>
              )) || <p className="text-ark-grey text-center py-10">{t.noInterp}</p>}

              <button
                type="button"
                onClick={() => {
                  const interps = (data.interpretations || [])
                    .map(
                      (i: any) =>
                        `- [${i.viewpoint}] ${i.scholar}: ${i.claim}\n  ${i.evidence || ""}`
                    )
                    .join("\n");
                  const ctx = verseAssistContext({
                    reference: data.reference,
                    textEn: data.text_en,
                    textKo: data.text_ko || data.translated_text,
                    original: data.original_text,
                    interps: interps || undefined,
                  });
                  askAiAbout(
                    aiPrompt(
                      `${data.reference} 구절을 DB 등록 본문·해석만으로 설명해 주세요.`,
                      `Explain ${data.reference} using only registered DB text/interpretations. Reply in English.`
                    ),
                    ctx
                  );
                }}
                className="w-full mb-4 px-4 py-2.5 rounded-xl bg-ark-navy text-white text-sm font-semibold hover:bg-ark-brown"
              >
                {t.askAssistInterp}
              </button>

              <div className="mt-4 p-4 bg-ark-bg border border-[#E8E2D9] rounded-xl flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <MessageSquare className="w-5 h-5 text-ark-grey" />
                  <span className="text-sm font-medium">{t.debate}</span>
                </div>
                <a href="/forum" className="flex items-center gap-1 text-sm font-bold text-ark-brown">
                  {t.suggest} <ArrowRight className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SearchResults() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-ark-grey text-sm">Loading…</div>}>
      <SearchInner />
    </Suspense>
  );
}
