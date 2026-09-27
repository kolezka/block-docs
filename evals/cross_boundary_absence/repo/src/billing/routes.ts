import { Db } from "../db/client";
import { applyPriceAdjustment } from "./adjust";

export async function handleAdjustPrice(db: Db, body: { sku: string; currency: string; amountCents: number }) {
  await applyPriceAdjustment(db, body.sku, body.currency, body.amountCents);
  return { status: 204 };
}
