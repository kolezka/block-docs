import { Item } from "./types";
import { search } from "./service";

export function handleSearch(index: Item[], params: { q?: string }): { status: number; results: Item[] } {
  const results = search(index, params.q ?? "");
  return { status: 200, results };
}
