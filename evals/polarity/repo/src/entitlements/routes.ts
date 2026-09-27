import { Account } from "./tiers";
import { hasPremiumAccess } from "./access";

export interface Response {
  status: number;
  body: string;
}

export function exportReport(account: Account, report: string): Response {
  if (!hasPremiumAccess(account)) {
    return { status: 403, body: "premium_required" };
  }
  return { status: 200, body: report };
}
