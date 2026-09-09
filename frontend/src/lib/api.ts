import { AgentRun, AuditLogEntry } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// In-memory access token storage (XSS protected)
let inMemoryAccessToken: string | null = null;
let inMemoryCsrfToken: string | null = null;

function getCsrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const cookie = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith("forge_csrf_token="));
  return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : null;
}

export const setAuthTokens = (accessToken: string | null, csrfToken: string | null) => {
  inMemoryAccessToken = accessToken;
  inMemoryCsrfToken = csrfToken;
};

export const getAccessToken = () => inMemoryAccessToken;
export const getCsrfToken = () => inMemoryCsrfToken;

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  isRetry = false
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const csrfToken = inMemoryCsrfToken || getCsrfCookie();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (inMemoryAccessToken) {
    headers["Authorization"] = `Bearer ${inMemoryAccessToken}`;
  }
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include", // sends httpOnly cookies
  });

  if (response.status === 401 && !isRetry && endpoint !== "/auth/verify" && endpoint !== "/auth/refresh") {
    // Attempt token refresh
    try {
      const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        },
        credentials: "include",
      });

      if (refreshRes.ok) {
        const data = await refreshRes.json();
        setAuthTokens(data.access_token, data.csrf_token);
        // Retry original request with new access token
        return request<T>(endpoint, options, true);
      } else {
        setAuthTokens(null, null);
      }
    } catch {
      setAuthTokens(null, null);
    }
  }

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = { detail: response.statusText };
    }
    throw new ApiError(response.status, errorData.detail || errorData.message || "Request failed", errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Auth
  verifyPassword: (password: string) =>
    request<{ access_token: string; csrf_token: string; expires_in: number }>("/auth/verify", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  refreshToken: () =>
    request<{ access_token: string; csrf_token: string; expires_in: number }>("/auth/refresh", {
      method: "POST",
    }),

  logout: () =>
    request<{ message: string }>("/auth/logout", {
      method: "POST",
    }),

  login: (username_or_email: string, password: string) =>
    request<{ access_token: string; csrf_token: string; expires_in: number; user: any }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username_or_email, password }),
    }),

  register: (username: string, password: string, email?: string) =>
    request<{ access_token: string; csrf_token: string; expires_in: number; user: any }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    }),

  // Agent
  startRun: (repo_url: string, task: string, provider?: string) =>
    request<{ run_id: string; status: string }>("/agent/run", {
      method: "POST",
      body: JSON.stringify({ repo_url, task, provider }),
    }),

  cancelRun: (run_id: string) =>
    request<{ message: string }>(`/agent/cancel/${run_id}`, {
      method: "POST",
    }),

  createPR: (run_id: string, title: string, body: string, branch_name: string, base_branch = "main") =>
    request<{ success: boolean; pr_url?: string; pr_number?: number }>(`/agent/${run_id}/create-pr`, {
      method: "POST",
      body: JSON.stringify({ title, body, branch_name, base_branch }),
    }),

  // History & Audit
  listRuns: (limit = 20, offset = 0) =>
    request<AgentRun[]>(`/runs?limit=${limit}&offset=${offset}`),

  getRun: (run_id: string) =>
    request<AgentRun>(`/runs/${run_id}`),

  getRunAuditLogs: (run_id: string) =>
    request<AuditLogEntry[]>(`/runs/${run_id}/audit-logs`),
};
