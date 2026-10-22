export type StoredPage = {
  url: string;
  s3_link: string | null;
  content_hash: string | null;
  last_crawled_time: number | null;
};

export type CrawlItem =
  | (StoredPage & { status: "saved"; final_url: string; http_status: number })
  | {
      url: string;
      status: "failed";
      error: string;
      detail: string;
      http_status?: number | null;
    };

export type CrawlResult = {
  items: CrawlItem[];
  saved: number;
  failed: number;
};

export type CatalogPage = { items: StoredPage[]; next_cursor: string | null };
export type Stats = {
  total_urls: number;
  with_content: number;
  unique_contents: number;
};
export type PageDetails = StoredPage & { text: string; html_content: string };
