import axios, { AxiosInstance } from 'axios';
import type {
  Lead,
  LeadListResponse,
  Listing,
  ListingListResponse,
  CreateListingInput,
  ContentDraft,
  AgentAction,
  AgentActionListResponse,
  AgentStatusResponse,
  CompanyProfile,
  BusinessRules,
  DashboardStats,
  ContentPost,
  Integration,
} from './types';

// ─── Axios Instance ──────────────────────────────────────────────────────────

const axiosInstance: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Token getter — injected at runtime by Clerk auth
let getTokenFn: (() => Promise<string | null>) | null = null;

export function setTokenGetter(fn: () => Promise<string | null>) {
  getTokenFn = fn;
}

axiosInstance.interceptors.request.use(async (config) => {
  if (getTokenFn) {
    const token = await getTokenFn();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Let Clerk handle re-auth
      console.warn('[API] Unauthorized — Clerk will redirect to sign-in');
    }
    return Promise.reject(error);
  }
);

// ─── API Object ──────────────────────────────────────────────────────────────

export const api = {
  // ── Dashboard ──────────────────────────────────────────────────────────────
  dashboard: {
    async getStats(): Promise<DashboardStats> {
      const res = await axiosInstance.get<DashboardStats>('/api/dashboard/stats');
      return res.data;
    },
    async getOverdueLeads(): Promise<Lead[]> {
      const res = await axiosInstance.get<Lead[]>('/api/dashboard/overdue-leads');
      return res.data;
    },
  },

  // ── Leads ──────────────────────────────────────────────────────────────────
  leads: {
    async list(params: { status?: string; search?: string; page?: number }): Promise<LeadListResponse> {
      const res = await axiosInstance.get<LeadListResponse>('/api/leads', { params });
      return res.data;
    },
    async get(id: string): Promise<Lead> {
      const res = await axiosInstance.get<Lead>(`/api/leads/${id}`);
      return res.data;
    },
    async update(id: string, data: Partial<Lead>): Promise<Lead> {
      const res = await axiosInstance.patch<Lead>(`/api/leads/${id}`, data);
      return res.data;
    },
    async escalate(id: string): Promise<void> {
      await axiosInstance.post(`/api/leads/${id}/escalate`);
    },
    async sendMessage(id: string, channel: 'whatsapp' | 'email', message: string): Promise<void> {
      await axiosInstance.post(`/api/leads/${id}/message`, { channel, message });
    },
    async scheduleViewing(id: string, datetime: string): Promise<void> {
      await axiosInstance.post(`/api/leads/${id}/schedule-viewing`, { datetime });
    },
    async exportCsv(): Promise<Blob> {
      const res = await axiosInstance.get('/api/leads/export', {
        responseType: 'blob',
      });
      return res.data;
    },
  },

  // ── Listings ───────────────────────────────────────────────────────────────
  listings: {
    async list(params: { status?: string; search?: string }): Promise<ListingListResponse> {
      const res = await axiosInstance.get<ListingListResponse>('/api/listings', { params });
      return res.data;
    },
    async get(id: string): Promise<Listing> {
      const res = await axiosInstance.get<Listing>(`/api/listings/${id}`);
      return res.data;
    },
    async create(data: CreateListingInput): Promise<Listing> {
      const res = await axiosInstance.post<Listing>('/api/listings', data);
      return res.data;
    },
    async update(id: string, data: Partial<CreateListingInput>): Promise<Listing> {
      const res = await axiosInstance.patch<Listing>(`/api/listings/${id}`, data);
      return res.data;
    },
    async delete(id: string): Promise<void> {
      await axiosInstance.delete(`/api/listings/${id}`);
    },
    async markSold(id: string): Promise<Listing> {
      const res = await axiosInstance.post<Listing>(`/api/listings/${id}/mark-sold`);
      return res.data;
    },
    async uploadFiles(
      id: string,
      files: File[],
      type: 'photos' | 'floor_plans' | 'brochure'
    ): Promise<string[]> {
      const formData = new FormData();
      files.forEach((f) => formData.append('files', f));
      formData.append('type', type);
      const res = await axiosInstance.post<{ urls: string[] }>(
        `/api/listings/${id}/media`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      return res.data.urls;
    },
  },

  // ── Approvals ─────────────────────────────────────────────────────────────
  approvals: {
    async list(): Promise<ContentDraft[]> {
      const res = await axiosInstance.get<ContentDraft[]>('/api/approvals');
      return res.data;
    },
    async approve(id: string): Promise<void> {
      await axiosInstance.post(`/api/approvals/${id}/approve`);
    },
    async reject(id: string, notes: string): Promise<void> {
      await axiosInstance.post(`/api/approvals/${id}/reject`, { notes });
    },
    async requestChanges(id: string, notes: string): Promise<void> {
      await axiosInstance.post(`/api/approvals/${id}/request-changes`, { notes });
    },
  },

  // ── Agents ────────────────────────────────────────────────────────────────
  agents: {
    async getStatus(): Promise<AgentStatusResponse> {
      const res = await axiosInstance.get<AgentStatusResponse>('/api/agents/status');
      return res.data;
    },
    async getActions(params: { page?: number; limit?: number }): Promise<AgentActionListResponse> {
      const res = await axiosInstance.get<AgentActionListResponse>('/api/agents/actions', {
        params,
      });
      return res.data;
    },
    async triggerMarketing(): Promise<void> {
      await axiosInstance.post('/api/agents/trigger/marketing');
    },
    async triggerBriefing(): Promise<void> {
      await axiosInstance.post('/api/agents/trigger/briefing');
    },
  },

  // ── Settings ──────────────────────────────────────────────────────────────
  settings: {
    async getCompanyProfile(): Promise<CompanyProfile> {
      const res = await axiosInstance.get<CompanyProfile>('/api/settings/company');
      return res.data;
    },
    async saveCompanyProfile(data: CompanyProfile): Promise<void> {
      await axiosInstance.put('/api/settings/company', data);
    },
    async getBusinessRules(): Promise<BusinessRules> {
      const res = await axiosInstance.get<BusinessRules>('/api/settings/business-rules');
      return res.data;
    },
    async saveBusinessRules(data: BusinessRules): Promise<void> {
      await axiosInstance.put('/api/settings/business-rules', data);
    },
    async getIntegrations(): Promise<Integration[]> {
      const res = await axiosInstance.get<Integration[]>('/api/settings/integrations');
      return res.data;
    },
    async uploadLogo(file: File): Promise<string> {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axiosInstance.post<{ url: string }>('/api/settings/logo', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data.url;
    },
  },

  // ── Content Calendar ──────────────────────────────────────────────────────
  content: {
    async getCalendar(params: { start: string; end: string }): Promise<ContentPost[]> {
      const res = await axiosInstance.get<ContentPost[]>('/api/content/calendar', { params });
      return res.data;
    },
    async getPublished(): Promise<ContentPost[]> {
      const res = await axiosInstance.get<ContentPost[]>('/api/content/published');
      return res.data;
    },
    async generateWeek(): Promise<void> {
      await axiosInstance.post('/api/content/generate-week');
    },
  },
};

export default axiosInstance;
