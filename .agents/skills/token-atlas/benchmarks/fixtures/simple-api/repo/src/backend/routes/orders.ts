export interface OrderSummary {
  id: string;
  status: "open" | "paid";
  totalCents: number;
}

const orders: OrderSummary[] = [
  { id: "ord_1001", status: "open", totalCents: 4800 }
];

export function getOrderRoute(orderId: string) {
  const order = orders.find((item) => item.id === orderId);

  if (!order) {
    return { status: 404, body: { error: "Order not found" } };
  }

  return { status: 200, body: order };
}
