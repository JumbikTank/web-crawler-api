const base = process.env.CRAWLER_API_URL || "http://127.0.0.1:8000";

export async function requestApi<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(new URL(path, base), {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      signal: AbortSignal.timeout(35_000),
    });
  } catch {
    throw new Error(
      "Сервер краулера недоступен. Проверьте его адрес и состояние.",
    );
  }

  if (!response.ok) {
    let detail = `Ошибка сервера: HTTP ${response.status}`;
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    if (typeof body?.detail === "string") detail = body.detail;
    throw new Error(detail);
  }

  return (response.status === 204 ? undefined : await response.json()) as T;
}
