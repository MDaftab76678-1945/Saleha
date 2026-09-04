/**
 * Client for the Saleha Python backend.
 *
 * Every /api/* route except /api/health requires an X-Saleha-Token header. The
 * backend prints that token when it starts (and regenerates it each launch
 * unless SALEHA_STUDIO_TOKEN is set), so the token is supplied by the operator
 * and kept in localStorage rather than baked into the bundle.
 */

const TOKEN_STORAGE_KEY = "saleha.studio.token";

export const DEFAULT_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export function getStoredToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function storeToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token.trim());
  } catch {
    // A blocked localStorage only costs the operator a re-entry next reload.
  }
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly isAuthError: boolean
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(
  path: string,
  options: { baseUrl?: string; token?: string; signal?: AbortSignal } = {}
): Promise<T> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const token = options.token ?? getStoredToken();

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      headers: token ? { "X-Saleha-Token": token } : undefined,
      signal: options.signal,
    });
  } catch (cause) {
    // A refused connection and a CORS rejection look identical here, so the
    // message covers both rather than guessing.
    throw new ApiError(
      `Could not reach the backend at ${baseUrl}. Is it running?`,
      0,
      false
    );
  }

  if (response.status === 401) {
    throw new ApiError(
      "The backend rejected this token. It changes every time the server restarts unless SALEHA_STUDIO_TOKEN is set.",
      401,
      true
    );
  }
  if (!response.ok) {
    throw new ApiError(`Backend returned ${response.status}.`, response.status, false);
  }
  return (await response.json()) as T;
}

/** Hits the one route that needs no token, to tell "server down" apart from "bad token". */
export async function checkHealth(
  baseUrl: string = DEFAULT_BASE_URL
): Promise<{ status: string; version: string } | null> {
  try {
    const response = await fetch(`${baseUrl}/api/health`);
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}
