import { Item } from "./types";

export function excludeHidden(items: Item[]): Item[] {
  return items.filter((item) => !item.hidden);
}

export function buildVisibleResults(items: Item[], limit: number): Item[] {
  return excludeHidden(items).slice(0, limit);
}
