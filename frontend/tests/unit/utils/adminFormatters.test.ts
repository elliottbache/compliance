import { describe, expect, it } from "vitest";

import {
  formatArchivedAt,
  formatArchiveReason,
  formatDateTime,
} from "../../../src/utils/adminFormatters";

describe("formatDateTime", () => {
  it("formats ISO timestamps for admin tables", () => {
    expect(formatDateTime("2026-05-14T21:34:19.701Z")).toMatch(
      /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/,
    );
  });

  it("returns a dash for missing values", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
    expect(formatDateTime("")).toBe("—");
  });

  it("returns invalid date text unchanged", () => {
    expect(formatDateTime("not-a-date")).toBe("not-a-date");
  });
});

describe("formatArchivedAt", () => {
  it("returns Active for non-archived records", () => {
    expect(formatArchivedAt(null)).toBe("Active");
  });

  it("formats archived timestamps", () => {
    expect(formatArchivedAt("2026-05-14T21:34:19.701Z")).toMatch(
      /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/,
    );
  });
});

describe("formatArchiveReason", () => {
  it("returns a dash when there is no archive reason", () => {
    expect(formatArchiveReason(null)).toBe("—");
    expect(formatArchiveReason("   ")).toBe("—");
  });

  it("trims archive reasons", () => {
    expect(formatArchiveReason(" duplicate record ")).toBe("duplicate record");
  });
});
