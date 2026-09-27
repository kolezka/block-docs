import { Next, Request, Response } from "./types";

export const SESSION_COOKIE = "sid";

// Validates the session before any protected handler runs.
export function requireSession(req: Request, res: Response, next: Next): void {
  const token = req.cookies[SESSION_COOKIE];
  if (!token) {
    res.status(401).end();
    return;
  }
  req.sessionToken = token;
  next();
}
