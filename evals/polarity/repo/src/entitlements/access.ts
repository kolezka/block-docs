import { Account, UNPAID_TIERS } from "./tiers";

export function hasPremiumAccess(account: Account): boolean {
  if (account.suspended) {
    return false;
  }
  return !UNPAID_TIERS.has(account.tier);
}
