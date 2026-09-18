import { v4 as uuidv4 } from "uuid";
import { getToken } from "./storage";

export function authHeaders(): Record<string, string> {
  const token = getToken();

  return {
    Accept: "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "X-Request-ID": uuidv4(),
  };
}

export function apiHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Request-ID": uuidv4(),
  };
}
