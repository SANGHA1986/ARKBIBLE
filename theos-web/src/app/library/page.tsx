"use client";

import { useEffect, useState } from "react";
import { Bookmark, Star, Trash2 } from "lucide-react";
import { useLang } from "../LangContext";
import { loadScraps, saveScraps, type ScrapItem } from "../../lib/libraryStore";

export default function LibraryPage() {
  const { lang } = useLang();
  const [items, setItems] = useState<ScrapItem[]>([]);

  useEffect(() => {
    setItems(loadScraps());
  }, []);

  const t =
    lang === "KO"
      ? {
          title: "내 서재",
          subtitle: "탐색에서 별(스크랩)로 담은 항목이 여기에 모입니다. 로그인 연동 전까지 이 브라우저에 저장됩니다.",
          empty: "아직 스크랩한 항목이 없습니다. 탐색에서 별 버튼을 눌러 보세요.",
          explore: "탐색으로 가기",
          remove: "삭제",
          savedAt: "저장",
        }
      : {
          title: "My Library",
          subtitle: "Starred items from Explore appear here. Stored in this browser until account sync.",
          empty: "No saved items yet. Star results in Explore.",
          explore: "Go to Explore",
          remove: "Remove",
          savedAt: "Saved",
        };

  const remove = (id: string) => {
    const next = items.filter((i) => i.id !== id);
    saveScraps(next);
    setItems(next);
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 py-10 pb-24">
      <div className="flex items-center gap-2 text-ark-brown mb-2">
        <Bookmark className="w-5 h-5" />
        <h1 className="font-serif text-2xl md:text-3xl font-bold text-ark-navy">{t.title}</h1>
      </div>
      <p className="text-sm text-ark-grey leading-relaxed mb-8">{t.subtitle}</p>

      {items.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-[#E8E2D9] rounded-2xl bg-white">
          <Star className="w-8 h-8 text-ark-gold mx-auto mb-3" />
          <p className="text-ark-grey text-sm mb-4">{t.empty}</p>
          <a
            href="/search"
            className="inline-block px-4 py-2 rounded-lg bg-ark-brown text-white text-sm font-semibold"
          >
            {t.explore}
          </a>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <article
              key={item.id}
              className="bg-white border border-[#E8E2D9] rounded-2xl p-5 shadow-soft"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wide text-ark-brown">
                    {item.kind}
                  </div>
                  <h2 className="font-serif font-bold text-lg text-ark-navy mt-1">
                    {item.href ? (
                      <a href={item.href} className="hover:text-ark-brown">
                        {item.title}
                      </a>
                    ) : (
                      item.title
                    )}
                  </h2>
                  {item.subtitle && (
                    <p className="text-xs text-ark-grey mt-1">{item.subtitle}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => remove(item.id)}
                  className="text-ark-grey hover:text-red-600 p-1"
                  title={t.remove}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              {item.body && (
                <p className="text-sm text-ark-navy/80 mt-3 leading-relaxed line-clamp-4">
                  {item.body}
                </p>
              )}
              <div className="text-[11px] text-ark-grey mt-3">
                {t.savedAt}: {new Date(item.savedAt).toLocaleString()}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
