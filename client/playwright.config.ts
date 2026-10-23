import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  workers: 1,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:3100",
    viewport: { width: 1280, height: 850 },
    video: { mode: "on", size: { width: 1280, height: 850 } },
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        "uv run --frozen uvicorn crawler.app:app --host 127.0.0.1 --port 8100",
      cwd: root,
      env: { DATABASE_PATH: "client/.e2e/crawler.sqlite3" },
      url: "http://127.0.0.1:8100/health",
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev",
      cwd: import.meta.dirname,
      env: { CLIENT_PORT: "3100", CRAWLER_API_URL: "http://127.0.0.1:8100" },
      url: "http://127.0.0.1:3100/",
      timeout: 30_000,
      reuseExistingServer: false,
    },
  ],
});
