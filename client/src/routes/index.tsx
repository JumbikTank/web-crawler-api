import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { CrawlForm } from "../components/CrawlForm";
import { CrawlResults } from "../components/CrawlResults";
import { Notice } from "../components/Notice";
import { PageCatalog } from "../components/PageCatalog";
import { PageDetails } from "../components/PageDetails";
import { crawlPages, deletePage, getStats } from "../lib/api.functions";
import { errorText } from "../lib/format";
import type { CrawlResult } from "../lib/types";

export const Route = createFileRoute("/")({ component: Dashboard });

function Dashboard() {
  const queryClient = useQueryClient();
  const [hydrated, setHydrated] = useState(false);
  const [result, setResult] = useState<CrawlResult | null>(null);
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => setHydrated(true), []);

  const stats = useQuery({ queryKey: ["stats"], queryFn: () => getStats() });
  const crawl = useMutation({
    mutationFn: (urls: string[]) => crawlPages({ data: { urls } }),
    onMutate: () => {
      setResult(null);
      setActionError(null);
    },
    onSuccess: (data) => {
      setResult(data);
      void queryClient.invalidateQueries({ queryKey: ["catalog"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (error) => setActionError(errorText(error)),
  });
  const remove = useMutation({
    mutationFn: (url: string) => deletePage({ data: { url } }),
    onMutate: () => setActionError(null),
    onSuccess: (_, url) => {
      if (selectedUrl === url) setSelectedUrl(null);
      void queryClient.invalidateQueries({ queryKey: ["catalog"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (error) => setActionError(errorText(error)),
  });

  return (
    <main className="workspace" data-hydrated={hydrated}>
      <header className="site-header">
        <strong>Краулер</strong>
        <span className={stats.isError ? "connection offline" : "connection"}>
          <i aria-hidden="true" />
          {stats.isPending
            ? "Подключаемся…"
            : stats.isError
              ? "Сервер недоступен"
              : "Сервер подключён"}
        </span>
      </header>

      <div className="intro">
        <h1>Обход веб-страниц</h1>
        <p>
          Укажите адреса, чтобы сохранить HTML и прочитать извлечённый текст.
        </p>
        {stats.data && (
          <p className="archive-count">
            В архиве {stats.data.total_urls} URL · {stats.data.unique_contents}{" "}
            уникальных HTML
          </p>
        )}
      </div>

      {stats.isError && (
        <Notice
          kind="error"
          action={{ label: "Повторить", onClick: () => void stats.refetch() }}
        >
          {errorText(stats.error)}
        </Notice>
      )}
      {actionError && <Notice kind="error">{actionError}</Notice>}
      <CrawlForm
        onSubmit={(urls) => crawl.mutate(urls)}
        pending={crawl.isPending}
      />
      {result && <CrawlResults result={result} onOpen={setSelectedUrl} />}
      <PageCatalog
        onOpen={setSelectedUrl}
        onDelete={(url) => remove.mutate(url)}
        deletingUrl={remove.isPending ? remove.variables : null}
      />
      <PageDetails
        url={selectedUrl}
        onClose={() => setSelectedUrl(null)}
        onDelete={(url) => remove.mutate(url)}
        deleting={remove.isPending}
      />
    </main>
  );
}
