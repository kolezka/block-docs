import { Db } from "../db/client";

export async function applyPriceAdjustment(db: Db, sku: string, currency: string, amountCents: number) {
  await db.query(
    "UPDATE prices SET amount_cents = $3 WHERE sku = $1 AND currency = $2",
    [sku, currency, amountCents],
  );
}
