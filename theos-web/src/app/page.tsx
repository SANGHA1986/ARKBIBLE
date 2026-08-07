"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  BookOpen,
  User,
  CalendarDays,
  MapPin,
  GitBranch,
  Languages,
  Landmark,
  Cross,
  FileSearch,
  FileText,
  TrendingUp,
  Flame,
  BookMarked,
  Library,
} from "lucide-react";
import { useLang } from "./LangContext";

import { API } from "../lib/api";

const TOPICS = [
  {
    id: "genesis",
    ko: "창세기의 약속",
    en: "Promise in Genesis",
    queryKo: "창세기",
    queryEn: "Genesis",
    image: "/topics/genesis.jpg",
  },
  {
    id: "romans",
    ko: "로마서와 믿음",
    en: "Faith in Romans",
    queryKo: "로마서",
    queryEn: "Romans",
    image: "/topics/romans.jpg",
  },
  {
    id: "jesus",
    ko: "마태복음 서두",
    en: "Opening of Matthew",
    queryKo: "마태복음",
    queryEn: "Matthew",
    image: "/topics/jesus.jpg",
  },
  {
    id: "paul",
    ko: "바울의 선교 여행",
    en: "Paul's Missionary Journeys",
    queryKo: "바울",
    queryEn: "Paul",
    image: "/topics/paul.jpg",
  },
  {
    id: "covenant",
    ko: "하나님의 언약",
    en: "God's Covenant",
    queryKo: "언약",
    queryEn: "covenant",
    image: "/topics/covenant.jpg",
  },
];

const CATEGORIES = [
  {
    ko: "성경",
    en: "Bible",
    icon: BookOpen,
    hrefKo: "/search?q=성경",
    hrefEn: "/search?q=Bible",
  },
  {
    ko: "인물",
    en: "People",
    icon: User,
    hrefKo: "/search?q=인물",
    hrefEn: "/search?q=People",
  },
  {
    ko: "사건",
    en: "Events",
    icon: CalendarDays,
    hrefKo: "/search?q=사건",
    hrefEn: "/search?q=Events",
  },
  {
    ko: "장소",
    en: "Places",
    icon: MapPin,
    hrefKo: "/search?q=장소",
    hrefEn: "/search?q=Places",
  },
  {
    ko: "교리",
    en: "Doctrine",
    icon: GitBranch,
    hrefKo: "/search?q=교리",
    hrefEn: "/search?q=Doctrine",
  },
  { ko: "원어", en: "Lexicon", icon: Languages, hrefKo: "/study?strong=G0026", hrefEn: "/study?strong=G0026" },
  {
    ko: "교부",
    en: "Fathers",
    icon: Landmark,
    hrefKo: "/search?q=교부",
    hrefEn: "/search?q=Fathers",
  },
  {
    ko: "종교개혁",
    en: "Reformation",
    icon: Cross,
    hrefKo: "/search?q=종교개혁",
    hrefEn: "/search?q=Reformation",
  },
  {
    ko: "주석",
    en: "Commentary",
    icon: FileSearch,
    hrefKo: "/search?q=주석",
    hrefEn: "/search?q=Commentary",
  },
  {
    ko: "논문",
    en: "Papers",
    icon: FileText,
    hrefKo: "/search?q=논문",
    hrefEn: "/search?q=papers",
  },
  {
    ko: "자료",
    en: "Sources",
    icon: Library,
    hrefKo: "/search?q=자료",
    hrefEn: "/search?q=Sources",
  },
];

function TopicCard({
  title,
  image,
  onClick,
}: {
  title: string;
  image: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="snap-start shrink-0 w-[168px] h-[112px] rounded-xl overflow-hidden relative text-left shadow-card group"
    >
      <img
        src={image}
        alt=""
        className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/25 to-transparent" />
      <div className="relative h-full flex flex-col justify-end p-3">
        <span className="text-white font-serif font-bold text-[13px] leading-snug drop-shadow group-hover:text-ark-gold transition-colors">
          {title}
        </span>
      </div>
    </button>
  );
}

