import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Clipboard,
  Code2,
  Database,
  ExternalLink,
  FileText,
  Globe2,
  Hash,
  Layers3,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import {
  crawlPages,
  deletePage,
  getCatalog,
  getPageDetails,
  getStats,
} from "../lib/api.functions";
import type { CrawlResult, StoredPage } from "../lib/types";

export const Route = createFileRoute("/")({ component: Dashboard });

function parseUrls(value: string): { urls: string[]; error: string | null } {
  const entries = value
    .split(/[\n,]/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (!entries.length)
    return { urls: [], error: "Добавьте хотя бы один адрес." };
  if (entries.length > 20)
    return {
      urls: [],
      error: "За один запуск можно обработать до 20 адресов.",
    };
  for (const entry of entries) {
    try {
      const url = new URL(entry);
      if (
        !["http:", "https:"].includes(url.protocol) ||
        url.username ||
        url.password
      ) {
        return {
          urls: [],
          error: `Нужен HTTP(S)-адрес без логина и пароля: ${entry}`,
        };
      }
      if (entry.length > 2048)
        return { urls: [], error: "Адрес длиннее 2048 символов." };
    } catch {
      return { urls: [], error: `Некорректный URL: ${entry}` };
    }
  }
  return { urls: [...new Set(entries)], error: null };
}

function formatDate(timestamp: number | null | undefined) {
  return timestamp
    ? new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(timestamp * 1000)
    : "—";
}

function shortHash(hash: string | null | undefined) {
  return hash ? `${hash.slice(0, 9)}…${hash.slice(-5)}` : "—";
}

function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Что-то пошло не так. Попробуйте ещё раз.";
}

