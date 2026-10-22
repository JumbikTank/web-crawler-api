import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import type {
  CatalogPage,
  CrawlResult,
  PageDetails,
  Stats,
  StoredPage,
} from "./types";

const webUrl = z
  .url()
  .max(2048)
  .refine((value) => {
    const parsed = new URL(value);
    return (
      ["http:", "https:"].includes(parsed.protocol) &&
      !parsed.username &&
      !parsed.password
    );
  }, "Введите HTTP(S)-адрес без логина и пароля");

export const getStats = createServerFn({ method: "GET" }).handler(
  async (): Promise<Stats> => {
    const { requestApi } = await import("./api.server");
    return requestApi<Stats>("/stats");
  },
);

export const getCatalog = createServerFn({ method: "GET" })
  .validator(
    z.object({ cursor: z.string().nullable(), hash: z.string().nullable() }),
  )
  .handler(async ({ data }): Promise<CatalogPage> => {
    const { requestApi } = await import("./api.server");
    const params = new URLSearchParams({ limit: "20" });
    if (data.cursor) params.set("cursor", data.cursor);
    if (data.hash) params.set("content_hash", data.hash);
    return requestApi<CatalogPage>(`/urls?${params}`);
  });

export const crawlPages = createServerFn({ method: "POST" })
  .validator(z.object({ urls: z.array(webUrl).min(1).max(20) }))
  .handler(async ({ data }): Promise<CrawlResult> => {
    const { requestApi } = await import("./api.server");
    return requestApi<CrawlResult>("/crawl", {
      method: "POST",
      body: JSON.stringify(data),
    });
  });

export const getPageDetails = createServerFn({ method: "GET" })
  .validator(z.object({ url: webUrl }))
  .handler(async ({ data }): Promise<PageDetails> => {
    const { requestApi } = await import("./api.server");
    const query = new URLSearchParams({ url: data.url });
    const [metadata, text, html] = await Promise.all([
      requestApi<StoredPage>(`/url-data?${query}`),
      requestApi<{ text: string }>(`/text?${query}`),
      requestApi<{ html_content: string }>(`/html?${query}`),
    ]);
    return { ...metadata, text: text.text, html_content: html.html_content };
  });

export const deletePage = createServerFn({ method: "POST" })
  .validator(z.object({ url: webUrl }))
  .handler(async ({ data }): Promise<{ deleted: true }> => {
    const { requestApi } = await import("./api.server");
    await requestApi<void>(
      `/url-data?${new URLSearchParams({ url: data.url })}`,
      {
        method: "DELETE",
      },
    );
    return { deleted: true };
  });
