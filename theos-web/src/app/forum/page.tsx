"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Send, Pin } from "lucide-react";
import { useLang } from "../LangContext";

type Thread = {
  id: string;
  title: string;
  topic: string;
  author: string;
  body: string;
  createdAt: string;
  replies: number;
};

const STORAGE_KEY = "ark_forum_threads_v2";

export default function ForumPage() {
  const { lang } = useLang();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [body, setBody] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          // 데모 시드(t1, t2, Pastor A 등)는 버리고 사용자 글만 유지
          setThreads(
            parsed.filter(
              (x: Thread) => typeof x?.id === "string" && x.id.startsWith("t_")
            )
          );
        }
      }
    } catch {
      setThreads([]);
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
    } catch {
      /* ignore */
    }
  }, [threads, ready]);

  const t =
    lang === "KO"
      ? {
          title: "토론방",
          subtitle:
            "베타: 예시 글 없이 비어 있습니다. 작성한 글은 이 브라우저에만 저장됩니다(서버 동기화 전).",
          newThread: "새 글 작성",
          topicPh: "주제 / 구절 (예: 요한복음 3:16)",
          titlePh: "제목",
          bodyPh: "내용을 입력하세요",
          submit: "등록",
          empty: "아직 글이 없습니다. 첫 글을 남겨 보세요.",
          replies: "댓글",
          pinned: "주제 연결",
        }
      : {
          title: "Forum",
          subtitle:
            "Beta: no demo posts. Threads stay in this browser until account sync.",
          newThread: "New thread",
          topicPh: "Topic / verse (e.g. John 3:16)",
          titlePh: "Title",
          bodyPh: "Write your post…",
          submit: "Post",
          empty: "No threads yet. Be the first to post.",
          replies: "replies",
          pinned: "Linked topic",
        };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;
    const next: Thread = {
      id: `t_${Date.now()}`,
      title: title.trim(),
      topic: topic.trim() || (lang === "KO" ? "일반" : "General"),
      author: lang === "KO" ? "나" : "Me",
      body: body.trim(),
      createdAt: new Date().toISOString(),
      replies: 0,
    };
    setThreads((prev) => [next, ...prev.filter((x) => x.id.startsWith("t_"))]);
    setTitle("");
    setTopic("");
    setBody("");
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 py-10 pb-24">
      <div className="mb-8">
        <h1 className="font-serif text-3xl font-bold text-ark-navy">{t.title}</h1>
        <p className="text-ark-grey text-sm mt-2 leading-relaxed">{t.subtitle}</p>
      </div>

      <form
        onSubmit={onSubmit}
        className="bg-white border border-[#E8E2D9] rounded-2xl p-4 shadow-soft mb-8 space-y-3"
      >
        <div className="font-semibold text-sm text-ark-brown flex items-center gap-2">
          <Send className="w-4 h-4" />
          {t.newThread}
        </div>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder={t.topicPh}
          className="w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm outline-none focus:border-ark-brown"
        />
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t.titlePh}
          className="w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm outline-none focus:border-ark-brown"
        />
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={t.bodyPh}
          rows={3}
          className="w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm outline-none focus:border-ark-brown resize-none"
        />
        <button
          type="submit"
          className="px-4 py-2 rounded-lg bg-ark-brown text-white text-sm font-semibold"
        >
          {t.submit}
        </button>
      </form>

      {!threads.length ? (
        <p className="text-center text-ark-grey py-12">{t.empty}</p>
      ) : (
        <div className="space-y-4">
          {threads.map((th) => (
            <article
              key={th.id}
              className="bg-white border border-[#E8E2D9] rounded-2xl p-5 shadow-soft"
            >
              <div className="flex items-start gap-3">
                <MessageSquare className="w-5 h-5 text-ark-brown shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <h2 className="font-serif font-bold text-lg text-ark-navy">{th.title}</h2>
                  <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-ark-grey">
                    <span className="inline-flex items-center gap-1 text-ark-brown font-semibold">
                      <Pin className="w-3 h-3" />
                      {t.pinned}: {th.topic}
                    </span>
                    <span>· {th.author}</span>
                    <span>
                      · {t.replies} {th.replies}
                    </span>
                  </div>
                  <p className="text-sm text-ark-navy/80 mt-3 leading-relaxed">{th.body}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
