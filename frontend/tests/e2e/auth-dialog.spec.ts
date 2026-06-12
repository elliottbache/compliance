import { expect, test } from "@playwright/test";

const API_BASE = "http://localhost:8000";

test("prompts for credentials and retries protected client requests", async ({
  page,
}) => {
  let authenticatedClientRequestCount = 0;
  let unauthenticatedClientRequestCount = 0;

  await page.route(`${API_BASE}/**`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [],
    });
  });

  await page.route(`${API_BASE}/clients`, async (route) => {
    if (route.request().headers().authorization === "Bearer e2e-token") {
      authenticatedClientRequestCount += 1;
      await route.fulfill({
        contentType: "application/json",
        json: [],
      });
      return;
    }

    unauthenticatedClientRequestCount += 1;
    await route.fulfill({
      contentType: "application/json",
      json: { detail: "Could not validate credentials" },
      status: 401,
    });
  });

  await page.route(`${API_BASE}/auth/token`, async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postData()).toBe(
      "username=alice%40example.com&password=secret-password",
    );

    await route.fulfill({
      contentType: "application/json",
      json: { access_token: "e2e-token", token_type: "bearer" },
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Clients", exact: true }).click();

  await expect(page.getByRole("dialog", { name: "Sign in" })).toBeVisible();

  const passwordInput = page.getByLabel("Password");
  await expect(passwordInput).toHaveAttribute("type", "password");

  await page.getByLabel("Email").fill("alice@example.com");
  await passwordInput.fill("secret-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("dialog", { name: "Sign in" })).toBeHidden();
  await expect(page.getByText("No clients found.")).toBeVisible();
  expect(unauthenticatedClientRequestCount).toBeGreaterThan(0);
  expect(authenticatedClientRequestCount).toBeGreaterThan(0);
});
