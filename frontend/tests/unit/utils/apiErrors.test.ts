import { describe, expect, it } from "vitest";

import { ApiError } from "../../../src/api/complianceApi";
import { getErrorMessage } from "../../../src/utils/apiErrors";

describe("getErrorMessage", () => {
  it("formats 404 API errors", () => {
    const error = new ApiError(404, "Attachment 45 not found.", "Not Found");

    expect(getErrorMessage(error)).toBe(
      "404 — Resource not found or not visible. Attachment 45 not found.",
    );
  });

  it("formats validation API errors", () => {
    const error = new ApiError(422, "Invalid attachment ID.", "Unprocessable Entity");

    expect(getErrorMessage(error)).toBe(
      "422 — Invalid request or request could not be processed. Invalid attachment ID.",
    );
  });

  it("formats failed fetch as a backend network error", () => {
    expect(getErrorMessage(new TypeError("Failed to fetch"))).toContain(
      "Network error: could not reach the FastAPI backend.",
    );
  });

  it("uses ordinary error messages for non-API errors", () => {
    expect(getErrorMessage(new Error("Something went wrong."))).toBe(
      "Something went wrong.",
    );
  });

  it("falls back for unknown thrown values", () => {
    expect(getErrorMessage("bad value")).toBe("Unexpected error.");
  });
});
