import { listCustomersRoute } from "./customers.js";

export function listCustomersRoutePathTest() {
  if (listCustomersRoute().path !== "/customers") {
    throw new Error("unexpected customer list path");
  }
}
