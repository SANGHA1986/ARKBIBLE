"use client";

import "./globals.css";
import { Globe, X, Sparkles, Bot, Square, Eraser, Menu } from "lucide-react";
import { LangProvider, useLang } from "./LangContext";
import { useState, useEffect, useRef } from "react";
import { motion, useDragControls } from "framer-motion";
import { API } from "../lib/api";

function Header() {
  const { lang, setLang } = useLang();
  const [mobileOpen, setMobileOpen] = useState(false);

  const links = [
    { href: "/search", ko: "탐색", en: "Explore" },
    { href: "/notice", ko: "공지", en: "News" },
    { href: "/report", ko: "제보", en: "Report" },
    { href: "/library", ko: "내 서재", en: "Library" },
    { href: "/forum", ko: "토론방", en: "Forum" },
    { href: "/study", ko: "원어 연구", en: "Lexicon" },
    { href: "/help", ko: "도움말", en: "Help" },
    { href: "/account", ko: "내정보", en: "Profile" },
  ];

  return (
    <header className="w-full z-20 bg-ark-white/90 backdrop-blur-md border-b border-[#E8E2D9]">
      <div className="max-w-6xl mx-auto px-4 md:px-6 h-16 md:h-[72px] flex items-center justify-between gap-4">
        <a href="/" className="flex items-center gap-2.5 shrink-0">
          <div className="w-8 h-8 flex items-center justify-center rounded bg-ark-brown text-white shadow-sm">
            <svg
              width="14"
              height="18"
              viewBox="0 0 16 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
            >
              <line x1="8" y1="2" x2="8" y2="18" />
              <line x1="4" y1="7" x2="12" y2="7" />
            </svg>
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-[22px] font-serif font-bold text-ark-navy tracking-wide">
              ARK
            </span>
            <span className="text-[9px] text-ark-brown uppercase tracking-[0.14em] font-semibold mt-0.5">
              Biblical Knowledge Platform
            </span>
          </div>
        </a>

        <nav className="hidden md:flex items-center gap-5 text-[14px] font-medium text-ark-grey">
          {links
            .filter((l) => l.href !== "/account")
            .map((l) => (
              <a key={l.href} href={l.href} className="hover:text-ark-brown transition-colors">
                {lang === "KO" ? l.ko : l.en}
              </a>
            ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="flex items-center gap-1 bg-[#F3F0EB] p-1 rounded-md border border-[#E8E2D9]">
            <Globe className="w-3.5 h-3.5 text-ark-grey ml-1" />
            <button
              onClick={() => setLang("KO")}
              className={`px-2 py-1 rounded text-[11px] font-bold ${
                lang === "KO" ? "bg-white shadow-sm text-ark-brown" : "text-ark-grey"
              }`}
            >
              KO
            </button>
            <button
              onClick={() => setLang("EN")}
              className={`px-2 py-1 rounded text-[11px] font-bold ${
                lang === "EN" ? "bg-white shadow-sm text-ark-brown" : "text-ark-grey"
              }`}
            >
              EN
            </button>
          </div>

          <a
            href="/account"
            className="hidden sm:inline text-sm font-semibold text-ark-grey hover:text-ark-brown"
          >
            {lang === "KO" ? "내정보" : "Profile"}
          </a>
          <a
            href="/login"
            className="hidden sm:inline px-4 py-1.5 border border-ark-brown text-ark-brown rounded text-sm font-semibold hover:bg-ark-brown hover:text-white transition-colors"
          >
            {lang === "KO" ? "로그인" : "Login"}
          </a>
          <button
            type="button"
            className="md:hidden p-2 rounded-md border border-[#E8E2D9] text-ark-navy"
            aria-label={lang === "KO" ? "메뉴" : "Menu"}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((o) => !o)}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t border-[#E8E2D9] bg-ark-white">
          <nav className="max-w-6xl mx-auto px-4 py-3 flex flex-col gap-1">
            {links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setMobileOpen(false)}
                className="px-3 py-2.5 rounded-lg text-sm font-medium text-ark-navy hover:bg-[#F3F0EB]"
              >
                {lang === "KO" ? l.ko : l.en}
              </a>
            ))}
            <a
              href="/login"
              onClick={() => setMobileOpen(false)}
              className="mt-1 px-3 py-2.5 rounded-lg text-sm font-semibold text-ark-brown border border-ark-brown text-center"
            >
              {lang === "KO" ? "로그인 / 회원가입" : "Login / Sign up"}
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}

type ChatMsg = { sender: "user" | "bot"; text: string; citations?: any[] };

const CHAT_STORAGE_KEY = "ark_assistant_messages_v1";
const CHAT_OPEN_KEY = "ark_assistant_open_v1";
const CHAT_SIZE_KEY = "ark_assistant_size_v1";

/** 마크다운(#, **, >, 목록 *) 제거 — 읽기 쉬운 평문 */
function cleanAssistantText(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^\*\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** 자유 드래그 + 리사이즈. 대화는 sessionStorage(탭 종료 시 삭제). 창 크기만 localStorage. */
function DraggableChatbot() {
  const { lang } = useLang();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const [loading, setLoading] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 380, height: 500 });
  const abortRef = useRef<AbortController | null>(null);
  const stoppedByUserRef = useRef(false);
  const dragControls = useDragControls();

  const openAssistant = (val: boolean) => {
    setIsOpen(val);
    try {
      sessionStorage.setItem(CHAT_OPEN_KEY, val ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

  const saveMessages = (next: ChatMsg[]) => {
    try {
      sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore quota */
    }
  };

  useEffect(() => {
    try {
      // 예전 localStorage 대화는 제거 (영구 보관 방지)
      localStorage.removeItem(CHAT_STORAGE_KEY);
      localStorage.removeItem(CHAT_OPEN_KEY);
      const raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) setMessages(parsed);
      }
      const openRaw = sessionStorage.getItem(CHAT_OPEN_KEY);
      if (openRaw === "1") setIsOpen(true);
      const sizeRaw = localStorage.getItem(CHAT_SIZE_KEY);
      if (sizeRaw) {
        const parsed = JSON.parse(sizeRaw);
        if (parsed?.width && parsed?.height) setDimensions(parsed);
      }
    } catch {
      /* ignore */
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveMessages(messages);
  }, [messages, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(CHAT_SIZE_KEY, JSON.stringify(dimensions));
    } catch {
      /* ignore */
    }
  }, [dimensions, hydrated]);

  useEffect(() => {
    // sessionStorage는 탭 간 storage 이벤트가 거의 없음 — 동기화 생략
    return;
  }, [hydrated]);

  useEffect(() => {
    const pullPrefill = () => {
      try {
        const pre = sessionStorage.getItem("ark_assistant_prefill");
        if (pre) {
          setInputVal(pre);
          openAssistant(true);
          sessionStorage.removeItem("ark_assistant_prefill");
        }
      } catch {
        /* ignore */
      }
    };
    pullPrefill();
    const onPrefill = () => pullPrefill();
    window.addEventListener("ark-assistant-prefill", onPrefill);
    return () => window.removeEventListener("ark-assistant-prefill", onPrefill);
  }, [hydrated]);

  const handleStop = () => {
    stoppedByUserRef.current = true;
    if (abortRef.current) {
      try {
        abortRef.current.abort();
      } catch {
        /* ignore */
      }
      abortRef.current = null;
    }
    setLoading(false);
    setMessages((prev) => [
      ...prev,
      {
        sender: "bot",
        text:
          lang === "KO"
            ? "사용자가 답변 생성을 중단했습니다. DB에 등록된 자료는 탐색/원어에서 확인하세요."
            : "Stopped. Check registered records in Explore / Lexicon.",
      },
    ]);
  };

  const handleClearChat = () => {
    if (loading) {
      stoppedByUserRef.current = true;
      if (abortRef.current) {
        try {
          abortRef.current.abort();
        } catch {
          /* ignore */
        }
        abortRef.current = null;
      }
      setLoading(false);
    }
    setMessages([]);
    try {
      sessionStorage.removeItem(CHAT_STORAGE_KEY);
    } catch {
      /* ignore */
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim() || loading) return;
    const userMsg = inputVal;
    let apiQuery = userMsg;
    try {
      const ctx = sessionStorage.getItem("ark_assistant_context");
      if (ctx) {
        apiQuery =
          lang === "KO"
            ? `${userMsg}\n\n[참고 DB 기록]\n${ctx}`
            : `${userMsg}\n\n[Registered DB notes]\n${ctx}\n\nReply in English.`;
        sessionStorage.removeItem("ark_assistant_context");
      }
    } catch {
      /* ignore */
    }
    setMessages((prev) => [...prev, { sender: "user", text: userMsg }]);
    setInputVal("");
    setLoading(true);
    stoppedByUserRef.current = false;

    abortRef.current = new AbortController();
    const id = setTimeout(() => abortRef.current?.abort(), 90000);

    try {
      const res = await fetch(
        `${API}/api/assistant/chat?query=${encodeURIComponent(apiQuery)}&username=free_user&lang=${lang}`,
        { signal: abortRef.current.signal, cache: "no-store" }
      );
      clearTimeout(id);
      const data = await res.json();
      if (!res.ok) {
        const detail =
          typeof data?.detail === "object"
            ? data.detail.message
            : data?.detail || "API Error";
        throw new Error(detail);
      }
      const cites = data.source_citations || [];
      let text = cleanAssistantText(data.answer || "");
      if (cites.length) {
        text +=
          (lang === "KO" ? "\n\n— 출처 —\n" : "\n\n— Sources —\n") +
          cites
            .map((c: any, i: number) => {
              const author = (c.author || "").trim();
              const title = (c.title || c.source || "Source").trim();
              const lic = c.license_type || c.copyright_status || c.license || "";
              // 제목·attribution 중복 제거, 한 줄로 축약
              let head = author && title && !title.includes(author) ? `${author} · ${title}` : author || title;
              if (head.length > 80) head = `${head.slice(0, 77)}…`;
              const line = `${i + 1}. ${head}${lic ? ` (${lic})` : ""}`;
              const url = (c.source_url || "").trim();
              // 긴 GitHub raw 경로 대신 호스트만 힌트
              if (!url) return line;
              try {
                const u = new URL(url);
                return `${line}\n   ${u.hostname}`;
              } catch {
                return line;
              }
            })
            .join("\n");
      }
      setMessages((prev) => [...prev, { sender: "bot", text, citations: cites }]);
    } catch (err: any) {
      const isAbort = err?.name === "AbortError";
      if (isAbort && stoppedByUserRef.current) {
        stoppedByUserRef.current = false;
        return;
      }
      setMessages((prev) => [
        ...prev,
        {
          sender: "bot",
          text: isAbort
            ? lang === "KO"
              ? "답변 생성 시간이 초과되었거나 중단되었습니다. DB에 등록된 자료는 탐색/원어에서 확인하세요."
              : "Response timed out or stopped. Check registered records in Explore / Lexicon."
            : err?.message ||
              (lang === "KO"
                ? "죄송합니다. 백엔드 서버에서 답변을 가져올 수 없었습니다."
                : "Sorry, could not retrieve response from the backend server."),
        },
      ]);
    } finally {
      clearTimeout(id);
      abortRef.current = null;
      setLoading(false);
    }
  };

  const handleResizeRight = (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startY = e.clientY;
    const startWidth = dimensions.width;
    const startHeight = dimensions.height;
    const onPointerMove = (moveEvent: PointerEvent) => {
      setDimensions({
        width: Math.max(320, startWidth + (moveEvent.clientX - startX)),
        height: Math.max(400, startHeight + (moveEvent.clientY - startY)),
      });
    };
    const onPointerUp = () => {
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
      try {
        localStorage.setItem(CHAT_SIZE_KEY, JSON.stringify(dimensions));
      } catch {}
    };
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
  };

  const handleResizeLeft = (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startY = e.clientY;
    const startWidth = dimensions.width;
    const startHeight = dimensions.height;
    const onPointerMove = (moveEvent: PointerEvent) => {
      setDimensions({
        width: Math.max(320, startWidth + (startX - moveEvent.clientX)),
        height: Math.max(400, startHeight + (moveEvent.clientY - startY)),
      });
    };
    const onPointerUp = () => {
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
      try {
        localStorage.setItem(CHAT_SIZE_KEY, JSON.stringify(dimensions));
      } catch {}
    };
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
  };

  return (
    <motion.div
      drag
      dragControls={dragControls}
      dragListener={false}
      dragMomentum={false}
      dragElastic={0}
      className="fixed top-24 right-10 z-50 flex flex-col items-end"
      style={{ touchAction: "none" }}
    >
      <button
        onPointerDown={(e) => {
          e.stopPropagation();
          dragControls.start(e);
        }}
        onClick={() => openAssistant(!isOpen)}
        className="w-16 h-16 bg-ark-navy text-white rounded-full shadow-2xl flex items-center justify-center hover:bg-ark-brown hover:scale-105 transition-all group border-2 border-white/20 mb-4 z-10 cursor-grab active:cursor-grabbing"
      >
        <Bot className="w-8 h-8 group-hover:animate-pulse text-ark-gold" />
      </button>

      {isOpen && (
        <div
          className="bg-white border border-[#E8E2D9] rounded-2xl shadow-2xl flex flex-col overflow-hidden relative"
          style={{ width: `${dimensions.width}px`, height: `${dimensions.height}px` }}
        >
          <div
            onPointerDown={(e) => {
              e.stopPropagation();
              dragControls.start(e);
            }}
            className="bg-ark-navy p-4 text-white flex justify-between items-center cursor-grab active:cursor-grabbing select-none shrink-0"
          >
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-ark-gold" />
              <span className="font-semibold text-sm tracking-wide">ARK Assistant</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  handleClearChat();
                }}
                className="flex items-center gap-1 px-2 py-1 rounded-md hover:bg-white/10 text-xs"
                title={lang === "KO" ? "대화 지우기" : "Clear chat"}
              >
                <Eraser className="w-3.5 h-3.5" />
                {lang === "KO" ? "대화 지우기" : "Clear"}
              </button>
              <button
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  openAssistant(false);
                }}
                className="hover:text-ark-gold"
                title={lang === "KO" ? "닫기 (탭을 닫으면 대화가 삭제됩니다)" : "Close (chat clears when tab closes)"}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="flex-1 p-4 overflow-y-auto bg-ark-bg text-sm space-y-4">
            <div className="bg-white p-3 rounded-lg border border-[#E8E2D9] inline-block max-w-[90%] text-ark-navy shadow-sm leading-relaxed">
              {lang === "KO"
                ? "연구 보조 어시스턴트입니다. DB에 등록된 기록만 근거로 설명합니다. 브라우저 탭을 닫으면 대화는 삭제됩니다. 생성 중에는 정지로 중단할 수 있습니다."
                : "Research helper: answers from registered DB records only. Chat is cleared when you close this tab. You can stop a response anytime."}
            </div>

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`p-3 rounded-lg max-w-[95%] shadow-sm leading-relaxed whitespace-pre-line ${
                    msg.sender === "user"
                      ? "bg-ark-brown text-white font-medium"
                      : "bg-white border border-[#E8E2D9] text-ark-navy"
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-[#E8E2D9] p-3 rounded-lg shadow-sm flex items-center gap-2 text-ark-grey">
                  <div
                    className="w-2 h-2 bg-ark-grey rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <div
                    className="w-2 h-2 bg-ark-grey rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <div
                    className="w-2 h-2 bg-ark-grey rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                  <span>{lang === "KO" ? "공개 자료 검색·해석 중..." : "Searching registered sources…"}</span>
                </div>
              </div>
            )}
          </div>

          <form
            onSubmit={handleSendMessage}
            className="p-3 border-t border-[#E8E2D9] bg-white shrink-0 flex gap-2 items-center"
          >
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder={
                lang === "KO" ? "질문을 입력하고 엔터를 치세요..." : "Enter your query..."
              }
              className="flex-1 min-w-0 px-3 py-2 border border-[#E8E2D9] rounded-lg focus:outline-none focus:border-ark-brown text-sm bg-ark-bg"
            />
            {loading && (
              <button
                type="button"
                onClick={handleStop}
                className="shrink-0 flex items-center gap-1 px-3 py-2 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 text-xs font-semibold border border-red-200"
              >
                <Square className="w-3 h-3 fill-current" />
                {lang === "KO" ? "정지" : "Stop"}
              </button>
            )}
          </form>

          <div
            onPointerDown={handleResizeLeft}
            className="absolute bottom-0 left-0 w-4 h-4 cursor-nesw-resize z-20 hover:bg-ark-brown/20 active:bg-ark-brown/40 rounded-bl-2xl transition-colors"
          />
          <div
            onPointerDown={handleResizeRight}
            className="absolute bottom-0 right-0 w-4 h-4 cursor-nwse-resize z-20 hover:bg-ark-brown/20 active:bg-ark-brown/40 rounded-br-2xl transition-colors"
          />
        </div>
      )}
    </motion.div>
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="font-sans antialiased text-ark-navy bg-ark-bg selection:bg-ark-gold/30">
        <LangProvider>
          <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1 w-full">{children}</main>
            <DraggableChatbot />
            <footer className="w-full py-5 text-center text-[11px] text-ark-grey border-t border-[#E8E2D9] bg-ark-white">
              © 2026 ARK · Biblical Knowledge Platform
            </footer>
          </div>
        </LangProvider>
      </body>
    </html>
  );
}
