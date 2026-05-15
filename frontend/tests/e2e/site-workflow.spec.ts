import { expect, test } from "@playwright/test";

import { mockApi } from "./helpers/apiMocks";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
});

test("loads site history and attachments", async ({ page }) => {
  await page.getByLabel("Site ID").fill("12");
  await page.getByRole("button", { name: "Load History" }).click();

  await expect(page.getByText("Site 12 · 1 inspection")).toBeVisible();
  await expect(page.getByText("USDA Organic").first()).toBeVisible();
  await expect(page.getByText("Missing pesticide logs").first()).toBeVisible();

  await page.getByRole("button", { name: "Load Attachments" }).click();

  await expect(page.getByText("Site 12 · 1 file")).toBeVisible();
  await expect(page.getByRole("heading", { name: "inspection_report" })).toBeVisible();
  await expect(page.getByText("Inspection report evidence")).toBeVisible();
});

test("runs analysis and generates Markdown", async ({ page }) => {
  await page.getByLabel("Site ID").fill("12");
  await page.getByRole("button", { name: "Run AI Analysis" }).click();

  await expect(page.getByText("Human review required").first()).toBeVisible();
  await expect(page.getByText("Records should be reviewed")).toBeVisible();

  await page.getByRole("button", { name: "Generate Markdown" }).click();

  await expect(page.getByRole("textbox")).toContainText("# Site Analysis");
  await expect(page.getByRole("textbox")).toContainText("Missing pesticide logs");
});

test("shows validation errors for invalid site IDs", async ({ page }) => {
  await page.getByLabel("Site ID").fill("0");
  await page.getByRole("button", { name: "Load History" }).click();

  await expect(page.getByText("Enter a valid positive numeric site ID.")).toBeVisible();
});
