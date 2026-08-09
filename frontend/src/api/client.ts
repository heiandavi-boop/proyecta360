import { API_ENDPOINTS } from "@contracts/endpoints";
import type { ApiOperationMap } from "@contracts/types";

const AUTH_TOKEN_KEY = "proyecta360_token";

type EndpointName = keyof ApiOperationMap;
type RequestOf<T extends EndpointName> = ApiOperationMap[T]["request"];
type ResponseOf<T extends EndpointName> = ApiOperationMap[T]["response"];

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  token: string;
  user: PublicUser;
};

export type PublicUser = {
  id: number;
  name: string;
  email: string;
  role: string;
  organization_id?: number;
};

type ApiOptions<T extends EndpointName> = {
  body?: RequestOf<T>;
  params?: Record<string, string | number>;
  query?: Record<string, string | number | undefined>;
  headers?: Record<string, string>;
};

function token(): string {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

export function saveToken(value: string): void {
  localStorage.setItem(AUTH_TOKEN_KEY, value);
}

export function clearToken(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function hasToken(): boolean {
  return Boolean(token());
}

function pathWithParams(path: string, params: Record<string, string | number> = {}): string {
  return Object.entries(params).reduce(
    (result, [key, value]) => result.replace(`{${key}}`, encodeURIComponent(String(value))),
    path
  );
}

function pathWithQuery(path: string, query: Record<string, string | number | undefined> = {}): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  const suffix = params.toString();
  return suffix ? `${path}?${suffix}` : path;
}

function formatApiError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const payload = detail as { message?: unknown; errors?: Array<{ row?: number; field?: string; message?: string }> };
    if (Array.isArray(payload.errors) && payload.errors.length) {
      const prefix = typeof payload.message === "string" ? payload.message : "La solicitud contiene errores";
      const lines = payload.errors.slice(0, 6).map((error) => {
        const row = error.row ? `Fila ${error.row}` : "Fila";
        const field = error.field ? `, ${error.field}` : "";
        return `${row}${field}: ${error.message || "Dato invalido"}`;
      });
      const suffix = payload.errors.length > lines.length ? ` (${payload.errors.length - lines.length} mas)` : "";
      return `${prefix}. ${lines.join(" | ")}${suffix}`;
    }
    if (typeof payload.message === "string") return payload.message;
  }
  return "Request failed";
}

export async function apiRequest<T extends EndpointName>(
  endpoint: T,
  options: ApiOptions<T> = {}
): Promise<ResponseOf<T>> {
  const definition = API_ENDPOINTS[endpoint];
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    "X-Locale": localStorage.getItem("proyecta360_language") || "es",
    ...options.headers
  };
  if (!isFormData) headers["Content-Type"] = "application/json";
  const authToken = token();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  const path = pathWithQuery(pathWithParams(definition.path, options.params), options.query);
  const response = await fetch(path, {
    method: definition.method,
    headers,
    body: options.body === undefined ? undefined : isFormData ? options.body as FormData : JSON.stringify(options.body)
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(formatApiError(detail.detail));
  }
  return response.json();
}

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(API_ENDPOINTS.login_api_auth_login_post.path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Locale": localStorage.getItem("proyecta360_language") || "es"
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(formatApiError(detail.detail || "Login failed"));
  }
  return response.json();
}

export async function logout(): Promise<void> {
  await apiRequest("logout_api_auth_logout_post");
  clearToken();
}
