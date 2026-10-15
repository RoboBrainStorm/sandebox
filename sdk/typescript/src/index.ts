export interface ExecutionResult {
  exit_code: number;
  stdout: string;
  stderr: string;
}

export interface SandboxResponse {
  id: string;
  workspace_id: string;
  user_id: string;
  pod_name: string;
  status: string;
}

export interface BuildResponse {
  id: string;
  target_name: string;
  image_tag: string;
  status: string;
}

export interface DeploymentResponse {
  name: string;
  namespace: string;
  url: string;
  status: string;
}

export interface AdminStatsResponse {
  active_sandboxes: number;
  uptime_seconds: number;
  namespace: string;
  runtime_class: string;
  image: string;
}

export interface CreateSandboxOptions {
  workspace_id?: string;
  user_id?: string;
  session_id?: string;
  image?: string;
  cpu_limit?: string;
  memory_limit?: string;
}

export interface BuildImageOptions {
  repo_path: string;
  target_name: string;
  is_agent?: boolean;
  prefix?: string;
}

export interface DeployServiceOptions {
  name: string;
  image: string;
  env?: Record<string, string>;
  command?: string[];
  namespace?: string;
  min_scale?: number;
  max_scale?: number;
}

export class SandboxError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "SandboxError";
  }
}

export class SandboxSessionClient {
  constructor(
    public readonly sessionId: string,
    private readonly baseUrl: string,
    private readonly apiKey: string
  ) {}

  async exec(command: string, env?: Record<string, string>): Promise<ExecutionResult> {
    const res = await fetch(`${this.baseUrl}/v1/sandboxes/${this.sessionId}/exec`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
      },
      body: JSON.stringify({ command, env }),
    });

    if (!res.ok) {
      throw new SandboxError(`Exec failed: ${res.statusText}`, res.status);
    }
    return (await res.json()) as ExecutionResult;
  }

  async stop(): Promise<{ id: string; stopped: boolean }> {
    const res = await fetch(`${this.baseUrl}/v1/sandboxes/${this.sessionId}`, {
      method: "DELETE",
      headers: {
        "X-API-Key": this.apiKey,
      },
    });

    if (!res.ok && res.status !== 404) {
      throw new SandboxError(`Stop failed: ${res.statusText}`, res.status);
    }
    return (await res.json()) as { id: string; stopped: boolean };
  }
}

export interface SandboxClientOptions {
  baseUrl?: string;
  apiKey?: string;
}

export class SandboxClient {
  public readonly baseUrl: string;
  public readonly apiKey: string;

  constructor(options: SandboxClientOptions = {}) {
    this.baseUrl = (options.baseUrl || "http://localhost:8000").replace(/\/$/, "");
    this.apiKey = options.apiKey || "sk-sandebox-dev-key";
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = {
      "Content-Type": "application/json",
      "X-API-Key": this.apiKey,
      ...(init?.headers || {}),
    };

    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });

    if (!res.ok) {
      const errorText = await res.text().catch(() => "");
      throw new SandboxError(`Request to ${path} failed (${res.status}): ${errorText}`, res.status);
    }

    return (await res.json()) as T;
  }

  async createSandbox(options: CreateSandboxOptions = {}): Promise<SandboxSessionClient> {
    const data = await this.request<SandboxResponse>("/v1/sandboxes", {
      method: "POST",
      body: JSON.stringify(options),
    });
    return new SandboxSessionClient(data.id, this.baseUrl, this.apiKey);
  }

  async listSandboxes(): Promise<SandboxResponse[]> {
    return this.request<SandboxResponse[]>("/v1/sandboxes");
  }

  async getSandbox(sessionId: string): Promise<SandboxResponse> {
    return this.request<SandboxResponse>(`/v1/sandboxes/${sessionId}`);
  }

  async stopSandbox(sessionId: string): Promise<{ id: string; stopped: boolean }> {
    return this.request<{ id: string; stopped: boolean }>(`/v1/sandboxes/${sessionId}`, {
      method: "DELETE",
    });
  }

  async runCommand(command: string): Promise<ExecutionResult> {
    return this.request<ExecutionResult>("/v1/sandboxes/run", {
      method: "POST",
      body: JSON.stringify({ command, language: "bash" }),
    });
  }

  async runPython(code: string): Promise<ExecutionResult> {
    return this.request<ExecutionResult>("/v1/sandboxes/run", {
      method: "POST",
      body: JSON.stringify({ code, language: "python" }),
    });
  }

  async buildImage(options: BuildImageOptions): Promise<BuildResponse> {
    return this.request<BuildResponse>("/v1/builds", {
      method: "POST",
      body: JSON.stringify(options),
    });
  }

  async deployService(options: DeployServiceOptions): Promise<DeploymentResponse> {
    return this.request<DeploymentResponse>("/v1/deployments", {
      method: "POST",
      body: JSON.stringify(options),
    });
  }

  async getDeployment(name: string, namespace?: string): Promise<DeploymentResponse> {
    const query = namespace ? `?namespace=${encodeURIComponent(namespace)}` : "";
    return this.request<DeploymentResponse>(`/v1/deployments/${name}${query}`);
  }

  async deleteDeployment(name: string, namespace?: string): Promise<{ name: string; deleted: boolean }> {
    const query = namespace ? `?namespace=${encodeURIComponent(namespace)}` : "";
    return this.request<{ name: string; deleted: boolean }>(`/v1/deployments/${name}${query}`, {
      method: "DELETE",
    });
  }

  async getStats(): Promise<AdminStatsResponse> {
    return this.request<AdminStatsResponse>("/v1/admin/stats");
  }
}
