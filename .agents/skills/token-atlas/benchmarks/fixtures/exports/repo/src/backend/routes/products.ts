import type { ProductRecord } from "../models/product.js";

const products: ProductRecord[] = [
  { id: "prod_1001", sku: "chain-16", priceCents: 6400 }
];

export function listProductsRoute() {
  return { status: 200, body: products };
}
