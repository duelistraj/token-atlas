export function listOrdersRoute() {
  return {
    status: 200,
    body: [{ id: "ord_2001", status: "paid" }]
  };
}
