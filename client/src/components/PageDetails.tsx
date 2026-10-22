import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPageDetails } from "../lib/api.functions";
import { errorText, formatDate } from "../lib/format";
import { Notice } from "./Notice";

type Tab = "text" | "html" | "meta";

export function PageDetails({
  url,
  onClose,
  onDelete,
  deleting,
}: {
  url: string | null;
  onClose: () => void;
  onDelete: (url: string) => void;
  deleting: boolean;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<Tab>("text");
  const details = useQuery({
    queryKey: ["details", url],
    queryFn: () => getPageDetails({ data: { url: url! } }),
    enabled: Boolean(url),
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (url && dialog && !dialog.open) dialog.showModal();
    if (!url && dialog?.open) dialog.close();
    setTab("text");
  }, [url]);

  return (
    <dialog
      ref={dialogRef}
      className="page-dialog"
      aria-label="Просмотр страницы"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="dialog-content">
        <header className="dialog-header">
          <div>
            <span className="eyebrow">Сохранённая страница</span>
            <h2>{url}</h2>
          </div>
          <button className="text-button" type="button" onClick={onClose}>
            Закрыть
          </button>
        </header>
        {details.isPending ? (
          <p className="list-state" role="status">
            Загружаем страницу…
          </p>
        ) : details.isError ? (
          <Notice
            kind="error"
            action={{
              label: "Повторить",
              onClick: () => void details.refetch(),
            }}
          >
            {errorText(details.error)}
          </Notice>
        ) : (
          <>
            <div className="tabs" role="tablist" aria-label="Данные страницы">
              {(["text", "html", "meta"] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={tab === key}
                  onClick={() => setTab(key)}
                >
                  {key === "text"
                    ? "Текст"
                    : key === "html"
                      ? "HTML"
                      : "Метаданные"}
                </button>
              ))}
            </div>
            <div className="tab-panel" role="tabpanel">
              {tab === "text" && (
                <pre>{details.data.text || "Текст не найден."}</pre>
              )}
              {tab === "html" && <pre>{details.data.html_content}</pre>}
              {tab === "meta" && (
                <dl className="metadata">
                  <div>
                    <dt>URL</dt>
                    <dd>{details.data.url}</dd>
                  </div>
                  <div>
                    <dt>SHA-256</dt>
                    <dd>{details.data.content_hash ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Сохранено</dt>
                    <dd>{formatDate(details.data.last_crawled_time)}</dd>
                  </div>
                  <div>
                    <dt>Хранилище</dt>
                    <dd>{details.data.s3_link ?? "—"}</dd>
                  </div>
                </dl>
              )}
            </div>
            <footer className="dialog-footer">
              <button
                className="text-button danger-text"
                type="button"
                disabled={deleting}
                onClick={() => onDelete(details.data.url)}
              >
                {deleting ? "Удаляем…" : "Удалить страницу"}
              </button>
            </footer>
          </>
        )}
      </div>
    </dialog>
  );
}
