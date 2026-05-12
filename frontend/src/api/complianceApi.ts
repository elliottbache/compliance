const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string, statusText: string) {
    super(`${status}: ${detail || statusText}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

function stringifyDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (detail === null || detail === undefined) {
    return "";
  }

  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const body: { detail?: unknown } = await response.json();
      return stringifyDetail(body.detail);
    } catch {
      return "";
    }
  }

  try {
    return await response.text();
  } catch {
    return "";
  }
}

export async function assertOk(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }

  const detail = await readErrorDetail(response);
  throw new ApiError(response.status, detail, response.statusText);
}

export async function fetchJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(buildUrl(path), {
    headers: {
      Accept: "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  await assertOk(response);
  return response.json() as Promise<T>;
}

export async function fetchText(
  path: string,
  options: RequestInit = {},
): Promise<string> {
  const response = await fetch(buildUrl(path), {
    headers: {
      Accept: "text/plain, text/markdown, */*",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  await assertOk(response);
  return response.text();
}

export async function postJson<T>(
  path: string,
  body?: unknown,
  options: RequestInit = {},
): Promise<T> {
  return fetchJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    ...options,
  });
}

export async function postText(
  path: string,
  body?: unknown,
  options: RequestInit = {},
): Promise<string> {
  return fetchText(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    ...options,
  });
}