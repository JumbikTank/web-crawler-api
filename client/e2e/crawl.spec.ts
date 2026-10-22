import { expect, test } from "@playwright/test";

test("URL validation, crawl, archive, page views and deletion reach the Python server", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.locator('[data-hydrated="true"]')).toBeVisible();
  await expect(page.getByText("Сервер подключён")).toBeVisible();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: "../docs/screenshots/overview.png" });

  const input = page.getByRole("textbox", { name: "АДРЕСА СТРАНИЦ" });
  await input.fill("this-is-not-a-url");
  await page.getByRole("button", { name: "Запустить обход" }).click();
  await expect(
    page.getByText("Некорректный URL: this-is-not-a-url"),
  ).toBeVisible();
  await page.waitForTimeout(1500);

  await input.fill("https://example.com\nhttps://example.com/no-such-page");
  await page.getByRole("button", { name: "Запустить обход" }).click();
  await expect(page.getByText("1 сохранено")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("1 ошибок")).toBeVisible();
  await expect(page.getByText(/HTTP 404/)).toBeVisible();
  await page.waitForTimeout(1300);
  await page.getByText("Результаты обхода").scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, 130));
  await page.screenshot({ path: "../docs/screenshots/crawl-results.png" });
  await page.waitForTimeout(1100);

  const metadata = await request.get("http://127.0.0.1:8100/url-data", {
    params: { url: "https://example.com" },
  });
  expect(metadata.ok()).toBeTruthy();
  const stored = (await metadata.json()) as { content_hash: string };
  expect(stored.content_hash).toMatch(/^[a-f0-9]{64}$/);

  await page.getByRole("button", { name: "Открыть" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByText("This domain is for use in documentation examples"),
  ).toBeVisible();
  await page.waitForTimeout(1700);
  await page.screenshot({ path: "../docs/screenshots/page-details.png" });

  await page.getByRole("tab", { name: "HTML" }).click();
  await expect(page.locator("pre")).toContainText("<!doctype html>");
  await page.waitForTimeout(1500);
  await page.getByRole("tab", { name: "Метаданные" }).click();
  await expect(
    page.getByText(stored.content_hash, { exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Закрыть" }).click();

  await page
    .getByRole("textbox", { name: "Фильтр по SHA-256" })
    .fill(stored.content_hash);
  await page.getByRole("button", { name: "Применить фильтр" }).click();
  await expect(
    page.getByRole("button", { name: /example\.com/ }).last(),
  ).toBeVisible();
  await page.waitForTimeout(1200);
  await page
    .getByRole("button", { name: "Удалить https://example.com" })
    .click();
  await expect(page.getByText("Здесь пока пусто")).toBeVisible();
  const missing = await request.get("http://127.0.0.1:8100/url-data", {
    params: { url: "https://example.com" },
  });
  expect(missing.status()).toBe(404);
  await page.waitForTimeout(1500);
});
