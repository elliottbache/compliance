import { expect, test } from "@playwright/test";

import { mockApi } from "./helpers/apiMocks";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Attachments", exact: true }).click();
});

test("shows pending attachments in the upload dropdown", async ({ page }) => {
  await page.getByRole("button", { name: "Upload File" }).click();

  const uploadSelect = page.getByLabel("Attachment");

  await expect(uploadSelect).toContainText("51 - pending_photo");
  await expect(uploadSelect).not.toContainText("50 - inspection_report");
});

test("shows uploaded attachments in the download dropdown", async ({ page }) => {
  await page.getByRole("button", { name: "Download File" }).click();

  const downloadSelect = page.getByLabel("Attachment");

  await expect(downloadSelect).toContainText("50 - inspection_report");
  await expect(downloadSelect).not.toContainText("51 - pending_photo");
});

test("downloads the selected uploaded attachment", async ({ page }) => {
  await page.getByRole("button", { name: "Download File" }).click();
  await page.getByLabel("Attachment").selectOption("50");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download", exact: true }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe("inspection_report.pdf");
});
