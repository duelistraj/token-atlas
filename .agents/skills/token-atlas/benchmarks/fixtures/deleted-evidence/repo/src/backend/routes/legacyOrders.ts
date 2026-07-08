export function getLegacyOrderRoute(orderId: string) {
  return {
    status: 200,
    body: { id: orderId, source: "legacy" }
  };
}

