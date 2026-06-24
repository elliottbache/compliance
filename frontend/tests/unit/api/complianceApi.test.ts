import { afterEach, describe, expect, it, vi } from "vitest";

import {
  downloadAttachmentFile,
  fetchJson,
  setAuthCredentialsProvider,
} from "../../../src/api/complianceApi";

const API_BASE_URL = "http://localhost:8000";
const AUTH_TOKEN_STORAGE_KEY = "compliance.authToken";

function jsonResponse(body: unknown, status = 200, statusText = "OK"): Response {
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json" },
    status,
    statusText,
  });
}

function createLocalStorage(): Storage {
  const values = new Map<string, string>();

  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

function getRequestHeaders(fetchMock: ReturnType<typeof vi.fn>, callIndex: number) {
  return new Headers(fetchMock.mock.calls[callIndex][1]?.headers);
}

function fileResponse(body: string, filename: string): Response {
  return new Response(body, {
    headers: {
      "content-disposition": `attachment; filename="${filename}"`,
      "content-type": "application/octet-stream",
    },
  });
}

describe("fetchJson", () => {
  afterEach(() => {
    setAuthCredentialsProvider(null);
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("requests a token and retries with a bearer header after a 401", async () => {
    const localStorage = createLocalStorage();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Unauthorized" }, 401, "Unauthorized"))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "test-token", token_type: "bearer" }),
      )
      .mockResolvedValueOnce(jsonResponse({ clients: [] }));

    vi.stubGlobal("window", { localStorage });
    vi.stubGlobal("fetch", fetchMock);

    setAuthCredentialsProvider(async () => ({
      email: "alice@example.com",
      password: "secret-password",
    }));

    const result = await fetchJson<{ clients: unknown[] }>("/clients");

    expect(result).toEqual({ clients: [] });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE_URL}/clients`);
    expect(getRequestHeaders(fetchMock, 0).has("Authorization")).toBe(false);
    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE_URL}/auth/token`);
    expect(String(fetchMock.mock.calls[1][1]?.body)).toBe(
      "username=alice%40example.com&password=secret-password",
    );
    expect(getRequestHeaders(fetchMock, 2).get("Authorization")).toBe(
      "Bearer test-token",
    );
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe("test-token");
  });

  it("sends a stored bearer token on the first request", async () => {
    const localStorage = createLocalStorage();
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "stored-token");

    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ clients: [] }));

    vi.stubGlobal("window", { localStorage });
    vi.stubGlobal("fetch", fetchMock);

    await fetchJson<{ clients: unknown[] }>("/clients");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(getRequestHeaders(fetchMock, 0).get("Authorization")).toBe(
      "Bearer stored-token",
    );
  });

  it("raises the original 401 when credentials are not provided", async () => {
    const localStorage = createLocalStorage();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Unauthorized" }, 401, "Unauthorized"));

    vi.stubGlobal("window", { localStorage });
    vi.stubGlobal("fetch", fetchMock);
    setAuthCredentialsProvider(async () => null);

    await expect(fetchJson("/clients")).rejects.toMatchObject({
      detail: "Unauthorized",
      status: 401,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("downloadAttachmentFile", () => {
  afterEach(() => {
    setAuthCredentialsProvider(null);
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("downloads an attachment with the stored bearer token", async () => {
    const localStorage = createLocalStorage();
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "stored-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(fileResponse("example file", "inspection_report.pdf"));
    const objectUrl = "blob:http://localhost/test";
    const anchor = {
      click: vi.fn(),
      download: "",
      href: "",
      remove: vi.fn(),
    };
    const append = vi.fn();
    const createElement = vi.fn().mockReturnValue(anchor);
    const createObjectURL = vi.fn().mockReturnValue(objectUrl);
    const revokeObjectURL = vi.fn();

    vi.stubGlobal("window", { localStorage });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", {
      body: { append },
      createElement,
    });
    vi.stubGlobal("URL", {
      createObjectURL,
      revokeObjectURL,
    });

    await downloadAttachmentFile(50);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${API_BASE_URL}/attachments/50/download`,
    );
    expect(getRequestHeaders(fetchMock, 0).get("Authorization")).toBe(
      "Bearer stored-token",
    );
    expect(anchor.href).toBe(objectUrl);
    expect(anchor.download).toBe("inspection_report.pdf");
    expect(append).toHaveBeenCalledWith(anchor);
    expect(anchor.click).toHaveBeenCalledOnce();
    expect(anchor.remove).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith(objectUrl);
  });
});
