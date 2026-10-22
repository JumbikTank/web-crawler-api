import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getCatalog } from "../lib/api.functions";
import { errorText, formatDate, shortHash } from "../lib/format";
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
  const [hashInput, setHashInput] = useState("");
  const [hash, setHash] = useState<string | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);

  const catalog = useQuery({
    queryKey: ["catalog", hash, cursors[page]],
    queryFn: () => getCatalog({ data: { hash, cursor: cursors[page] } }),
  });

  function resetPage() {
    setPage(0);
    setCursors([null]);
  }

  function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = hashInput.trim().toLowerCase();
    if (value && !/^[a-f0-9]{64}$/.test(value)) {
      setFilterError(
        "Введите полный SHA-256: 64 символа от 0 до 9 и от a до f.",
      );
      return;
    }
    setFilterError(null);
    setHash(value || null);
    resetPage();
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
    <section className="section" aria-labelledby="catalog-heading">
      <div className="section-title">
        <h2 id="catalog-heading">Сохранённые страницы</h2>
        <button
          className="text-button"
          type="button"
          onClick={() =>
            void queryClient.invalidateQueries({ queryKey: ["catalog"] })
          }
        >
          Обновить
        </button>
      </div>

      <details className="filter-details">
        <summary>Фильтр по SHA-256 {hash && `· ${shortHash(hash)}`}</summary>
        <form onSubmit={applyFilter} className="filter-form">
          <input
            type="text"
            aria-label="Фильтр по SHA-256"
            value={hashInput}
            onChange={(event) => {
              setHashInput(event.target.value);
              setFilterError(null);
            }}
            placeholder="Полный SHA-256, 64 символа"
          />
          <button className="button button-secondary" type="submit">
            Применить
          </button>
          {hash && (
            <button
              className="text-button"
              type="button"
              onClick={() => {
                setHash(null);
                setHashInput("");
                setFilterError(null);
                resetPage();
              }}
            >
              Сбросить
            </button>
          )}
        </form>
        {filterError && <Notice kind="error">{filterError}</Notice>}
      </details>

      {catalog.isPending ? (
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
        <p className="list-state">
          {hash
            ? "Страниц с таким хешем нет."
            : "Пока пусто. Запустите обход выше."}
        </p>
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
  return (
    <li className="catalog-row">
      <div className="page-summary">
        <strong>{item.url}</strong>
        <span>
          {formatDate(item.last_crawled_time)} · SHA-256{" "}
          {shortHash(item.content_hash)}
        </span>
      </div>
      <div className="row-actions">
        <button className="text-button" type="button" onClick={onOpen}>
          Открыть
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
