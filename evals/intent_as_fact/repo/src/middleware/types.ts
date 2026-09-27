export interface Request {
  path: string;
  cookies: Record<string, string | undefined>;
  sessionToken?: string;
}

export interface Response {
  status(code: number): Response;
  end(): void;
}

export type Next = () => void;
