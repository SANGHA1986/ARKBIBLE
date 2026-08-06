"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLang } from "../LangContext";
import { authHeaders, clearSession, getSession, setSession } from "../../lib/authStore";

import { API } from "../../lib/api";

type Profile = {
  username: string;
  full_name?: string;
  organization?: string;
  activity_region?: string;
  occupation?: string;
  join_purpose?: string;
  phone?: string;
};

const empty: Profile = {
  username: "",
  full_name: "",
  organization: "",
  activity_region: "",
  occupation: "",
  join_purpose: "",
  phone: "",
};

export default function AccountPage() {
  const { lang } = useLang();
  const router = useRouter();
  const [form, setForm] = useState<Profile>(empty);
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const s = getSession();
    if (!s) {
      setLoading(false);
      return;
    }
    try {
      const r = await fetch(`${API}/api/me`, { headers: authHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "failed");
      setForm({
        username: j.username,
        full_name: j.full_name || "",
        organization: j.organization || "",
        activity_region: j.activity_region || "",
        occupation: j.occupation || "",
        join_purpose: j.join_purpose || "",
        phone: j.phone || "",
      });
    } catch (e: any) {
      clearSession();
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMsg(null);
    const body: any = {
      full_name: form.full_name,
      organization: form.organization,
      activity_region: form.activity_region,
      occupation: form.occupation,
      join_purpose: form.join_purpose,
      phone: form.phone,
    };
    if (password.trim()) body.password = password.trim();
    try {
      const r = await fetch(`${API}/api/me`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail));
      if (j.token) {
        setSession({
          username: j.user.username,
          token: j.token,
          full_name: j.user.full_name,
        });
      }
      setPassword("");
      setForm({
        username: j.user.username,
        full_name: j.user.full_name || "",
        organization: j.user.organization || "",
        activity_region: j.user.activity_region || "",
        occupation: j.user.occupation || "",
        join_purpose: j.user.join_purpose || "",
        phone: j.user.phone || "",
      });
      setMsg(lang === "KO" ? "저장되었습니다." : "Saved.");
    } catch (err: any) {
      setError(String(err.message || err));
    }
  };

  const withdraw = async () => {
    if (!confirm(lang === "KO" ? "정말 탈퇴하시겠습니까?" : "Withdraw your account?")) return;
    const r = await fetch(`${API}/api/me/withdraw`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (r.ok) {
      clearSession();
      router.push("/");
    }
  };

  if (loading) {
    return (
      <main className="max-w-lg mx-auto px-4 py-16 text-sm text-ark-grey">
        {lang === "KO" ? "불러오는 중…" : "Loading…"}
      </main>
    );
  }

  if (!getSession()) {
    return (
      <main className="max-w-lg mx-auto px-4 py-16">
        <p className="text-sm text-ark-grey mb-4">
          {lang === "KO" ? "로그인이 필요합니다." : "Please log in."}
        </p>
        <a
          href="/login"
          className="inline-block px-4 py-2 rounded-lg bg-ark-brown text-white text-sm font-semibold"
        >
          {lang === "KO" ? "로그인" : "Login"}
        </a>
      </main>
    );
  }

  const field = (
    key: keyof Profile,
    label: string,
    opts?: { textarea?: boolean }
  ) => (
    <label className="block text-xs font-semibold text-ark-grey">
      {label} *
      {opts?.textarea ? (
        <textarea
          value={(form[key] as string) || ""}
          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
          rows={3}
          className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm font-normal text-ark-navy"
          required
        />
      ) : (
        <input
          value={(form[key] as string) || ""}
          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
          className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm font-normal text-ark-navy"
          required={key !== "username"}
          disabled={key === "username"}
        />
      )}
    </label>
  );

  return (
    <main className="max-w-lg mx-auto px-4 py-10">
      <h1 className="font-serif text-2xl font-bold text-ark-navy mb-2">
        {lang === "KO" ? "내정보 수정" : "My profile"}
      </h1>
      <p className="text-xs text-ark-grey mb-6 leading-relaxed">
        {lang === "KO"
          ? "가입 항목은 모두 필수입니다. 휴대폰은 0000·1000·2222·연속숫자(1234 등)를 쓸 수 없습니다."
          : "All profile fields are required. Phone cannot include 0000, 1000, 2222, or consecutive digits."}
      </p>

      <form onSubmit={save} className="bg-white border border-[#E8E2D9] rounded-2xl p-5 space-y-3 shadow-soft">
        {field("username", lang === "KO" ? "아이디" : "Username")}
        <label className="block text-xs font-semibold text-ark-grey">
          {lang === "KO" ? "패스워드 (변경 시에만)" : "Password (only to change)"}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
            autoComplete="new-password"
          />
        </label>
        {field("full_name", lang === "KO" ? "성함" : "Name")}
        {field("organization", lang === "KO" ? "소속" : "Organization")}
        {field("activity_region", lang === "KO" ? "활동지역" : "Region")}
        {field("occupation", lang === "KO" ? "직업" : "Occupation")}
        {field("join_purpose", lang === "KO" ? "가입목적" : "Purpose", { textarea: true })}
        {field("phone", lang === "KO" ? "휴대폰번호" : "Phone")}

        {error && <p className="text-sm text-red-700">{error}</p>}
        {msg && <p className="text-sm text-ark-brown">{msg}</p>}

        <button
          type="submit"
          className="w-full py-2.5 rounded-lg bg-ark-brown text-white text-sm font-semibold"
        >
          {lang === "KO" ? "저장" : "Save"}
        </button>
      </form>

      <div className="mt-6 flex flex-wrap gap-3 text-xs">
        <button type="button" onClick={() => { clearSession(); router.push("/"); }} className="underline text-ark-grey">
          {lang === "KO" ? "로그아웃" : "Logout"}
        </button>
        <button type="button" onClick={withdraw} className="underline text-red-700">
          {lang === "KO" ? "회원 탈퇴" : "Withdraw"}
        </button>
      </div>
    </main>
  );
}
