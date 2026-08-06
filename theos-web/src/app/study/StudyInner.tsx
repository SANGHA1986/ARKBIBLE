"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BookOpen, Search, Shield, SplitSquareHorizontal } from "lucide-react";
import { useLang } from "../LangContext";

import { API } from "../../lib/api";
const USER = "free_user";

type StrongPayload = {
  strong_number: string;
  language_type: string;
  lemma?: string;
  transliteration?: string;
  pronunciation?: string;
  gloss?: string;
  gloss_en?: string;
  definition_full?: string;
  root_word?: string;
  source?: {
    title?: string;
    copyright_status?: string;
    license_type?: string;
    attribution_text?: string;
    source_url?: string;
  };
  expansions?: Array<{ lexicon_name: string; entry_text: string; attribution?: string }>;
  morphology_links?: Array<{ related_strong: string; relation_type: string }>;
};

export default function StudyInner() {
  const { lang } = useLang();
  const params = useSearchParams();
  const [query, setQuery] = useState(params.get("strong") || "G0026");
  const [data, setData] = useState<StrongPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [panelTab, setPanelTab] = useState<"en" | "step" | "source">("en");
  const [pricingLock, setPricingLock] = useState<string | null>(null);

  const load = useCallback(async (strong: string) => {
    setLoading(true);
    setError(null);
    setPricingLock(null);
    try {
      const res = await fetch(
        `${API}/api/lexicon/strong/${encodeURIComponent(strong)}?username=${USER}`
      );
      const json = await res.json();
      if (res.status === 402 || res.status === 403) {
        const msg =
          typeof json?.detail === "object"
            ? json.detail.message
            : json?.detail ||
              (lang === "KO" ? "요금제를 선택하세요." : "Please choose a plan.");
        setPricingLock(msg);
        setData(null);
        return;
      }
      if (!res.ok)
        throw new Error(
          typeof json?.detail === "string"
            ? json.detail
            : lang === "KO"
              ? "조회 실패"
              : "Lookup failed"
        );
      setData(json);
      setPanelTab("en");
    } catch (e: any) {
      setError(e.message || String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [lang]);

  useEffect(() => {
    load(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stepText = useMemo(() => {
    if (!data?.expansions?.length) return null;
    return data.expansions.find((e) => e.lexicon_name.startsWith("STEP")) || data.expansions[0];
  }, [data]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    load(query.trim().toUpperCase());
  };

  return (
    <div className="w-full py-8 pb-24 px-4 max-w-6xl mx-auto">
      <div className="mb-6 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-ark-brown">
          <SplitSquareHorizontal className="w-5 h-5" />
          <h1 className="font-serif text-2xl font-bold text-ark-navy">
            {lang === "KO" ? "원어 연구" : "Lexical Study"}
          </h1>
        </div>
        <p className="text-sm text-ark-grey">
          {lang === "KO"
            ? "Strong 번호로 원문·영문 정의를 조회합니다. (G=헬라어, H=히브리어 — Strong’s 사전 색인)"
            : "Look up lemmas and English definitions by Strong’s number (G=Greek, H=Hebrew)."}
        </p>
      </div>

      <form onSubmit={onSubmit} className="mb-6 flex gap-2">
        <div className="flex-1 flex items-center border border-[#E8E2D9] rounded-xl bg-white shadow-sm overflow-hidden">
          <Search className="w-4 h-4 text-ark-grey ml-3" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="G0026 / H7225"
            className="w-full px-3 py-3 text-sm outline-none"
          />
        </div>
        <button
          type="submit"
          className="px-5 py-3 rounded-xl bg-ark-navy text-white text-sm font-semibold hover:bg-ark-brown"
        >
          {lang === "KO" ? "조회" : "Lookup"}
        </button>
      </form>

      {pricingLock && (
        <div className="mb-6 p-6 rounded-xl border-2 border-ark-brown bg-amber-50 text-center">
          <p className="font-semibold text-ark-navy mb-3">{pricingLock}</p>
          <a href="/pricing" className="inline-block px-5 py-2 bg-ark-brown text-white rounded-lg text-sm font-bold">
            {lang === "KO" ? "요금제 선택" : "Choose a plan"}
          </a>
        </div>
      )}

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 text-sm border border-red-100">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-[520px]">
        <section className="border border-[#E8E2D9] rounded-2xl bg-white shadow-soft overflow-hidden flex flex-col">
          <header className="px-4 py-3 border-b border-[#E8E2D9] bg-ark-bg flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-ark-brown" />
            <span className="text-sm font-semibold text-ark-navy">
              {lang === "KO" ? "요약" : "Summary"}
            </span>
          </header>
          <div className="p-5 flex-1 overflow-y-auto">
            {loading && <p className="text-ark-grey text-sm">Loading…</p>}
            {!loading && data && (
              <div className="space-y-4">
                <div>
                  <div className="text-3xl font-serif font-bold text-ark-navy">{data.strong_number}</div>
                  <div className="text-xl text-ark-navy mt-1" dir="auto">
                    {data.lemma}
                  </div>
                  <div className="text-sm text-ark-grey mt-1">
                    {data.transliteration}
                    {data.pronunciation ? ` · ${data.pronunciation}` : ""}
                  </div>
                </div>
                <div className="text-sm font-medium text-ark-navy">
                  {data.gloss_en || data.gloss || "—"}
                </div>
                {data.root_word && (
                  <p className="text-xs text-ark-grey">Root: {data.root_word}</p>
                )}
                {!!data.morphology_links?.length && (
                  <div>
                    <div className="text-xs font-bold uppercase tracking-wide text-ark-grey mb-2">
                      {lang === "KO" ? "연관 번호" : "Cross-refs"}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {data.morphology_links.slice(0, 12).map((l, i) => (
                        <button
                          key={i}
                          onClick={() => {
                            setQuery(l.related_strong);
                            load(l.related_strong);
                          }}
                          className="text-xs px-2 py-1 rounded border border-[#E8E2D9] hover:border-ark-brown"
                        >
                          {l.related_strong}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        <section className="border border-[#E8E2D9] rounded-2xl bg-white shadow-soft overflow-hidden flex flex-col">
          <header className="px-4 py-3 border-b border-[#E8E2D9] bg-ark-bg flex items-center gap-2 flex-wrap">
            <Shield className="w-4 h-4 text-emerald-700" />
            <span className="text-sm font-semibold text-ark-navy">
              {lang === "KO" ? "상세" : "Detail"}
            </span>
            <div className="ml-auto flex gap-1 flex-wrap">
              {(
                [
                  ["en", "EN"],
                  ["step", "STEP"],
                  ["source", lang === "KO" ? "출처" : "Source"],
                ] as const
              ).map(([t, label]) => (
                <button
                  key={t}
                  onClick={() => setPanelTab(t)}
                  className={`text-[11px] px-2 py-1 rounded ${
                    panelTab === t ? "bg-ark-navy text-white" : "bg-white border border-[#E8E2D9]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </header>
          <div className="p-5 flex-1 overflow-y-auto text-sm leading-relaxed">
            {!data && !loading && <p className="text-ark-grey">—</p>}
            {data && panelTab === "en" && (
              <p className="whitespace-pre-wrap text-ark-navy/90" dir="auto">
                {data.definition_full || data.gloss_en || data.gloss || "—"}
              </p>
            )}
            {data && panelTab === "step" && (
              <div className="space-y-3">
                <p className="text-xs text-ark-grey font-bold">{stepText?.lexicon_name || "STEP"}</p>
                <p className="whitespace-pre-wrap text-ark-navy" dir="auto">
                  {stepText?.entry_text || "—"}
                </p>
              </div>
            )}
            {data && panelTab === "source" && (
              <div className="space-y-2">
                <p className="font-semibold text-ark-navy">{data.source?.title || "—"}</p>
                {data.source?.license_type && (
                  <p className="text-ark-grey text-xs">
                    {lang === "KO" ? "라이선스" : "License"}: {data.source.license_type}
                  </p>
                )}
                {data.source?.attribution_text && (
                  <p className="text-ark-navy/80 text-sm leading-relaxed">
                    {data.source.attribution_text}
                  </p>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
