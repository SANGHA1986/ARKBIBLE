"use client";

import { useEffect, useState } from "react";
import { Shield } from "lucide-react";
import { useLang } from "../LangContext";

import { API } from "../../lib/api";
const KEY_STORAGE = "ark_admin_key_v1";

type Notice = {
  id: number;
  title: string;
  body: string;
  pinned: boolean;
  published: boolean;
};

type Report = {
  id: number;
  category: string;
  title: string;
  body: string;
  contact?: string;
  search_query?: string;
  status: string;
  created_at?: string;
};

type Member = {
  id: number;
  username: string;
  full_name?: string;
  organization?: string;
  activity_region?: string;
  occupation?: string;
  join_purpose?: string;
  phone?: string;
  tier: string;
  membership_status: string;
  daily_view_limit: number;
  withdrawn?: boolean;
  has_password?: boolean;
};

type MemberForm = {
  username: string;
  password: string;
  full_name: string;
  organization: string;
  activity_region: string;
  occupation: string;
  join_purpose: string;
  phone: string;
  tier: string;
  membership_status: string;
  daily_view_limit: number;
};

const emptyMember = (): MemberForm => ({
  username: "",
  password: "",
  full_name: "",
  organization: "",
  activity_region: "",
  occupation: "",
  join_purpose: "",
  phone: "",
  tier: "Free",
  membership_status: "Free_Trial",
  daily_view_limit: 20,
});

const MEMBER_STATUSES = ["Free_Trial", "Limited_24h", "Blocked", "Paid", "Institution"];

