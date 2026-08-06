"use client";

export type ScrapItem = {
  id: string;
  kind: "event" | "character" | "verse" | "strong" | "concept" | "note";
  title: string;
  subtitle?: string;
  body?: string;
  href?: string;
  query?: string;
  savedAt: string;
};

const KEY = "ark_library_scraps_v1";

export function loadScraps(): ScrapItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveScraps(items: ScrapItem[]) {
  localStorage.setItem(KEY, JSON.stringify(items));
}

export function scrapId(kind: string, title: string) {
  return `${kind}:${title}`;
}

export function isScrapped(kind: string, title: string): boolean {
  return loadScraps().some((s) => s.id === scrapId(kind, title));
}

export function toggleScrap(item: Omit<ScrapItem, "id" | "savedAt">): ScrapItem[] {
  const id = scrapId(item.kind, item.title);
  const cur = loadScraps();
  const exists = cur.find((s) => s.id === id);
  let next: ScrapItem[];
  if (exists) {
    next = cur.filter((s) => s.id !== id);
  } else {
    next = [
      {
        ...item,
        id,
        savedAt: new Date().toISOString(),
      },
      ...cur,
    ];
  }
  saveScraps(next);
  return next;
}
