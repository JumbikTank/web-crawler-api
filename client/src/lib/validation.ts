export function parseUrls(value: string): {
  urls: string[];
  error: string | null;
} {
  const entries = value
    .split(/[\n,]/)
    .map((part) => part.trim())
    .filter(Boolean);

  if (entries.length === 0) {
    return { urls: [], error: "Добавьте хотя бы один адрес." };
  }
  if (entries.length > 20) {
    return {
      urls: [],
      error: "За один запуск можно обработать до 20 адресов.",
    };
  }

  for (const entry of entries) {
    if (entry.length > 2048) {
      return { urls: [], error: "Адрес длиннее 2048 символов." };
    }
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
    } catch {
      return { urls: [], error: `Некорректный URL: ${entry}` };
    }
  }

  return { urls: [...new Set(entries)], error: null };
}
