"use client";

import { useLang } from "../LangContext";

export default function PricingPage() {
  const { lang } = useLang();

  const t =
    lang === "KO"
      ? {
          title: "요금제",
          intro:
            "7일 무료 체험 후 24시간 맛보기가 끝나면 구독이 필요합니다. (결제 연동은 추후 — 지금은 게이트 UI)",
          plans: [
            { name: "Free Trial", desc: "가입 후 7일 무제한", price: "₩0" },
            { name: "Limited 24h", desc: "만료 후 하루 맛보기 (일일 조회 제한)", price: "₩0" },
            { name: "Paid", desc: "무제한 원어·주석·AI 연구", price: "추후 공개" },
            { name: "Institution", desc: "신학교·교단 라이선스", price: "문의" },
          ],
          back: "← 도움말로 돌아가기",
        }
      : {
          title: "Pricing",
          intro:
            "After a 7-day free trial and a 24-hour limited preview, a subscription is required. (Payments later — gate UI only for now)",
          plans: [
            { name: "Free Trial", desc: "Unlimited for 7 days after signup", price: "₩0" },
            { name: "Limited 24h", desc: "Daily view cap after trial ends", price: "₩0" },
            { name: "Paid", desc: "Unlimited lexicon, commentary, AI research", price: "TBA" },
            { name: "Institution", desc: "Seminary / denomination license", price: "Contact" },
          ],
          back: "← Back to Help",
        };

  return (
    <div className="w-full max-w-2xl mx-auto px-4 py-16 text-center">
      <h1 className="font-serif text-4xl font-bold text-ark-navy mb-4">{t.title}</h1>
      <p className="text-ark-grey mb-10 leading-relaxed">{t.intro}</p>
      <div className="grid gap-4 text-left">
        {t.plans.map((p) => (
          <div
            key={p.name}
            className="border border-[#E8E2D9] rounded-xl p-5 bg-white shadow-soft"
          >
            <div className="flex justify-between items-baseline">
              <h2 className="font-semibold text-lg text-ark-navy">{p.name}</h2>
              <span className="text-ark-brown font-bold">{p.price}</span>
            </div>
            <p className="text-sm text-ark-grey mt-1">{p.desc}</p>
          </div>
        ))}
      </div>
      <a href="/help" className="inline-block mt-8 text-sm font-semibold text-ark-brown hover:underline">
        {t.back}
      </a>
    </div>
  );
}
