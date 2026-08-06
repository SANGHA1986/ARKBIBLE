/** 회원 로그인 세션 (localStorage) */
const USER_KEY = "ark_user_session_v1";

export type ArkSession = {
  username: string;
  token: string;
  full_name?: string | null;
};

export function getSession(): ArkSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    const j = JSON.parse(raw);
    if (!j?.username || !j?.token) return null;
    return j;
  } catch {
    return null;
  }
}

export function setSession(s: ArkSession) {
  localStorage.setItem(USER_KEY, JSON.stringify(s));
  window.dispatchEvent(new Event("ark-auth-changed"));
}

export function clearSession() {
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("ark-auth-changed"));
}

export function authHeaders(): Record<string, string> {
  const s = getSession();
  if (!s) return {};
  return {
    "X-Username": s.username,
    "X-User-Token": s.token,
  };
}
