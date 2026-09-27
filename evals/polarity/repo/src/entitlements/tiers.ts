export type Tier = "free" | "trial" | "basic" | "pro" | "grace";

export interface Account {
  id: string;
  tier: Tier;
  suspended: boolean;
}

// Trial and grace accounts are not paid tiers.
export const UNPAID_TIERS: ReadonlySet<Tier> = new Set<Tier>(["free"]);
