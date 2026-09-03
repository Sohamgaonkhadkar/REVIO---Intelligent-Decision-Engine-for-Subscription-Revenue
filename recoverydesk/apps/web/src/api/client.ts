import type { paths } from "./schema";

type Path = keyof paths;
type Method = "get" | "post";
type Op<P extends Path, M extends Method> = paths[P][M];
type ResBody<O> = O extends { responses: { 200: { content: { "application/json": infer R } } } } ? R
  : O extends { responses: { 201: { content: { "application/json": infer R } } } } ? R : never;

/** Typed fetch client — every call goes through the LIVE API (same origin). */
export async function api<P extends Path & string, M extends Method = "get">(
  path: P,
  init?: { method?: M; json?: unknown; headers?: Record<string, string> },
): Promise<ResBody<Op<P, M>>> {
  const res = await fetch(path, {
    method: init?.method ?? "get",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    body: init?.json !== undefined ? JSON.stringify(init.json) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* keep status */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<ResBody<Op<P, M>>>;
}

export const OPS_KEY = "rd-ops-key"; // ops console only; read endpoints need no key
