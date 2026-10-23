import type { CrawlResult } from "../lib/types";

export function CrawlResults({
  result,
  onOpen,
}: {
  result: CrawlResult;
  onOpen: (url: string) => void;
}) {
  return (
    <section
      className="section results-section"
      aria-labelledby="results-heading"
    >
      <div className="section-title">
        <h2 id="results-heading">Результаты</h2>
        <span>
          {result.saved} сохранено · {result.failed} ошибок
        </span>
      </div>
      <ul className="results-list">
        {result.items.map((item) => (
          <li key={item.url} className="result-item">
            <div className="result-description">
              <span
                className={`status-mark ${item.status}`}
                aria-hidden="true"
              />
              <div>
                <strong>{item.url}</strong>
                <small>
                  {item.status === "saved"
                    ? `Сохранено · HTTP ${item.http_status}`
                    : `${item.detail}${item.http_status ? ` · HTTP ${item.http_status}` : ""}`}
                </small>
              </div>
            </div>
            {item.status === "saved" && (
              <button
                className="text-button"
                type="button"
                onClick={() => onOpen(item.url)}
              >
                Открыть
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
