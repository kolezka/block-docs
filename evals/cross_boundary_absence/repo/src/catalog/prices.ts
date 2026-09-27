import { Db } from "../db/client";

export interface Price {
  sku: string;
  currency: string;
  amountCents: number;
}

export async function getPrice(db: Db, sku: string, currency: string): Promise<Price | null> {
  const rows = await db.query<Price>(
    "SELECT sku, currency, amount_cents AS amountCents FROM prices WHERE sku = $1 AND currency = $2",
    [sku, currency],
  );
  return rows.length > 0 ? rows[0] : null;
}

export async function listPrices(db: Db, sku: string): Promise<Price[]> {
  return db.query<Price>(
    "SELECT sku, currency, amount_cents AS amountCents FROM prices WHERE sku = $1 ORDER BY currency",
    [sku],
  );
}
