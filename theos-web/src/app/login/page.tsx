"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLang } from "../LangContext";
import { setSession } from "../../lib/authStore";

import { API } from "../../lib/api";

export default function LoginPage() {
  const { lang } = useLang();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [organization, setOrganization] = useState("");
  const [activityRegion, setActivityRegion] = useState("");
  const [occupation, setOccupation] = useState("");
  const [joinPurpose, setJoinPurpose] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body =
        mode === "login"
          ? { username: username.trim(), password }
          : {
              username: username.trim(),
              password,
              full_name: fullName.trim(),
              organization: organization.trim(),
              activity_region: activityRegion.trim(),
              occupation: occupation.trim(),
              join_purpose: joinPurpose.trim(),
              phone: phone.trim(),
            };
      const r = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || (mode === "login" ? "login failed" : "register failed"));
      setSession({
        username: j.user.username,
        token: j.token,
        full_name: j.user.full_name,
      });
      router.push("/account");
    } catch (err: any) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  };

  const field = (
    label: string,
    value: string,
    set: (v: string) => void,
    opts?: { type?: string; autoComplete?: string; required?: boolean }
  ) => (
    <label className="block text-xs font-semibold text-ark-grey">
      {label}
      <input
        type={opts?.type || "text"}
        value={value}
        onChange={(e) => set(e.target.value)}
        className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
        required={opts?.required !== false}
        autoComplete={opts?.autoComplete}
      />
    </label>
  );

  return (
    <main className="max-w-md mx-auto px-4 py-16">
      <h1 className="font-serif text-2xl font-bold text-ark-navy mb-2">
        {mode === "login"
          ? lang === "KO"
            ? "로그인"
            : "Login"
          : lang === "KO"
            ? "베타 회원가입"
            : "Beta sign up"}
      </h1>
      <p className="text-xs text-ark-grey mb-6 leading-relaxed">
        {lang === "KO"
          ? "테스트용 자가 가입이 열려 있습니다. 가입 후 「내정보」에서 수정할 수 있습니다."
          : "Self-signup is open for beta testing. Edit details later in My Profile."}
      </p>

      <div className="flex gap-2 mb-4">
        <button
          type="button"
          onClick={() => {
            setMode("login");
            setError(null);
          }}
          className={`flex-1 py-2 rounded-lg text-sm font-semibold border ${
            mode === "login"
              ? "bg-ark-brown text-white border-ark-brown"
              : "border-[#E8E2D9] text-ark-grey"
          }`}
        >
          {lang === "KO" ? "로그인" : "Login"}
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("register");
            setError(null);
          }}
          className={`flex-1 py-2 rounded-lg text-sm font-semibold border ${
            mode === "register"
              ? "bg-ark-brown text-white border-ark-brown"
              : "border-[#E8E2D9] text-ark-grey"
          }`}
        >
          {lang === "KO" ? "회원가입" : "Sign up"}
        </button>
      </div>

      <form onSubmit={submit} className="bg-white border border-[#E8E2D9] rounded-2xl p-5 space-y-3 shadow-soft">
        {field(lang === "KO" ? "아이디" : "Username", username, setUsername, {
          autoComplete: "username",
        })}
        {field(lang === "KO" ? "패스워드" : "Password", password, setPassword, {
          type: "password",
          autoComplete: mode === "login" ? "current-password" : "new-password",
        })}
        {mode === "register" && (
          <>
            {field(lang === "KO" ? "성함" : "Full name", fullName, setFullName)}
            {field(lang === "KO" ? "소속" : "Organization", organization, setOrganization)}
            {field(lang === "KO" ? "활동지역" : "Region", activityRegion, setActivityRegion)}
            {field(lang === "KO" ? "직업" : "Occupation", occupation, setOccupation)}
            {field(lang === "KO" ? "가입목적" : "Purpose", joinPurpose, setJoinPurpose)}
            {field(lang === "KO" ? "휴대폰번호" : "Phone", phone, setPhone, {
              autoComplete: "tel",
            })}
          </>
        )}
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-ark-brown text-white text-sm font-semibold disabled:opacity-50"
        >
          {loading
            ? "…"
            : mode === "login"
              ? lang === "KO"
                ? "로그인"
                : "Sign in"
              : lang === "KO"
                ? "가입하기"
                : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-xs text-ark-grey">
        <a href="/account" className="text-ark-brown underline">
          {lang === "KO" ? "내정보" : "My profile"}
        </a>
      </p>
    </main>
  );
}
