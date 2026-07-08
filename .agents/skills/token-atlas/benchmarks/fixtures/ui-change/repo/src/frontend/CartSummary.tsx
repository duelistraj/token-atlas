export interface CartSummaryProps {
  itemCount: number;
  totalCents: number;
}

export function renderCartSummary(props: CartSummaryProps): string {
  const formattedTotal = `$${(props.totalCents / 100).toFixed(2)}`;

  return [
    `<section aria-label="Cart summary">`,
    `<p>${props.itemCount} items</p>`,
    `<strong>${formattedTotal}</strong>`,
    `</section>`
  ].join("");
}
