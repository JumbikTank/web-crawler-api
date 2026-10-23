import { expect, test } from "@playwright/test";

test("recorded walkthrough", async ({ page, request }) => {
  await request.delete("http://127.0.0.1:8100/url-data", {
    params: { url: "https://example.com" },
  });
  await page.goto("/");
  await expect(page.locator('[data-hydrated="true"]')).toBeVisible();
  await expect(page.getByText("Сервер подключён")).toBeVisible();
  await page.waitForTimeout(1200);

  const input = page.getByRole("textbox", { name: "URL-адреса" });
  await input.click();
  await input.pressSequentially("wrong-url", { delay: 55 });
  await page.getByRole("button", { name: "Начать обход" }).click();
  await expect(page.getByText("Некорректный URL: wrong-url")).toBeVisible();
  await page.waitForTimeout(1300);

  await input.fill("");
  await input.pressSequentially("https://example.com", { delay: 35 });
  await input.press("Enter");
  await input.pressSequentially("https://example.com/no-such-page", {
    delay: 28,
  });
  await page.waitForTimeout(600);
  await page.getByRole("button", { name: "Начать обход" }).click();
  await expect(page.getByText("1 сохранено · 1 ошибок")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/HTTP 404/)).toBeVisible();
  await page.waitForTimeout(1800);

  await page.getByRole("button", { name: "Открыть" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByText("This domain is for use in documentation examples"),
  ).toBeVisible();
  await page.waitForTimeout(1800);
  await dialog.getByRole("tab", { name: "HTML" }).click();
  await expect(dialog.locator("pre")).toContainText("<!doctype html>");
  await page.waitForTimeout(1500);
  await dialog.getByRole("tab", { name: "Метаданные" }).click();
  await expect(dialog.getByText("Отпечаток HTML")).toBeVisible();
  await page.waitForTimeout(1800);
  await dialog.getByRole("button", { name: "Закрыть" }).click();
  await page.waitForTimeout(850);

  await page
    .getByRole("button", { name: "Удалить https://example.com" })
    .click();
  await expect(
    page.getByText("Пока пусто. Запустите обход выше."),
  ).toBeVisible();
  const missing = await request.get("http://127.0.0.1:8100/url-data", {
    params: { url: "https://example.com" },
  });
  expect(missing.status()).toBe(404);
  await page.waitForTimeout(1800);
});
