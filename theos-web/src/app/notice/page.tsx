"use client";

import { useEffect, useState } from "react";
import { Megaphone, Pin } from "lucide-react";
import { useLang } from "../LangContext";

import { API } from "../../lib/api";

type Notice = {
  id: number;
  title: string;
  body: string;
  pinned: boolean;
  created_at?: string;
};

export default function NoticePage() {
  const { lang } = useLang();
  const [items, setItems] = useState<Notice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/api/notices`);
        const j = await r.json();
        setItems(j.items || []);
      } catch (e: any) {
        setError(e.message || "load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <div className="flex items-center gap-2 mb-6">
        <Megaphone className="w-5 h-5 text-ark-brown" />
        <h1 className="font-serif text-2xl font-bold text-ark-navy">
          {lang === "KO" ? "공지사항" : "Announcements"}
        </h1>
      </div>

      {loading && (
        <p className="text-sm text-ark-grey">{lang === "KO" ? "불러오는 중…" : "Loading…"}</p>
      )}
      {error && <p className="text-sm text-red-700">{error}</p>}

      {!loading && !items.length && (
        <p className="text-sm text-ark-grey">
          {lang === "KO" ? "등록된 공지가 없습니다." : "No announcements yet."}
        </p>
      )}

      <div className="space-y-4">
        {items.map((n) => (
          <article
            key={n.id}
            className="bg-white border border-[#E8E2D9] rounded-2xl p-5 shadow-soft"
          >
            <div className="flex items-start gap-2 mb-2">
              {n.pinned && <Pin className="w-4 h-4 text-ark-brown shrink-0 mt-1" />}
              <h2 className="font-serif text-lg font-bold text-ark-navy">{n.title}</h2>
            </div>
            {n.created_at && (
              <p className="text-[11px] text-ark-grey mb-3">
                {new Date(n.created_at).toLocaleString(lang === "KO" ? "ko-KR" : "en-US")}
              </p>
            )}
            <pre className="whitespace-pre-wrap font-sans text-sm text-ark-navy/90 leading-relaxed">
              {n.body}
            </pre>
          </article>
        ))}
      </div>

      <p className="mt-8 text-xs text-ark-grey">
        {lang === "KO" ? (
          <>
            버그·데이터 오류·수정안은{" "}
            <a href="/report" className="text-ark-brown font-semibold underline">
              제보하기
            </a>
            로 남겨 주세요.
          </>
        ) : (
          <>
            Report bugs or data issues via{" "}
            <a href="/report" className="text-ark-brown font-semibold underline">
              Feedback
            </a>
            .
          </>
        )}
      </p>
    </main>
  );
}
