import { Db } from "../db/client";
import { getPrice } from "./prices";

export async function handleGetPrice(db: Db, sku: string, currency: string) {
  const price = await getPrice(db, sku, currency);
  if (price === null) {
    return { status: 404, body: { error: "price_not_found" } };
  }
  return { status: 200, body: price };
}
