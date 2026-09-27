import { requireSession } from "../middleware/session";
import { Next, Request, Response } from "../middleware/types";

type Handler = (req: Request, res: Response, next: Next) => void;

export const accountRoutes: Array<{ path: string; handlers: Handler[] }> = [
  { path: "/account", handlers: [requireSession] },
  { path: "/account/settings", handlers: [requireSession] },
];
