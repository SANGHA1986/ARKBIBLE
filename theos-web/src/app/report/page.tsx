"use client";

import { useState } from "react";
import { Flag } from "lucide-react";
import { useLang } from "../LangContext";

import { API } from "../../lib/api";

export default function ReportPage() {
  const { lang } = useLang();
  const [category, setCategory] = useState("bug");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [contact, setContact] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sending, setSending] = useState(false);
  const [doneId, setDoneId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const t =
    lang === "KO"
      ? {
          h1: "제보하기",
          sub: "버그, 데이터 오류, 기능 수정안을 남겨 주세요. 테스트에 큰 도움이 됩니다.",
          category: "분류",
          bug: "버그",
          data: "데이터 오류",
          feature: "기능·수정안",
          title: "제목",
          body: "내용",
          contact: "연락처 (선택)",
          query: "관련 검색어/구절 (선택)",
          send: "보내기",
          sending: "전송 중…",
          ok: "제보가 접수되었습니다. 감사합니다.",
          id: "접수번호",
        }
      : {
          h1: "Feedback",
          sub: "Report bugs, data errors, or feature ideas.",
          category: "Category",
          bug: "Bug",
          data: "Data error",
          feature: "Feature / fix idea",
          title: "Title",
          body: "Details",
          contact: "Contact (optional)",
          query: "Related search / verse (optional)",
          send: "Submit",
          sending: "Sending…",
          ok: "Thanks — your report was received.",
          id: "Ticket",
        };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;
    setSending(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category,
          title: title.trim(),
          body: body.trim(),
          contact: contact.trim() || null,
          page_url: typeof window !== "undefined" ? window.location.href : null,
          search_query: searchQuery.trim() || null,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "failed");
      setDoneId(j.id);
      setTitle("");
      setBody("");
      setSearchQuery("");
    } catch (err: any) {
      setError(String(err.message || err));
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="max-w-xl mx-auto px-4 py-10">
      <div className="flex items-center gap-2 mb-2">
        <Flag className="w-5 h-5 text-ark-brown" />
        <h1 className="font-serif text-2xl font-bold text-ark-navy">{t.h1}</h1>
      </div>
      <p className="text-sm text-ark-grey mb-6 leading-relaxed">{t.sub}</p>

      {doneId != null && (
        <div className="mb-4 p-3 rounded-xl bg-ark-bg border border-[#E8E2D9] text-sm text-ark-navy">
          {t.ok} ({t.id}: {doneId})
        </div>
      )}
      {error && <p className="mb-3 text-sm text-red-700">{error}</p>}

      <form onSubmit={submit} className="space-y-4 bg-white border border-[#E8E2D9] rounded-2xl p-5 shadow-soft">
        <label className="block text-xs font-semibold text-ark-grey">
          {t.category}
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm text-ark-navy"
          >
            <option value="bug">{t.bug}</option>
            <option value="data">{t.data}</option>
            <option value="feature">{t.feature}</option>
          </select>
        </label>

        <label className="block text-xs font-semibold text-ark-grey">
          {t.title}
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
          />
        </label>

        <label className="block text-xs font-semibold text-ark-grey">
          {t.body}
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            required
            rows={6}
            className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
          />
        </label>

        <label className="block text-xs font-semibold text-ark-grey">
          {t.query}
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
            placeholder={lang === "KO" ? "예: 창세기 9:16 / 논문" : "e.g. Genesis 9:16"}
          />
        </label>

        <label className="block text-xs font-semibold text-ark-grey">
          {t.contact}
          <input
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
          />
        </label>

        <button
          type="submit"
          disabled={sending}
          className="w-full py-2.5 rounded-lg bg-ark-brown text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50"
        >
          {sending ? t.sending : t.send}
        </button>
      </form>
    </main>
  );
}
