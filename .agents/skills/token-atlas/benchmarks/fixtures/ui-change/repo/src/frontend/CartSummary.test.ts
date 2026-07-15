import { renderCartSummary } from "./CartSummary.js";

export function cartSummaryLabel(): boolean {
  return renderCartSummary({ itemCount: 1, totalCents: 1200 }).includes("Cart summary");
}
