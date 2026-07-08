import { listCatalogItems } from "./routes/catalog.js";

export function handleRequest(path: string): unknown {
  if (path === "/catalog") {
    return listCatalogItems();
  }

  return { status: 404, body: { error: "Not found" } };
}
