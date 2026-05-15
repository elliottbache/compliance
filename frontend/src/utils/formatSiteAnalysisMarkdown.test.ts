import { describe, expect, it, vi } from "vitest";

import { buildSiteAnalysisMarkdown } from "./formatSiteAnalysisMarkdown";

describe("buildSiteAnalysisMarkdown", () => {
  it("renders metadata, summary, sections, and evidence", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-15T10:30:00.000Z"));

    const markdown = buildSiteAnalysisMarkdown({
      site_id: 12,
      executive_summary: "Recurring records issue.",
      recurring_issues: [
        {
          item: "Missing pesticide logs",
          confidence_note: "High confidence.",
          evidence: [
            {
              cert_id: 42,
              reg_title: "USDA Organic",
              inspection_date: "2026-04-01",
              finding_id: 7,
              rule_index: "7 CFR 205.201",
              support_text: "Logs were unavailable during inspection.",
            },
          ],
        },
      ],
    });

    expect(markdown).toContain("# Site Analysis");
    expect(markdown).toContain("**Site ID:** 12");
    expect(markdown).toContain("**Generated at:** 2026-05-15T10:30:00.000Z");
    expect(markdown).toContain("Recurring records issue.");
    expect(markdown).toContain("### Missing pesticide logs");
    expect(markdown).toContain("#### Confidence note");
    expect(markdown).toContain("- Certification ID: 42");
    expect(markdown).toContain("- Rule index: 7 CFR 205.201");

    vi.useRealTimers();
  });

  it("uses fallback text when optional content is missing", () => {
    const markdown = buildSiteAnalysisMarkdown({});

    expect(markdown).toContain("**Site ID:** Unknown");
    expect(markdown).toContain("## Executive summary\n\nNone.");
    expect(markdown).toContain("## Recurring issues\n\nNone.");
    expect(markdown).toContain("## Missing information\n\nNone.");
    expect(markdown).toContain("## Needs human review\n\nNone.");
    expect(markdown).toContain("## Suggestions\n\nNone.");
  });
});
