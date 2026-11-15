/** Only public endpoint configuration is read here. No operations credential belongs in a SPA. */
export const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(
  /\/$/,
  "",
);
export const connected =
  import.meta.env.VITE_DATA_MODE === "api" &&
  new URLSearchParams(location.search).get("mode") !== "simulation";
export async function readApi<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error(
      `${path}: expected API JSON; received a page. Check the backend URL.`,
    );
  }
  return response.json() as Promise<T>;
}