type FeedItem = {
  type: "verse" | "character" | "material";
  title: string;
  subtitle: string;
  link: string;
  badge: string;
};

export default function Home() {
  const { lang } = useLang();
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [feedLoading, setFeedLoading] = useState(true);
  const [bootMsg, setBootMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setFeed([]);
    setFeedLoading(true);
    fetch(`${API}/api/feed/trending?lang=${lang}`)
      .then((res) => (res.ok ? res.json() : { feed: [] }))
      .then((json) => {
        if (!cancelled) setFeed((json.feed || []) as FeedItem[]);
      })
      .catch(() => {
        if (!cancelled) setFeed([]);
      })
      .finally(() => {
        if (!cancelled) setFeedLoading(false);
      });

    fetch(`${API}/api/bootstrap/status`)
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        if (cancelled || !json) return;
        const verses = Number(json.verses_now || json.verses || 0);
        const commentaries = Number(json.commentaries_now || json.commentaries || 0);
        const characters = Number(json.characters_now || json.characters || 0);
        const sources = Number(json.sources_now || json.sources || 0);
        if (json.running) {
          setBootMsg(
            lang === "KO"
              ? `테스트 데이터 적재 중… (${json.phase || ""} / 성경본문 ${verses.toLocaleString()} · 구절주석조각 ${commentaries.toLocaleString()} · 인물 ${characters} · 등록자료 ${sources}). 완료까지 새로고침해 주세요.`
              : `Loading beta data… (${json.phase || ""} / Bible verses ${verses.toLocaleString()}, verse-commentary rows ${commentaries.toLocaleString()}, people ${characters}, sources ${sources}). Refresh until done.`
          );
        } else if (verses < 30000 || commentaries < 500 || characters < 20) {
          setBootMsg(
            lang === "KO"
              ? `적재가 아직 부족합니다 (본문 ${verses.toLocaleString()} · 주석 ${commentaries.toLocaleString()} · 인물 ${characters}). 잠시 후 새로고침하거나 API를 재배포해 주세요.`
              : `Bootstrap still thin (verses ${verses}, commentaries ${commentaries}, people ${characters}). Refresh or redeploy API.`
          );
        } else {
          setBootMsg(null);
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [lang]);

  const localizeBadge = (badge: string) => {
    const mapKo: Record<string, string> = {
      Hot: "인기",
      Topic: "주제",
      Character: "인물",
      Commentary: "주석",
      Source: "자료",
      Lexicon: "원어",
      Book: "서적",
      Paper: "논문",
      논문: "논문",
    };
    const mapEn: Record<string, string> = {
      인기: "Hot",
      주제: "Topic",
      인물: "Character",
      주석: "Commentary",
      자료: "Source",
      원어: "Lexicon",
      서적: "Book",
      논문: "Paper",
      Paper: "Paper",
    };
    if (lang === "KO") return mapKo[badge] || badge;
    return mapEn[badge] || badge;
  };

  const topicHref = (topic: (typeof TOPICS)[number]) =>
    `/search?q=${encodeURIComponent(lang === "KO" ? topic.queryKo : topic.queryEn)}`;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    const q = encodeURIComponent(searchQuery.trim());
    if (/^[GgHh]\d+$/.test(searchQuery.trim())) {
      router.push(`/study?strong=${searchQuery.trim().toUpperCase()}`);
    } else {
      router.push(`/search?q=${q}`);
    }
  };

  const copy =
    lang === "KO"
      ? {
          subtitle: "노아의 방주에서 이름을 딴, 말씀과 기원·어원을 모은 지식 데이터베이스입니다.",
          placeholder:
            "성경 구절, 인물, 사건, 원어, 장소, 신학 주제, 역사적 배경을 검색하세요.",
          today: "실시간 인기 콘텐츠",
          explore: "탐색 카테고리",
          live: "흐르는 연구 노트",
          loading: "불러오는 중…",
          catHint:
            "성경=본문 · 주석=주석 자료 · 논문=논문. 써진 이름대로만 연결됩니다.",
        }
      : {
          subtitle:
            "Named after Noah’s Ark—a knowledge database of Scripture, origins, and word roots.",
          placeholder:
            "Search verses, people, events, lexicon, places, topics, papers…",
          today: "Live Trending Content",
          explore: "Explore Categories",
          live: "Research Feed",
          loading: "Loading…",
          catHint:
            "Bible=verses · Commentary=commentaries · Papers=papers. Each opens its own list.",
        };

  const topicRow = TOPICS.map((topic) => (
    <TopicCard
      key={`${lang}-${topic.id}`}
      title={lang === "KO" ? topic.ko : topic.en}
      image={topic.image}
      onClick={() => router.push(topicHref(topic))}
    />
  ));

  const feedRow = (feed.length ? feed : TOPICS.map((t) => ({
    type: "verse" as const,
    title: lang === "KO" ? t.ko : t.en,
    subtitle: "",
    link: topicHref(t),
    badge: lang === "KO" ? "주제" : "Topic",
  }))).map((item, idx) => {
    const Icon =
      item.type === "verse" ? BookMarked
      : item.type === "character" ? User
      : Library;
    const badge = localizeBadge(item.badge);
    const isHot = badge === "Hot" || badge === "인기";
    return (
      <button
        key={`${lang}-feed-${idx}-${item.title}`}
        type="button"
        onClick={() => router.push(item.link)}
        className="snap-start shrink-0 w-[200px] h-[112px] rounded-xl overflow-hidden relative text-left bg-white border border-[#E8E2D9] shadow-soft hover:border-ark-brown transition-colors group p-3 flex flex-col justify-between"
      >
        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-ark-brown/10 text-ark-brown text-[10px] font-bold">
            {isHot && <Flame className="w-3 h-3" />}
            {badge}
          </span>
          <Icon className="w-4 h-4 text-ark-grey/60" />
        </div>
        <div>
          <div className="font-serif font-bold text-sm text-ark-navy leading-snug line-clamp-2 group-hover:text-ark-brown transition-colors">
            {item.title}
          </div>
          {item.subtitle && (
            <div className="text-[10px] text-ark-grey mt-0.5 line-clamp-1">
              {item.subtitle}
            </div>
          )}
        </div>
      </button>
    );
  });

  return (
    <div className="w-full">
      <section className="max-w-6xl mx-auto px-4 md:px-6 pt-14 md:pt-20 pb-10 md:pb-14 text-center">
        <h1 className="font-serif text-[28px] sm:text-[36px] md:text-[44px] font-bold text-ark-navy tracking-tight leading-snug">
          {lang === "KO" ? (
            <>
              성경을 더 깊이{" "}
              <span className="text-ark-brown">연구</span>
              하십시오.
            </>
          ) : (
            <>
              Study the Bible more{" "}
              <span className="text-ark-brown italic">deeply</span>.
            </>
          )}
        </h1>
        <p className="mt-4 text-[15px] md:text-[17px] text-ark-grey max-w-2xl mx-auto leading-relaxed">
          {copy.subtitle}
        </p>

        <form onSubmit={handleSearch} className="mt-10 max-w-3xl mx-auto">
          <div className="flex items-center bg-[#F0EEE9] border border-[#E0DBD2] rounded-2xl overflow-hidden shadow-soft focus-within:border-ark-brown focus-within:bg-white transition-colors">
            <div className="pl-5 text-ark-brown">
              <Search className="w-5 h-5 md:w-6 md:h-6" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={copy.placeholder}
              className="w-full bg-transparent border-none outline-none text-ark-navy px-4 py-4 md:py-5 text-[14px] md:text-[15px] placeholder:text-[#9AA3AD]"
            />
            <button
              type="submit"
              disabled={isSearching}
              className="mr-2 md:mr-3 px-4 py-2.5 rounded-xl bg-ark-brown text-white text-sm font-semibold hover:bg-[#9A5C00] disabled:opacity-50 transition-colors shrink-0"
            >
              {lang === "KO" ? "검색" : "Search"}
            </button>
          </div>
        </form>
      </section>

      {bootMsg && (
        <div className="max-w-6xl mx-auto px-4 md:px-6 pb-4">
          <div className="rounded-xl border border-ark-brown/30 bg-[#FFF8EF] px-4 py-3 text-sm text-ark-navy leading-relaxed">
            {bootMsg}
          </div>
        </div>
      )}

      {/* Live trending feed — real data from DB */}
      <section className="max-w-6xl mx-auto px-4 md:px-6 pb-10 md:pb-14">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-ark-brown" />
          <h2 className="font-serif text-base md:text-lg font-bold text-ark-navy">
            {copy.today}
          </h2>
          {feedLoading && (
            <span className="text-[11px] text-ark-grey ml-2">{copy.loading}</span>
          )}
        </div>
        <div className="relative overflow-hidden masked-marquee">
          <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-10 bg-gradient-to-r from-ark-bg to-transparent z-10" />
          <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-10 bg-gradient-to-l from-ark-bg to-transparent z-10" />
          <div className="flex w-max animate-marquee gap-3 hover:[animation-play-state:paused]">
            <div className="flex shrink-0 gap-3">{feedRow}</div>
            <div className="flex shrink-0 gap-3" aria-hidden>
              {feedRow}
            </div>
          </div>
        </div>
      </section>

      {/* Topics — image cards + continuous horizontal marquee */}
      <section className="max-w-6xl mx-auto px-4 md:px-6 pb-10 md:pb-14">
        <h2 className="font-serif text-base md:text-lg font-bold text-ark-navy mb-4">
          {copy.live}
        </h2>
        <div className="relative overflow-hidden masked-marquee">
          <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-10 bg-gradient-to-r from-ark-bg to-transparent z-10" />
          <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-10 bg-gradient-to-l from-ark-bg to-transparent z-10" />
          <div className="flex w-max animate-marquee gap-3 hover:[animation-play-state:paused]">
            <div className="flex shrink-0 gap-3">{topicRow}</div>
            <div className="flex shrink-0 gap-3" aria-hidden>
              {TOPICS.map((topic) => (
                <TopicCard
                  key={`${lang}-dup-${topic.id}`}
                  title={lang === "KO" ? topic.ko : topic.en}
                  image={topic.image}
                  onClick={() => router.push(topicHref(topic))}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Categories — narrower grid, centered (less clutter) */}
      <section className="max-w-6xl mx-auto px-4 md:px-6 pb-16 md:pb-20">
        <h2 className="font-serif text-base md:text-lg font-bold text-ark-navy mb-1">
          {copy.explore}
        </h2>
        <p className="text-[11px] text-ark-grey mb-4 leading-relaxed">{copy.catHint}</p>
        <div className="max-w-3xl mx-auto grid grid-cols-5 gap-1.5 md:gap-2">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            return (
              <button
                key={cat.en}
                onClick={() =>
                  router.push(lang === "KO" ? cat.hrefKo : cat.hrefEn)
                }
                className="flex flex-col items-center justify-center gap-1.5 py-2.5 md:py-3 rounded-lg bg-white border border-[#E8E2D9] hover:border-ark-brown hover:shadow-soft group transition-all"
              >
                <div className="w-8 h-8 md:w-9 md:h-9 rounded-full border-2 border-ark-brown/40 text-ark-brown flex items-center justify-center group-hover:bg-ark-brown group-hover:text-white transition-colors">
                  <Icon className="w-4 h-4 md:w-[18px] md:h-[18px]" strokeWidth={2} />
                </div>
                <span className="text-[11px] md:text-[12px] font-semibold text-ark-navy group-hover:text-ark-brown transition-colors">
                  {lang === "KO" ? cat.ko : cat.en}
                </span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
