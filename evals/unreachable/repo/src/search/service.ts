import { Item } from "./types";

export const DEFAULT_LIMIT = 20;

export function rankResults(items: Item[]): Item[] {
  return [...items].sort((a, b) => b.score - a.score);
}

export function search(index: Item[], query: string, limit: number = DEFAULT_LIMIT): Item[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) {
    return [];
  }
  const matches = index.filter((item) => item.title.toLowerCase().includes(needle));
  return rankResults(matches).slice(0, limit);
}