function Dashboard() {
  const queryClient = useQueryClient();
  const [hydrated, setHydrated] = useState(false);
  const [input, setInput] = useState("https://example.com");
  const [inputError, setInputError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<CrawlResult | null>(null);
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<"text" | "html" | "meta">("text");
  const [hashInput, setHashInput] = useState("");
  const [appliedHash, setAppliedHash] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(0);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => setHydrated(true), []);

  const stats = useQuery({ queryKey: ["stats"], queryFn: () => getStats() });
  const catalog = useQuery({
    queryKey: ["catalog", cursors[page], appliedHash],
    queryFn: () =>
      getCatalog({ data: { cursor: cursors[page], hash: appliedHash } }),
  });
  const details = useQuery({
    queryKey: ["details", selectedUrl],
    queryFn: () => getPageDetails({ data: { url: selectedUrl! } }),
    enabled: selectedUrl !== null,
  });

  const crawl = useMutation({
    mutationFn: (urls: string[]) => crawlPages({ data: { urls } }),
    onSuccess: (result) => {
      setRunResult(result);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["catalog"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (error) => setActionError(errorText(error)),
  });
  const remove = useMutation({
    mutationFn: (url: string) => deletePage({ data: { url } }),
    onSuccess: (_, url) => {
      if (selectedUrl === url) setSelectedUrl(null);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["catalog"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      void queryClient.removeQueries({ queryKey: ["details", url] });
    },
    onError: (error) => setActionError(errorText(error)),
  });

  useEffect(() => {
    if (!selectedUrl) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedUrl(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedUrl]);

  const displayedItems = useMemo(() => {
    const items = catalog.data?.items ?? [];
    return searchInput
      ? items.filter((item) =>
          item.url.toLowerCase().includes(searchInput.toLowerCase()),
        )
      : items;
  }, [catalog.data, searchInput]);

  function runCrawl(event: React.FormEvent) {
    event.preventDefault();
    const { urls, error } = parseUrls(input);
    setInputError(error);
    if (error) return;
    setRunResult(null);
    setActionError(null);
    crawl.mutate(urls);
  }

  function applyHash(event: React.FormEvent) {
    event.preventDefault();
    const normalized = hashInput.trim().toLowerCase();
    if (normalized && !/^[a-f0-9]{64}$/.test(normalized)) {
      setActionError(
        "SHA-256 должен состоять из 64 шестнадцатеричных символов.",
      );
      return;
    }
    setActionError(null);
    setAppliedHash(normalized || null);
    setPage(0);
    setCursors([null]);
  }

  function nextPage() {
    if (!catalog.data?.next_cursor) return;
    setCursors((previous) => [
      ...previous.slice(0, page + 1),
      catalog.data!.next_cursor,
    ]);
    setPage((current) => current + 1);
  }

  async function copyHash(hash: string) {
    await navigator.clipboard.writeText(hash);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="app-shell" data-hydrated={hydrated}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Activity size={22} strokeWidth={2.6} />
          </div>
          <div>
            <strong>
              trace<span>.</span>
            </strong>
            <small>WEB CRAWLER</small>
          </div>
        </div>
        <div className="side-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav aria-label="Основная навигация">
          <a className="nav-item active" href="#overview">
            <Layers3 size={18} /> Обзор <span className="nav-dot" />
          </a>
          <a className="nav-item" href="#crawl">
            <Globe2 size={18} /> Новый обход
          </a>
          <a className="nav-item" href="#archive">
            <Database size={18} /> Архив{" "}
            <span className="nav-count">{stats.data?.total_urls ?? "—"}</span>
          </a>
        </nav>
        <div className="sidebar-bottom">
          <div className="side-info">
            <ShieldCheck size={18} />
            <div>
              <strong>Бережный обход</strong>
              <span>robots.txt · лимиты · без JS</span>
            </div>
          </div>
          <div className="side-footer">
            TRACE / 2026
            <br />
            Клиент-серверное приложение
          </div>
        </div>
      </aside>

      <main className="main-content" id="overview">
        <div className="topbar">
          <div className="breadcrumbs">
            ПРОЕКТ <ChevronRight size={14} /> ОБЗОР
          </div>
          <div className={`connection ${stats.isError ? "offline" : ""}`}>
            <span />
            {stats.isError ? "Сервер недоступен" : "Сервер подключён"}
          </div>
        </div>
        <div className="content-wrap">
          <header className="hero">
            <div>
              <div className="eyebrow">
                <span className="eyebrow-line" /> ИНСТРУМЕНТ ИССЛЕДОВАНИЯ ВЕБА
              </div>
              <h1>
                Страницы под
                <br />
                <em>контролем.</em>
              </h1>
              <p>
                Задайте адреса, получите HTML и чистый текст. Никаких скрытых
                переходов — только страницы, которые вы выбрали.
              </p>
              <a className="text-link" href="#crawl">
                Начать обход <ArrowDown size={16} />
              </a>
            </div>
            <div className="hero-art" aria-hidden="true">
              <div className="orbit orbit-one" />
              <div className="orbit orbit-two" />
              <div className="orbit orbit-three" />
              <div className="art-core">
                <Globe2 size={84} strokeWidth={1.2} />
              </div>
              <span className="orbit-node node-one" />
              <span className="orbit-node node-two" />
              <span className="orbit-node node-three" />
            </div>
          </header>

          <section className="metrics" aria-label="Статистика">
            <div className="metric">
              <div className="metric-icon lavender">
                <Globe2 size={21} />
              </div>
              <span>Адресов в архиве</span>
              <strong>
                {stats.isPending ? "…" : (stats.data?.total_urls ?? "—")}
              </strong>
              <small>проверенных URL</small>
            </div>
            <div className="metric">
              <div className="metric-icon peach">
                <FileText size={21} />
              </div>
              <span>HTML-страниц</span>
              <strong>
                {stats.isPending ? "…" : (stats.data?.with_content ?? "—")}
              </strong>
              <small>успешно сохранено</small>
            </div>
            <div className="metric">
              <div className="metric-icon mint">
                <Hash size={21} />
              </div>
              <span>Уникальный контент</span>
              <strong>
                {stats.isPending ? "…" : (stats.data?.unique_contents ?? "—")}
              </strong>
              <small>по хешу SHA-256</small>
            </div>
          </section>

          <section className="panel crawl-panel" id="crawl">
            <div className="section-heading">
              <div>
                <span className="section-kicker">01 / ЗАГРУЗКА</span>
                <h2>Новый обход</h2>
                <p>Один URL на строку. Максимум 20 адресов за запуск.</p>
              </div>
              <span className="panel-badge">
                <Plus size={14} /> НОВАЯ ЗАДАЧА
              </span>
            </div>
            <form onSubmit={runCrawl}>
              <label className="field-label" htmlFor="url-input">
                АДРЕСА СТРАНИЦ
              </label>
              <div className={`input-wrap ${inputError ? "invalid" : ""}`}>
                <span className="input-prefix">
                  <Globe2 size={17} />
                </span>
                <textarea
                  id="url-input"
                  value={input}
                  onChange={(event) => {
                    setInput(event.target.value);
                    setInputError(null);
                  }}
                  placeholder={"https://example.com\nhttps://example.org"}
                  spellCheck={false}
                  rows={3}
                  aria-invalid={Boolean(inputError)}
                  aria-describedby={inputError ? "url-error" : undefined}
                />
              </div>
              {inputError && (
                <p className="field-error" id="url-error">
                  {inputError}
                </p>
              )}
              <div className="form-bottom">
                <div className="suggestions">
                  Попробуйте:{" "}
                  <button
                    type="button"
                    onClick={() => setInput("https://example.com")}
                  >
                    example.com
                  </button>
                  <button
                    type="button"
                    onClick={() => setInput("https://example.org")}
                  >
                    example.org
                  </button>
                </div>
                <button
                  className="primary-button"
                  disabled={crawl.isPending}
                  type="submit"
                >
                  {crawl.isPending ? (
                    <LoaderCircle className="spin" size={18} />
                  ) : (
                    <Play size={17} fill="currentColor" />
                  )}{" "}
                  {crawl.isPending ? "Обрабатываем…" : "Запустить обход"}{" "}
                  <ArrowRight size={17} />
                </button>
              </div>
            </form>
            {crawl.isPending && (
              <div className="progress-note" role="status">
                <LoaderCircle className="spin" size={16} /> Сверяемся с
                robots.txt, загружаем и сохраняем страницы…
              </div>
            )}
          </section>

          {(actionError || runResult) && (
            <section className="result-section" aria-label="Результаты обхода">
              {actionError && (
                <div className="alert error" role="alert">
                  <X size={18} />
                  {actionError}
                  <button
                    type="button"
                    onClick={() => setActionError(null)}
                    aria-label="Закрыть сообщение"
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
              {runResult && (
                <div className="panel result-panel">
                  <div className="result-title">
                    <div>
                      <span className="section-kicker">ПОСЛЕДНИЙ ЗАПУСК</span>
                      <h2>Результаты обхода</h2>
                    </div>
                    <div className="result-summary">
                      <span className="saved-count">
                        <Check size={15} /> {runResult.saved} сохранено
                      </span>
                      <span className="failed-count">
                        {runResult.failed} ошибок
                      </span>
                    </div>
                  </div>
                  <div className="result-list">
                    {runResult.items.map((item) => (
                      <div className="result-row" key={item.url}>
                        <span className={`result-indicator ${item.status}`}>
                          <span />
                        </span>
                        <div>
                          <strong>{item.url}</strong>
                          <small>
                            {item.status === "saved"
                              ? `HTTP ${item.http_status} · ${shortHash(item.content_hash)}`
                              : `${item.detail}${item.http_status ? ` · HTTP ${item.http_status}` : ""}`}
                          </small>
                        </div>
                        {item.status === "saved" && (
                          <button
                            type="button"
                            className="inline-action"
                            onClick={() => {
                              setSelectedUrl(item.url);
                              setDetailTab("text");
                            }}
                          >
                            Открыть <ArrowUpRight size={15} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          <section className="panel archive-panel" id="archive">
            <div className="section-heading archive-heading">
              <div>
                <span className="section-kicker">02 / ХРАНИЛИЩЕ</span>
                <h2>Архив страниц</h2>
                <p>Сохранённые адреса и снимки их содержимого.</p>
              </div>
              <button
                className="icon-button refresh"
                type="button"
                onClick={() => {
                  void queryClient.invalidateQueries({ queryKey: ["catalog"] });
                  void queryClient.invalidateQueries({ queryKey: ["stats"] });
                }}
                aria-label="Обновить архив"
              >
                <RefreshCw size={18} />
              </button>
            </div>
            <div className="archive-tools">
              <label className="search-field">
                <Search size={17} />
                <input
                  aria-label="Поиск URL на странице каталога"
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="Найти URL на этой странице…"
                />
              </label>
              <form onSubmit={applyHash} className="hash-filter">
                <Hash size={16} />
                <input
                  aria-label="Фильтр по SHA-256"
                  value={hashInput}
                  onChange={(event) => setHashInput(event.target.value)}
                  placeholder="Фильтр по SHA-256"
                />
                <button type="submit" aria-label="Применить фильтр">
                  <ArrowRight size={16} />
                </button>
              </form>
            </div>
            {appliedHash && (
              <div className="filter-tag">
                SHA-256: {shortHash(appliedHash)}{" "}
                <button
                  type="button"
                  onClick={() => {
                    setAppliedHash(null);
                    setHashInput("");
                    setPage(0);
                    setCursors([null]);
                  }}
                  aria-label="Сбросить фильтр"
                >
                  <X size={13} />
                </button>
              </div>
            )}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>СТРАНИЦА</th>
                    <th>ХЕШ СОДЕРЖИМОГО</th>
                    <th>ЗАГРУЖЕНО</th>
                    <th aria-label="Действия" />
                  </tr>
                </thead>
                <tbody>
                  {catalog.isPending ? (
                    <tr>
                      <td colSpan={4}>
                        <div className="table-state">
                          <LoaderCircle className="spin" size={22} /> Загружаем
                          архив…
                        </div>
                      </td>
                    </tr>
                  ) : catalog.isError ? (
                    <tr>
                      <td colSpan={4}>
                        <div className="table-state error-state">
                          {errorText(catalog.error)}{" "}
                          <button
                            type="button"
                            onClick={() => void catalog.refetch()}
                          >
                            Повторить
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : displayedItems.length ? (
                    displayedItems.map((item) => (
                      <ArchiveRow
                        key={item.url}
                        item={item}
                        onOpen={() => {
                          setSelectedUrl(item.url);
                          setDetailTab("text");
                        }}
                        onDelete={() => remove.mutate(item.url)}
                        deleting={
                          remove.isPending && remove.variables === item.url
                        }
                      />
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4}>
                        <div className="table-state empty-state">
                          <Database size={24} />
                          <strong>Здесь пока пусто</strong>
                          <span>
                            {searchInput || appliedHash
                              ? "По этому запросу ничего не найдено."
                              : "Запустите обход, чтобы первая страница появилась в архиве."}
                          </span>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span>
                Страница {page + 1} · {displayedItems.length} записей
              </span>
              <div>
                <button
                  type="button"
                  disabled={page === 0 || catalog.isFetching}
                  onClick={() => setPage((current) => current - 1)}
                  aria-label="Предыдущая страница"
                >
                  <ArrowLeft size={17} />
                </button>
                <button
                  type="button"
                  disabled={!catalog.data?.next_cursor || catalog.isFetching}
                  onClick={nextPage}
                  aria-label="Следующая страница"
                >
                  <ArrowRight size={17} />
                </button>
              </div>
            </div>
          </section>
          <footer className="main-footer">
            <span>TRACE / CRAWLER</span>
            <span>
              Только заданные URL · robots.txt · без исполнения JavaScript
            </span>
          </footer>
        </div>
      </main>

      {selectedUrl && (
        <div
          className="drawer-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelectedUrl(null);
          }}
        >
          <aside
            className="detail-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Данные страницы"
          >
            <div className="drawer-header">
              <div>
                <span className="section-kicker">ПРОСМОТР СТРАНИЦЫ</span>
                <h2>Данные URL</h2>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setSelectedUrl(null)}
                aria-label="Закрыть"
              >
                <X size={20} />
              </button>
            </div>
            <div className="drawer-url">
              <Globe2 size={18} />
              <span>{selectedUrl}</span>
              <a
                href={selectedUrl}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Открыть сайт"
              >
                <ExternalLink size={16} />
              </a>
            </div>
            <div className="tab-list" role="tablist" aria-label="Вид данных">
              <button
                role="tab"
                aria-selected={detailTab === "text"}
                className={detailTab === "text" ? "active" : ""}
                onClick={() => setDetailTab("text")}
                type="button"
              >
                <FileText size={16} /> Текст
              </button>
              <button
                role="tab"
                aria-selected={detailTab === "html"}
                className={detailTab === "html" ? "active" : ""}
                onClick={() => setDetailTab("html")}
                type="button"
              >
                <Code2 size={16} /> HTML
              </button>
              <button
                role="tab"
                aria-selected={detailTab === "meta"}
                className={detailTab === "meta" ? "active" : ""}
                onClick={() => setDetailTab("meta")}
                type="button"
              >
                <Hash size={16} /> Метаданные
              </button>
            </div>
            <div className="drawer-body" role="tabpanel">
              {details.isPending ? (
                <div className="drawer-state">
                  <LoaderCircle className="spin" size={24} /> Загружаем
                  содержимое…
                </div>
              ) : details.isError ? (
                <div className="drawer-state error-state">
                  {errorText(details.error)}{" "}
                  <button type="button" onClick={() => void details.refetch()}>
                    Повторить
                  </button>
                </div>
              ) : detailTab === "text" ? (
                <div className="text-content">
                  <div className="content-label">
                    ИЗВЛЕЧЁННЫЙ ТЕКСТ <span>selectolax / Lexbor</span>
                  </div>
                  <p>
                    {details.data.text || "На странице нет видимого текста."}
                  </p>
                </div>
              ) : detailTab === "html" ? (
                <div className="html-content">
                  <div className="content-label">
                    ИСХОДНЫЙ HTML{" "}
                    <span>
                      {details.data.html_content.length.toLocaleString("ru-RU")}{" "}
                      символов
                    </span>
                  </div>
                  <pre>{details.data.html_content}</pre>
                </div>
              ) : (
                <div className="metadata">
                  <div className="meta-row">
                    <span>URL</span>
                    <strong>{details.data.url}</strong>
                  </div>
                  <div className="meta-row">
                    <span>SHA-256</span>
                    <div>
                      <strong className="mono hash-full">
                        {details.data.content_hash || "—"}
                      </strong>
                      {details.data.content_hash && (
                        <button
                          type="button"
                          onClick={() =>
                            void copyHash(details.data.content_hash!)
                          }
                          aria-label="Скопировать хеш"
                        >
                          {copied ? (
                            <Check size={16} />
                          ) : (
                            <Clipboard size={16} />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="meta-row">
                    <span>Загружено</span>
                    <strong>
                      {formatDate(details.data.last_crawled_time)}
                    </strong>
                  </div>
                  <div className="meta-row">
                    <span>Ссылка на хранилище</span>
                    <strong className="mono">
                      {details.data.s3_link || "—"}
                    </strong>
                  </div>
                </div>
              )}
            </div>
            <div className="drawer-footer">
              <button
                type="button"
                className="danger-button"
                disabled={remove.isPending}
                onClick={() => remove.mutate(selectedUrl)}
              >
                <Trash2 size={16} />{" "}
                {remove.isPending ? "Удаляем…" : "Удалить из архива"}
              </button>
              <span>
                Удаляется запись URL. Общий HTML остаётся в хранилище.
              </span>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function ArchiveRow({
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
  let hostname = item.url;
  try {
    hostname = new URL(item.url).hostname;
  } catch {}
  return (
    <tr>
      <td>
        <button className="page-cell" type="button" onClick={onOpen}>
          <span className="site-avatar">
            <Globe2 size={17} />
          </span>
          <span>
            <strong>{hostname}</strong>
            <small>{item.url}</small>
          </span>
        </button>
      </td>
      <td>
        <span className="hash-cell">{shortHash(item.content_hash)}</span>
      </td>
      <td>
        <span className="date-cell">{formatDate(item.last_crawled_time)}</span>
      </td>
      <td>
        <div className="row-actions">
          <button
            type="button"
            title="Просмотреть"
            aria-label={`Просмотреть ${item.url}`}
            onClick={onOpen}
          >
            <ArrowUpRight size={17} />
          </button>
          <button
            type="button"
            title="Удалить"
            aria-label={`Удалить ${item.url}`}
            disabled={deleting}
            onClick={onDelete}
          >
            {deleting ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Trash2 size={16} />
            )}
          </button>
        </div>
      </td>
    </tr>
  );
}
