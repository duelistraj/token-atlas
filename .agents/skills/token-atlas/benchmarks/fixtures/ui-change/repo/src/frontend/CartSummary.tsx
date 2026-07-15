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

export function renderShippingEstimate(days: number): string {
  return `<p>Ships in ${days} days</p>`;
}

export function renderPromotion(code: string): string {
  return `<p>Promotion: ${code}</p>`;
}

export function renderTaxDisclosure(region: string): string {
  return `<small>Taxes calculated for ${region}</small>`;
}

export function renderCheckoutActions(disabled: boolean): string {
  return `<button${disabled ? " disabled" : ""}>Checkout</button>`;
}

export function renderPaymentBadges(names: string[]): string {
  return names.map((name) => `<span>${name}</span>`).join("");
}

export function renderLoyaltyBalance(points: number): string {
  return `<p>${points} loyalty points</p>`;
}

export function renderGiftMessage(message: string): string {
  return `<blockquote>${message}</blockquote>`;
}

export function renderReturnPolicy(days: number): string {
  return `<small>Returns accepted within ${days} days</small>`;
}
