export function getOrderRoute(orderId: string) {
  return {
    status: 200,
    body: { id: orderId, source: "current" }
  };
}
