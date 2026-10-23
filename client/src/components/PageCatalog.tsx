import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getCatalog, getPageMeta } from "../lib/api.functions";
import { errorText, formatDate } from "../lib/format";
import { parseUrls } from "../lib/validation";
import type { StoredPage } from "../lib/types";
import { Notice } from "./Notice";

export function PageCatalog({
  onOpen,
  onDelete,
  deletingUrl,
}: {
  onOpen: (url: string) => void;
  onDelete: (url: string) => void;
  deletingUrl: string | null;
}) {
  const queryClient = useQueryClient();
  const [searchInput, setSearchInput] = useState("");
  const [searchedUrl, setSearchedUrl] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);

  const catalog = useQuery({
    queryKey: ["catalog", cursors[page]],
    queryFn: () => getCatalog({ data: { hash: null, cursor: cursors[page] } }),
  });
  const found = useQuery({
    queryKey: ["lookup", searchedUrl],
    queryFn: () => getPageMeta({ data: { url: searchedUrl! } }),
    enabled: Boolean(searchedUrl),
    retry: false,
  });

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = parseUrls(searchInput);
    if (parsed.error || parsed.urls.length !== 1) {
      setSearchError(parsed.error ?? "Введите один URL-адрес.");
      return;
    }
    setSearchError(null);
    setSearchedUrl(parsed.urls[0]);
  }

  function nextPage() {
    if (!catalog.data?.next_cursor) return;
    setCursors((current) => [
      ...current.slice(0, page + 1),
      catalog.data!.next_cursor,
    ]);
    setPage((current) => current + 1);
  }

  return (
    <section
      className="section catalog-section"
      aria-labelledby="catalog-heading"
    >
      <div className="section-title">
        <div>
          <span className="eyebrow">02 / Ваша библиотека</span>
          <h2 id="catalog-heading">Архив страниц</h2>
        </div>
        <button
          className="text-button"
          type="button"
          onClick={() => {
            void queryClient.invalidateQueries({ queryKey: ["catalog"] });
            void queryClient.invalidateQueries({ queryKey: ["lookup"] });
          }}
        >
          Обновить ↗
        </button>
      </div>

      <form className="search-form" onSubmit={search}>
        <label className="sr-only" htmlFor="catalog-search">
          Найти URL в архиве
        </label>
        <input
          id="catalog-search"
          type="url"
          value={searchInput}
          onChange={(event) => {
            setSearchInput(event.target.value);
            setSearchError(null);
          }}
          placeholder="Найти страницу по URL"
        />
        <button className="button button-secondary" type="submit">
          Найти
        </button>
        {searchedUrl && (
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setSearchedUrl(null);
              setSearchInput("");
              setSearchError(null);
            }}
          >
            Сбросить
          </button>
        )}
      </form>
      {searchError && <Notice kind="error">{searchError}</Notice>}

      {searchedUrl ? (
        found.isPending ? (
          <p className="list-state" role="status">
            Ищем страницу…
          </p>
        ) : found.isError ? (
          /404|not found|не найден/i.test(errorText(found.error)) ? (
            <p className="list-state">Страница с таким адресом не найдена.</p>
          ) : (
            <Notice
              kind="error"
              action={{
                label: "Повторить",
                onClick: () => void found.refetch(),
              }}
            >
              {errorText(found.error)}
            </Notice>
          )
        ) : (
          <ul className="catalog-list">
            <PageRow
              item={found.data}
              onOpen={() => onOpen(found.data.url)}
              onDelete={() => onDelete(found.data.url)}
              deleting={deletingUrl === found.data.url}
            />
          </ul>
        )
      ) : catalog.isPending ? (
        <p className="list-state" role="status">
          Загружаем архив…
        </p>
      ) : catalog.isError ? (
        <Notice
          kind="error"
          action={{ label: "Повторить", onClick: () => void catalog.refetch() }}
        >
          {errorText(catalog.error)}
        </Notice>
      ) : catalog.data.items.length === 0 ? (
        <div className="empty-state">
          <span aria-hidden="true">↗</span>
          <p>Здесь появятся страницы после первого обхода.</p>
        </div>
      ) : (
        <ul className="catalog-list">
          {catalog.data.items.map((item) => (
            <PageRow
              key={item.url}
              item={item}
              onOpen={() => onOpen(item.url)}
              onDelete={() => onDelete(item.url)}
              deleting={deletingUrl === item.url}
            />
          ))}
        </ul>
      )}

      {!searchedUrl && (
        <div className="pagination">
          <span>Страница {page + 1}</span>
          <div>
            <button
              className="button button-secondary"
              type="button"
              disabled={page === 0 || catalog.isFetching}
              onClick={() => setPage((current) => current - 1)}
            >
              Назад
            </button>
            <button
              className="button button-secondary"
              type="button"
              disabled={!catalog.data?.next_cursor || catalog.isFetching}
              onClick={nextPage}
            >
              Далее
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function PageRow({
  item,
  onOpen,
  onDelete,
  deleting,
}: {
  item: StoredPage;
  onOpen: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const hostname = new URL(item.url).hostname;
  return (
    <li className="catalog-row">
      <div className="site-avatar" aria-hidden="true">
        {hostname.charAt(0).toUpperCase()}
      </div>
      <div className="page-summary">
        <strong>{hostname}</strong>
        <span className="page-url">{item.url}</span>
        <span>Сохранено {formatDate(item.last_crawled_time)}</span>
      </div>
      <div className="row-actions">
        <button className="text-button" type="button" onClick={onOpen}>
          Открыть ↗
        </button>
        <button
          className="text-button danger-text"
          type="button"
          disabled={deleting}
          onClick={onDelete}
          aria-label={`Удалить ${item.url}`}
        >
          {deleting ? "Удаляем…" : "Удалить"}
        </button>
      </div>
    </li>
  );
}