export default function AdminPage() {
  const { lang } = useLang();
  const [keyInput, setKeyInput] = useState("");
  const [adminKey, setAdminKey] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [tab, setTab] = useState<"notices" | "reports" | "members">("members");
  const [notices, setNotices] = useState<Notice[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [nTitle, setNTitle] = useState("");
  const [nBody, setNBody] = useState("");
  const [nPinned, setNPinned] = useState(true);
  const [nPublished, setNPublished] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [mForm, setMForm] = useState<MemberForm>(emptyMember());
  const [editingMemberId, setEditingMemberId] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const k = sessionStorage.getItem(KEY_STORAGE);
    if (k) setAdminKey(k);
  }, []);

  const headers = (k: string) => ({
    "Content-Type": "application/json",
    "X-Admin-Key": k,
  });

  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    try {
      const r = await fetch(`${API}/api/admin/ping`, {
        headers: { "X-Admin-Key": keyInput.trim() },
      });
      if (!r.ok) throw new Error("invalid key");
      sessionStorage.setItem(KEY_STORAGE, keyInput.trim());
      setAdminKey(keyInput.trim());
    } catch {
      setAuthError(lang === "KO" ? "비밀번호가 올바르지 않습니다." : "Invalid password.");
    }
  };

  const logout = () => {
    sessionStorage.removeItem(KEY_STORAGE);
    setAdminKey(null);
  };

  const load = async (k: string) => {
    setMsg(null);
    try {
      const [nr, rr, ur] = await Promise.all([
        fetch(`${API}/api/notices?all=true`, { headers: headers(k) }),
        fetch(`${API}/api/admin/reports`, { headers: headers(k) }),
        fetch(`${API}/api/admin/users`, { headers: headers(k) }),
      ]);
      const nj = await nr.json();
      const rj = await rr.json();
      const uj = await ur.json();
      if (!nr.ok) throw new Error(nj.detail || "notices failed");
      if (!rr.ok) throw new Error(rj.detail || "reports failed");
      if (!ur.ok) throw new Error(uj.detail || "users failed");
      setNotices(nj.items || []);
      setReports(rj.items || []);
      setMembers(uj.items || []);
    } catch (e: any) {
      setMsg(String(e.message || e));
    }
  };

  useEffect(() => {
    if (adminKey) load(adminKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adminKey]);

  const resetNoticeForm = () => {
    setEditingId(null);
    setNTitle("");
    setNBody("");
    setNPinned(true);
    setNPublished(true);
  };

  const startEdit = (n: Notice) => {
    setEditingId(n.id);
    setNTitle(n.title);
    setNBody(n.body);
    setNPinned(!!n.pinned);
    setNPublished(!!n.published);
    setTab("notices");
  };

  const saveNotice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminKey || !nTitle.trim() || !nBody.trim()) return;
    const payload = {
      title: nTitle.trim(),
      body: nBody.trim(),
      pinned: nPinned,
      published: nPublished,
    };
    const url =
      editingId != null
        ? `${API}/api/admin/notices/${editingId}`
        : `${API}/api/admin/notices`;
    const r = await fetch(url, {
      method: editingId != null ? "PATCH" : "POST",
      headers: headers(adminKey),
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      setMsg(j.detail || "save failed");
      return;
    }
    resetNoticeForm();
    await load(adminKey);
    setMsg(lang === "KO" ? "공지 저장됨" : "Saved");
  };

  const deleteNotice = async (id: number) => {
    if (!adminKey) return;
    if (!confirm(lang === "KO" ? "이 공지를 삭제할까요?" : "Delete?")) return;
    await fetch(`${API}/api/admin/notices/${id}`, {
      method: "DELETE",
      headers: headers(adminKey),
    });
    if (editingId === id) resetNoticeForm();
    await load(adminKey);
  };

  const setReportStatus = async (id: number, status: string) => {
    if (!adminKey) return;
    await fetch(`${API}/api/admin/reports/${id}`, {
      method: "PATCH",
      headers: headers(adminKey),
      body: JSON.stringify({ status }),
    });
    await load(adminKey);
  };

  const startEditMember = (u: Member) => {
    setEditingMemberId(u.id);
    setMForm({
      username: u.username || "",
      password: "",
      full_name: u.full_name || "",
      organization: u.organization || "",
      activity_region: u.activity_region || "",
      occupation: u.occupation || "",
      join_purpose: u.join_purpose || "",
      phone: u.phone || "",
      tier: u.tier || "Free",
      membership_status: u.membership_status || "Free_Trial",
      daily_view_limit: u.daily_view_limit ?? 20,
    });
    setTab("members");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const resetMemberForm = () => {
    setEditingMemberId(null);
    setMForm(emptyMember());
  };

  const saveMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminKey) return;
    setMsg(null);
    const isEdit = editingMemberId != null;
    const payload: any = {
      username: mForm.username.trim(),
      full_name: mForm.full_name.trim(),
      organization: mForm.organization.trim(),
      activity_region: mForm.activity_region.trim(),
      occupation: mForm.occupation.trim(),
      join_purpose: mForm.join_purpose.trim(),
      phone: mForm.phone.trim(),
      tier: mForm.tier,
      membership_status: mForm.membership_status,
      daily_view_limit: mForm.daily_view_limit,
    };
    if (mForm.password.trim()) payload.password = mForm.password.trim();
    if (!isEdit && !payload.password) {
      setMsg(lang === "KO" ? "패스워드를 입력해 주세요." : "Password required.");
      return;
    }
    const url = isEdit
      ? `${API}/api/admin/users/${editingMemberId}`
      : `${API}/api/admin/users`;
    const r = await fetch(url, {
      method: isEdit ? "PATCH" : "POST",
      headers: headers(adminKey),
      body: JSON.stringify(payload),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      setMsg(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || "failed"));
      return;
    }
    resetMemberForm();
    await load(adminKey);
    setMsg(lang === "KO" ? (isEdit ? "회원 수정됨" : "회원 등록됨") : "Member saved");
  };

  const withdrawMember = async (id: number) => {
    if (!adminKey) return;
    if (!confirm(lang === "KO" ? "이 회원을 탈퇴 처리할까요?" : "Withdraw this user?")) return;
    const r = await fetch(`${API}/api/admin/users/${id}/withdraw`, {
      method: "POST",
      headers: headers(adminKey),
    });
    if (!r.ok) {
      setMsg("withdraw failed");
      return;
    }
    await load(adminKey);
    setMsg(lang === "KO" ? "탈퇴 처리됨" : "Withdrawn");
  };

  const restoreMember = async (id: number) => {
    if (!adminKey) return;
    await fetch(`${API}/api/admin/users/${id}/restore`, {
      method: "POST",
      headers: headers(adminKey),
    });
    await load(adminKey);
  };

  if (!adminKey) {
    return (
      <main className="max-w-md mx-auto px-4 py-16">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-ark-brown" />
          <h1 className="font-serif text-2xl font-bold text-ark-navy">
            {lang === "KO" ? "어드민" : "Admin"}
          </h1>
        </div>
        <form onSubmit={login} className="space-y-3 bg-white border border-[#E8E2D9] rounded-2xl p-5">
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder={lang === "KO" ? "비밀번호" : "Password"}
            className="w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
          />
          {authError && <p className="text-sm text-red-700">{authError}</p>}
          <button type="submit" className="w-full py-2 rounded-lg bg-ark-brown text-white text-sm font-semibold">
            {lang === "KO" ? "입장" : "Enter"}
          </button>
        </form>
      </main>
    );
  }

  const mField = (
    key: keyof MemberForm,
    label: string,
    opts?: { type?: string; textarea?: boolean; required?: boolean; disabled?: boolean }
  ) => (
    <label className="block text-xs font-semibold text-ark-grey">
      {label}
      {opts?.textarea ? (
        <textarea
          value={String(mForm[key] ?? "")}
          onChange={(e) => setMForm({ ...mForm, [key]: e.target.value })}
          rows={3}
          required={opts.required !== false}
          className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm font-normal text-ark-navy"
        />
      ) : (
        <input
          type={opts?.type || "text"}
          value={String(mForm[key] ?? "")}
          onChange={(e) =>
            setMForm({
              ...mForm,
              [key]:
                key === "daily_view_limit" ? Number(e.target.value || 0) : e.target.value,
            })
          }
          required={opts?.required !== false && key !== "password"}
          disabled={opts?.disabled}
          className="mt-1 w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm font-normal text-ark-navy disabled:bg-ark-bg"
        />
      )}
    </label>
  );

  return (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between gap-3 mb-6">
        <h1 className="font-serif text-2xl font-bold text-ark-navy">
          {lang === "KO" ? "어드민" : "Admin"}
        </h1>
        <button type="button" onClick={logout} className="text-xs text-ark-grey underline">
          {lang === "KO" ? "로그아웃" : "Logout"}
        </button>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {(
          [
            ["members", lang === "KO" ? "회원관리" : "Members", members.length],
            ["notices", lang === "KO" ? "공지" : "Notices", notices.length],
            ["reports", lang === "KO" ? "제보" : "Reports", reports.length],
          ] as const
        ).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`px-3 py-1.5 rounded-lg text-sm font-semibold border ${
              tab === id ? "bg-ark-brown text-white border-ark-brown" : "border-[#E8E2D9]"
            }`}
          >
            {label} ({count})
          </button>
        ))}
      </div>

      {msg && <p className="mb-3 text-sm text-ark-brown whitespace-pre-wrap">{msg}</p>}

      {tab === "members" && (
        <div className="space-y-6">
          <p className="text-xs text-ark-grey leading-relaxed">
            {lang === "KO"
              ? "필수: 아이디·패스워드·성함·소속·활동지역·직업·가입목적·휴대폰. 휴대폰에 0000·1000·2222·연속숫자(1234 등) 불가. 하나라도 비면 재작성."
              : "All profile fields required. Phone cannot include 0000, 1000, 2222, or consecutive digits."}
          </p>

          <form
            onSubmit={saveMember}
            className="bg-white border border-[#E8E2D9] rounded-xl p-4 space-y-3"
          >
            <h2 className="font-bold text-sm text-ark-navy">
              {editingMemberId != null
                ? lang === "KO"
                  ? `회원 수정 #${editingMemberId}`
                  : `Edit #${editingMemberId}`
                : lang === "KO"
                  ? "회원 등록"
                  : "Add member"}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {mField("username", lang === "KO" ? "아이디 *" : "Username *", {
                disabled: editingMemberId != null,
              })}
              {mField(
                "password",
                editingMemberId != null
                  ? lang === "KO"
                    ? "패스워드 (변경 시에만)"
                    : "Password (optional)"
                  : lang === "KO"
                    ? "패스워드 *"
                    : "Password *",
                { type: "password", required: editingMemberId == null }
              )}
              {mField("full_name", lang === "KO" ? "성함 *" : "Name *")}
              {mField("organization", lang === "KO" ? "소속 *" : "Organization *")}
              {mField("activity_region", lang === "KO" ? "활동지역 *" : "Region *")}
              {mField("occupation", lang === "KO" ? "직업 *" : "Occupation *")}
              {mField("phone", lang === "KO" ? "휴대폰번호 *" : "Phone *")}
            </div>
            {mField("join_purpose", lang === "KO" ? "가입목적 *" : "Purpose *", {
              textarea: true,
            })}
            <div className="flex flex-wrap gap-3 text-xs">
              <label className="text-ark-grey">
                상태
                <select
                  value={mForm.membership_status}
                  onChange={(e) => setMForm({ ...mForm, membership_status: e.target.value })}
                  className="ml-2 border border-[#E8E2D9] rounded px-2 py-1"
                >
                  {MEMBER_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-ark-grey">
                tier
                <select
                  value={mForm.tier}
                  onChange={(e) => setMForm({ ...mForm, tier: e.target.value })}
                  className="ml-2 border border-[#E8E2D9] rounded px-2 py-1"
                >
                  {["Free", "Paid", "Institution"].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              {mField("daily_view_limit", lang === "KO" ? "일일 한도" : "Daily limit", {
                type: "number",
                required: false,
              })}
            </div>
            <div className="flex gap-2">
              <button type="submit" className="px-4 py-2 rounded-lg bg-ark-brown text-white text-sm font-semibold">
                {editingMemberId != null
                  ? lang === "KO"
                    ? "수정 저장"
                    : "Save"
                  : lang === "KO"
                    ? "등록"
                    : "Create"}
              </button>
              {editingMemberId != null && (
                <button
                  type="button"
                  onClick={resetMemberForm}
                  className="px-4 py-2 rounded-lg border border-[#E8E2D9] text-sm"
                >
                  {lang === "KO" ? "취소" : "Cancel"}
                </button>
              )}
            </div>
          </form>

          <div className="space-y-3">
            {members.map((u) => (
              <article
                key={u.id}
                className={`bg-white border rounded-xl p-4 space-y-2 ${
                  u.withdrawn ? "border-red-200 opacity-80" : "border-[#E8E2D9]"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-bold text-ark-navy">{u.username}</span>
                    <span className="text-[11px] text-ark-grey ml-2">
                      {u.full_name || "—"} · {u.membership_status}
                      {u.withdrawn ? (lang === "KO" ? " · 탈퇴" : " · withdrawn") : ""}
                    </span>
                  </div>
                  <div className="flex gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => startEditMember(u)}
                      className="text-ark-brown underline"
                    >
                      {lang === "KO" ? "수정" : "Edit"}
                    </button>
                    {!u.withdrawn ? (
                      <button
                        type="button"
                        onClick={() => withdrawMember(u.id)}
                        className="text-red-700 underline"
                      >
                        {lang === "KO" ? "탈퇴" : "Withdraw"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => restoreMember(u.id)}
                        className="text-ark-brown underline"
                      >
                        {lang === "KO" ? "복구" : "Restore"}
                      </button>
                    )}
                  </div>
                </div>
                <p className="text-[11px] text-ark-grey leading-relaxed">
                  {[
                    u.organization && `소속 ${u.organization}`,
                    u.activity_region && `지역 ${u.activity_region}`,
                    u.occupation && `직업 ${u.occupation}`,
                    u.phone && `휴대폰 ${u.phone}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                {u.join_purpose && (
                  <p className="text-xs text-ark-navy/80 line-clamp-2">{u.join_purpose}</p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}

      {tab === "notices" && (
        <div className="space-y-6">
          <form onSubmit={saveNotice} className="bg-white border border-[#E8E2D9] rounded-xl p-4 space-y-3">
            <h2 className="font-bold text-sm text-ark-navy">
              {editingId != null
                ? lang === "KO"
                  ? `공지 수정 #${editingId}`
                  : `Edit #${editingId}`
                : lang === "KO"
                  ? "새 공지"
                  : "New notice"}
            </h2>
            <input
              value={nTitle}
              onChange={(e) => setNTitle(e.target.value)}
              className="w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
              required
              placeholder={lang === "KO" ? "제목" : "Title"}
            />
            <textarea
              value={nBody}
              onChange={(e) => setNBody(e.target.value)}
              rows={5}
              className="w-full border border-[#E8E2D9] rounded-lg px-3 py-2 text-sm"
              required
            />
            <div className="flex gap-4 text-xs">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={nPinned} onChange={(e) => setNPinned(e.target.checked)} />
                {lang === "KO" ? "고정" : "Pinned"}
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={nPublished}
                  onChange={(e) => setNPublished(e.target.checked)}
                />
                {lang === "KO" ? "공개" : "Published"}
              </label>
            </div>
            <div className="flex gap-2">
              <button type="submit" className="px-4 py-2 rounded-lg bg-ark-brown text-white text-sm font-semibold">
                {lang === "KO" ? "저장" : "Save"}
              </button>
              {editingId != null && (
                <button type="button" onClick={resetNoticeForm} className="px-4 py-2 rounded-lg border text-sm">
                  {lang === "KO" ? "취소" : "Cancel"}
                </button>
              )}
            </div>
          </form>
          {notices.map((n) => (
            <article key={n.id} className="bg-white border border-[#E8E2D9] rounded-xl p-4">
              <div className="flex justify-between gap-2">
                <h3 className="font-bold text-ark-navy">
                  {n.pinned ? "📌 " : ""}
                  {n.title}
                </h3>
                <div className="flex gap-3 text-xs shrink-0">
                  <button type="button" onClick={() => startEdit(n)} className="text-ark-brown underline">
                    {lang === "KO" ? "수정" : "Edit"}
                  </button>
                  <button type="button" onClick={() => deleteNotice(n.id)} className="text-red-700 underline">
                    {lang === "KO" ? "삭제" : "Delete"}
                  </button>
                </div>
              </div>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-sm">{n.body}</pre>
            </article>
          ))}
        </div>
      )}

      {tab === "reports" && (
        <div className="space-y-3">
          {reports.map((r) => (
            <article key={r.id} className="bg-white border border-[#E8E2D9] rounded-xl p-4">
              <div className="text-xs text-ark-grey mb-1">
                #{r.id} · {r.category} · {r.status}
              </div>
              <h3 className="font-bold text-ark-navy">{r.title}</h3>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-sm">{r.body}</pre>
              <div className="mt-3 flex gap-2">
                {["open", "in_progress", "done"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setReportStatus(r.id, s)}
                    className={`px-2 py-1 rounded text-[11px] border ${
                      r.status === s ? "bg-ark-brown text-white border-ark-brown" : "border-[#E8E2D9]"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
