import type { CatalogItem } from "../models/catalogItem.js";

const items: CatalogItem[] = [
  { id: "sku-ring-01", name: "Silver Ring", priceCents: 3200, active: true }
];

export function listCatalogItems() {
  return {
    status: 200,
    body: items.filter((item) => item.active)
  };
}
