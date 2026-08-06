"use client";

import { useLang } from "../LangContext";

export default function HelpPage() {
  const { lang } = useLang();

  const t =
    lang === "KO"
      ? {
          title: "도움말",
          intro:
            "ARK는 노아의 방주(Ark)에서 이름을 따왔습니다. 말씀과 그 기원·어원을 한곳에 모아 둔 지식 데이터베이스입니다.",
          sections: [
            {
              h: "ARK란?",
              p: "방주가 생명을 품었듯, ARK는 성경 본문·인물·사건·원어의 뿌리를 품는 지식 공간입니다. 구절을 찾고, 단어의 뜻을 살피며, 이야기가 어떻게 이어지는지 따라갈 수 있습니다.",
            },
            {
              h: "탐색(검색)",
              p: "책·장·절을 넣으면 해당 본문을 보여 줍니다. 예: 「창세기 4장」, 「요한복음 3:16」, 「로마서 8 1」. 인물·사건 이름으로도 찾을 수 있습니다. 별(스크랩)로 내 서재에 담을 수 있습니다.",
            },
            {
              h: "내 서재",
              p: "스크랩한 항목이 모이는 개인 공간입니다. 로그인 연동 전까지는 이 브라우저에 저장됩니다.",
            },
            {
              h: "토론방",
              p: "구절·사건·주제에 매달린 대화 공간입니다.",
            },
            {
              h: "원어 연구",
              p: "성경 단어마다 붙은 Strong 번호(예: G0026)로 원문·발음·영문 정의를 봅니다. 이 번호는 ARK가 만든 것이 아니라, 오래전부터 쓰인 Strong’s 사전 번호입니다. 한국어 설명은 어시스턴트에게 요청하면 됩니다.",
            },
            {
              h: "AI 어시스턴트",
              p: "검색과 원어 연구를 돕는 보조입니다. DB에 있는 기록만 근거로 설명하고, 없는 내용은 지어내지 않도록 설계되어 있습니다.",
            },
            {
              h: "교단·호칭",
              p: "가톨릭·개신교·정교회는 호칭과 강조점이 다를 수 있습니다. 전통을 라벨로 구분해 비교하는 방식을 권합니다.",
            },
          ],
          faqTitle: "자주 묻는 질문",
          faqs: [
            {
              q: "G0026 같은 번호는 뭔가요?",
              a: "Strong’s 번호입니다. 헬라어는 G, 히브리어는 H로 시작합니다. 연구자들이 같은 원어 단어를 가리킬 때 쓰는 표준 번호이며, ARK가 임의로 붙인 것이 아닙니다.",
            },
            {
              q: "장만 검색해도 되나요?",
              a: "네. 「창세기 4장」처럼 책과 장만 넣으면 그 장의 구절 목록이 나옵니다.",
            },
          ],
          planLink: "요금제 미리보기 →",
        }
      : {
          title: "Help",
          intro:
            "ARK takes its name from Noah’s Ark—a knowledge database of Scripture, origins, and word roots.",
          sections: [
            {
              h: "What is ARK?",
              p: "A place to hold verses, people, events, and lexical roots together—so you can follow the text and its origins.",
            },
            {
              h: "Explore (Search)",
              p: "Search by book, chapter, or verse—e.g. Genesis 4, John 3:16. You can also search people and events, then star items into your Library.",
            },
            {
              h: "Library",
              p: "Your saved items. Stored in this browser until account sync.",
            },
            {
              h: "Forum",
              p: "Discussion anchored to verses, events, or topics.",
            },
            {
              h: "Lexicon",
              p: "Look up Strong’s numbers (e.g. G0026)—a long-standing dictionary index, not something ARK invented. Ask the assistant to explain registered entries in your language.",
            },
            {
              h: "AI assistant",
              p: "A helper that explains from registered records only.",
            },
            {
              h: "Traditions",
              p: "Catholic / Protestant / Orthodox may differ; compare with clear labels.",
            },
          ],
          faqTitle: "FAQ",
          faqs: [
            {
              q: "What is G0026?",
              a: "A Strong’s number. G = Greek, H = Hebrew. Standard lexicon indexing—not invented by ARK.",
            },
            {
              q: "Can I search a whole chapter?",
              a: "Yes. Try “Genesis 4” or “John 3:16”.",
            },
          ],
          planLink: "Preview plans →",
        };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 py-12 pb-24">
      <h1 className="font-serif text-3xl md:text-4xl font-bold text-ark-navy text-center mb-3">
        {t.title}
      </h1>
      <p className="text-center text-ark-grey text-[15px] leading-relaxed mb-10 max-w-xl mx-auto">
        {t.intro}
      </p>

      <div className="space-y-5">
        {t.sections.map((s) => (
          <section
            key={s.h}
            className="bg-white border border-[#E8E2D9] rounded-2xl p-6 shadow-soft"
          >
            <h2 className="font-serif text-xl font-bold text-ark-navy mb-2">{s.h}</h2>
            <p className="text-sm text-ark-navy/80 leading-relaxed">{s.p}</p>
          </section>
        ))}

        <section className="bg-white border border-[#E8E2D9] rounded-2xl p-6 shadow-soft">
          <h2 className="font-serif text-xl font-bold text-ark-navy mb-4">{t.faqTitle}</h2>
          <div className="space-y-4">
            {t.faqs.map((f) => (
              <div key={f.q}>
                <h3 className="font-semibold text-ark-navy text-sm">{f.q}</h3>
                <p className="text-sm text-ark-grey mt-1 leading-relaxed">{f.a}</p>
              </div>
            ))}
          </div>
          <a
            href="/pricing"
            className="inline-block mt-6 text-sm font-semibold text-ark-brown hover:underline"
          >
            {t.planLink}
          </a>
        </section>
      </div>
    </div>
  );
}
