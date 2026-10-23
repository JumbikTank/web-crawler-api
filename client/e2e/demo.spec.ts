import { expect, test } from "@playwright/test";

test("recorded walkthrough", async ({ page, request }) => {
  await request.delete("http://127.0.0.1:8100/url-data", {
    params: { url: "https://example.com" },
  });
  await page.goto("/");
  await expect(page.locator('[data-hydrated="true"]')).toBeVisible();
  await expect(page.getByText("Сервер подключён")).toBeVisible();
  await page.waitForTimeout(2500);

  const input = page.getByRole("textbox", { name: "URL-адреса" });
  await input.fill("wrong-url");
  await page.waitForTimeout(1300);
  await page.getByRole("button", { name: /Начать обход/ }).click();
  await expect(page.getByText("Некорректный URL: wrong-url")).toBeVisible();
  await page.waitForTimeout(2200);

  await input.fill("https://example.com\nhttps://example.com/no-such-page");
  await page.waitForTimeout(2200);
  await page.getByRole("button", { name: /Начать обход/ }).click();
  await expect(page.getByText("1 сохранено · 1 ошибок")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/HTTP 404/)).toBeVisible();
  await page.waitForTimeout(2800);

  await page
    .getByRole("button", { name: /Открыть/ })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByText("This domain is for use in documentation examples"),
  ).toBeVisible();
  await page.waitForTimeout(2600);
  await dialog.getByRole("tab", { name: "HTML" }).click();
  await expect(dialog.locator("pre")).toContainText("<!doctype html>");
  await page.waitForTimeout(2300);
  await dialog.getByRole("tab", { name: "О странице" }).click();
  await expect(dialog.getByText("HTML-страница")).toBeVisible();
  await page.waitForTimeout(2300);
  await dialog.getByRole("button", { name: "Закрыть" }).click();
  await page.waitForTimeout(1600);

  await page
    .getByRole("textbox", { name: "Найти URL в архиве" })
    .fill("https://example.com");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Найти", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Удалить https://example.com" }),
  ).toBeVisible();
  await page.waitForTimeout(2100);

  await page
    .getByRole("button", { name: "Удалить https://example.com" })
    .click();
  await expect(
    page.getByText("Страница с таким адресом не найдена."),
  ).toBeVisible();
  const missing = await request.get("http://127.0.0.1:8100/url-data", {
    params: { url: "https://example.com" },
  });
  expect(missing.status()).toBe(404);
  await page.waitForTimeout(3000);
});
