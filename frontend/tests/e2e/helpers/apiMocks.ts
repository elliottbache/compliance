import type { Page, Route } from "@playwright/test";

const API_BASE = "http://localhost:8000";

export async function mockApi(page: Page): Promise<void> {
  await page.route(`${API_BASE}/**`, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === "/sites/12/history") {
      await route.fulfill({
        contentType: "application/json",
        json: {
          site_id: 12,
          inspection_count: 1,
          latest_inspection_date: "2026-04-01",
          certifications: [
            {
              cert_id: 42,
              result: "Fail",
              resolution_date: null,
              reg_title: "USDA Organic",
              reg_description: "Organic compliance requirements.",
              certifier_org_name: "Certifier Co",
              inspection_date: "2026-04-01",
              findings: [
                {
                  finding_id: 7,
                  finding: "Missing pesticide logs",
                  rule_index: "7 CFR 205.201",
                  rule_title: "Organic plan",
                  rule_description: "Producer must maintain records.",
                },
              ],
            },
          ],
        },
      });
      return;
    }

    if (path === "/sites/12/attachments") {
      await route.fulfill({
        contentType: "application/json",
        json: {
          site_id: 12,
          attachments: [
            {
              id: 50,
              file_name: "inspection_report",
              file_path: "backend/storage/attachments/report.pdf",
              description: "Inspection report evidence",
              uploaded_at: "2026-04-03T09:30:00Z",
              archived_at: null,
              archive_reason: null,
              certification_id: 42,
              inspection_date: "2026-04-01",
              regulation_id: 3,
              regulation_title: "USDA Organic",
              finding_links: [
                {
                  finding_id: 7,
                  finding: "Missing pesticide logs",
                  rule_index: "7 CFR 205.201",
                  rule_title: "Organic plan",
                  rule_description: "Producer must maintain records.",
                },
              ],
            },
          ],
        },
      });
      return;
    }

    if (path === "/sites/12/analysis" && route.request().method() === "POST") {
      await route.fulfill({
        contentType: "application/json",
        json: {
          site_id: 12,
          executive_summary: "Records should be reviewed before certification.",
          recurring_issues: [
            {
              item: "Missing pesticide logs",
              confidence_note: "Supported by inspection finding.",
              evidence: [
                {
                  cert_id: 42,
                  reg_title: "USDA Organic",
                  inspection_date: "2026-04-01",
                  finding_id: 7,
                  rule_index: "7 CFR 205.201",
                  support_text: "Missing pesticide logs",
                },
              ],
            },
          ],
          missing_information: [],
          needs_human_review: [],
          suggestions: [],
        },
      });
      return;
    }

    if (path === "/attachments") {
      await route.fulfill({
        contentType: "application/json",
        json: [
          {
            id: 50,
            certification_id: 42,
            file_name: "inspection_report",
            file_path: "backend/storage/attachments/report.pdf",
            description: "Inspection report evidence",
            uploaded_at: "2026-04-03T09:30:00Z",
            archived_at: null,
            archive_reason: null,
            finding_ids: [],
            inspection_date: "2026-04-01",
            regulation_id: 3,
            regulation_title: "USDA Organic",
          },
          {
            id: 51,
            certification_id: 42,
            file_name: "pending_photo",
            file_path: "backend/storage/attachments/pending_photo",
            description: "Pending upload",
            uploaded_at: null,
            archived_at: null,
            archive_reason: null,
            finding_ids: [],
            inspection_date: "2026-04-01",
            regulation_id: 3,
            regulation_title: "USDA Organic",
          },
        ],
      });
      return;
    }

    if (path === "/attachments/50/download") {
      await route.fulfill({
        body: "example file",
        contentType: "text/plain",
        headers: {
          "Content-Disposition": 'attachment; filename="inspection_report.pdf"',
        },
      });
      return;
    }

    await fulfillEmptyList(route);
  });
}

async function fulfillEmptyList(route: Route): Promise<void> {
  await route.fulfill({
    contentType: "application/json",
    json: [],
  });
}
