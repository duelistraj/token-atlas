import type { CustomerRecord } from "../models/customer.js";

const customers: CustomerRecord[] = [
  { id: "cus_1001", email: "ada@example.test", marketingOptIn: true }
];

export function listCustomersRoute() {
  return { status: 200, body: customers };
}
