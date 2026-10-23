import { useState, type FormEvent } from "react";
import { parseUrls } from "../lib/validation";
import { Notice } from "./Notice";

export function CrawlForm({
  onSubmit,
  pending,
}: {
  onSubmit: (urls: string[]) => void;
  pending: boolean;
}) {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = parseUrls(input);
    setError(result.error);
    if (!result.error) onSubmit(result.urls);
  }

  return (
    <section className="section crawl-section" aria-labelledby="crawl-heading">
      <div className="section-title">
        <h2 id="crawl-heading">Новый обход</h2>
        <span>До 20 URL</span>
      </div>
      <form onSubmit={submit}>
        <label htmlFor="url-input">URL-адреса</label>
        <textarea
          id="url-input"
          rows={4}
          value={input}
          onChange={(event) => {
            setInput(event.target.value);
            setError(null);
          }}
          placeholder={"https://example.com\nhttps://example.org"}
          spellCheck={false}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "url-error" : "url-help"}
        />
        <div className="form-footer">
          <span id="url-help">
            По одному URL на строку. Обходим только указанные страницы.
          </span>
          <button
            className="button button-primary"
            disabled={pending}
            type="submit"
          >
            {pending ? "Сохраняем страницы…" : "Начать обход"}
          </button>
        </div>
        {error && (
          <div id="url-error">
            <Notice kind="error">{error}</Notice>
          </div>
        )}
        {pending && <Notice>Проверяем robots.txt и скачиваем страницы…</Notice>}
      </form>
    </section>
  );
}
