'use client';

import * as React from 'react';
import { useUser } from '@clerk/nextjs';
import { format } from 'date-fns';
import {
  Users,
  CheckSquare,
  Building2,
  Flame,
  RefreshCw,
  Eye,
  Send,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { StatsCard } from '@/components/stats-card';
import { AgentActivityFeed } from '@/components/agent-activity-feed';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/components/ui/toast';
import { cn, formatRelativeTime, formatCurrency } from '@/lib/utils';
import { LeadDetailPanel } from '@/components/lead-detail-panel';
import type { Lead, LeadStatus, ContentDraft, ContentType } from '@/lib/types';

// ─── Helpers ──────────────────────────────────────────────────────────────

const statusVariant: Record<LeadStatus, 'default' | 'success' | 'warning' | 'destructive' | 'outline'> = {
  new: 'default',
  warm: 'warning',
  hot: 'destructive',
  viewing_scheduled: 'success',
  offer: 'success',
  closed: 'outline',
  lost: 'outline',
};

const contentTypeIcons: Record<ContentType, string> = {
  email: '📧',
  instagram: '📸',
  whatsapp: '💬',
  facebook: '👥',
  tiktok: '🎵',
};

function getGreeting(hour: number): string {
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

// ─── Page ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useUser();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedLead, setSelectedLead] = React.useState<Lead | null>(null);

  const now = new Date();
  const greeting = getGreeting(now.getHours());
  const dateString = format(now, 'EEEE, MMMM d, yyyy');

  // ── Data fetching ──

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.dashboard.getStats(),
    refetchInterval: 60_000,
  });

  const { data: overdueLeads = [] } = useQuery({
    queryKey: ['overdue-leads'],
    queryFn: () => api.dashboard.getOverdueLeads(),
    refetchInterval: 60_000,
  });

  const { data: pendingApprovals = [], isLoading: approvalsLoading } = useQuery({
    queryKey: ['approvals'],
    queryFn: () => api.approvals.list(),
    refetchInterval: 30_000,
    select: (data) => data.filter((d) => d.status === 'pending').slice(0, 5),
  });

  // ── Mutations ──

  const approveMutation = useMutation({
    mutationFn: (id: string) => api.approvals.approve(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['approvals'] });
      const prev = queryClient.getQueryData<ContentDraft[]>(['approvals']);
      queryClient.setQueryData<ContentDraft[]>(['approvals'], (old) =>
        old?.map((d) => (d.id === id ? { ...d, status: 'approved' as const } : d))
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      queryClient.setQueryData(['approvals'], ctx?.prev);
      toast.error('Failed to approve');
    },
    onSuccess: () => toast.success('Content approved'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['approvals'] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => api.approvals.reject(id, 'Rejected from dashboard'),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['approvals'] });
      const prev = queryClient.getQueryData<ContentDraft[]>(['approvals']);
      queryClient.setQueryData<ContentDraft[]>(['approvals'], (old) =>
        old?.map((d) => (d.id === id ? { ...d, status: 'rejected' as const } : d))
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      queryClient.setQueryData(['approvals'], ctx?.prev);
      toast.error('Failed to reject');
    },
    onSuccess: () => toast.success('Content rejected'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['approvals'] }),
  });

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* ── Morning briefing card ── */}
      <div className="rounded-2xl bg-gradient-to-br from-primary-500 to-primary-600 text-white p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-primary-200 text-sm font-medium mb-1">{dateString}</p>
            <h1 className="text-2xl font-bold">
              {greeting}, {user?.firstName || 'there'} 👋
            </h1>
            <p className="text-primary-200 text-sm mt-1.5">
              Your agents are working. Here's what needs your attention today.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="border-white/30 text-white hover:bg-white/10 hover:text-white flex-shrink-0"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
              queryClient.invalidateQueries({ queryKey: ['overdue-leads'] });
              queryClient.invalidateQueries({ queryKey: ['approvals'] });
            }}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Stats row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="New Leads Today"
          value={stats?.new_leads_today ?? 0}
          trend={stats?.new_leads_trend}
          icon={<Users className="w-5 h-5" />}
          loading={statsLoading}
        />
        <StatsCard
          title="Pending Approvals"
          value={stats?.pending_approvals ?? 0}
          icon={<CheckSquare className="w-5 h-5" />}
          loading={statsLoading}
        />
        <StatsCard
          title="Active Listings"
          value={stats?.active_listings ?? 0}
          icon={<Building2 className="w-5 h-5" />}
          loading={statsLoading}
        />
        <StatsCard
          title="Hot Leads"
          value={stats?.hot_leads ?? 0}
          trend={stats?.hot_leads_trend}
          icon={<Flame className="w-5 h-5" />}
          loading={statsLoading}
        />
      </div>

      {/* ── Main content 2-column ── */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Agent Activity Feed */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Agent Activity
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse-dot" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <AgentActivityFeed />
          </CardContent>
        </Card>

        {/* Pending Approvals quick-action */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Pending Approvals</CardTitle>
              <a href="/approvals" className="text-xs text-primary-500 hover:underline">
                View all
              </a>
            </div>
          </CardHeader>
          <CardContent>
            {approvalsLoading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-16 rounded-lg bg-[var(--muted-bg)] animate-pulse" />
                ))}
              </div>
            ) : pendingApprovals.length === 0 ? (
              <div className="text-center py-8 text-[var(--muted)]">
                <CheckSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No pending approvals</p>
              </div>
            ) : (
              <div className="space-y-2">
                {pendingApprovals.map((draft) => (
                  <div
                    key={draft.id}
                    className="flex items-center gap-3 p-3 rounded-xl border border-[var(--border)] hover:bg-[var(--muted-bg)] transition-colors"
                  >
                    <span className="text-xl flex-shrink-0" aria-label={draft.type}>
                      {contentTypeIcons[draft.type]}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--foreground)] truncate">
                        {draft.subject || draft.listing_name || draft.agent_name}
                      </p>
                      <p className="text-xs text-[var(--muted)] truncate mt-0.5">
                        {draft.body.slice(0, 80)}...
                      </p>
                    </div>
                    <div className="flex gap-1.5 flex-shrink-0">
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => approveMutation.mutate(draft.id)}
                        loading={approveMutation.isPending}
                        disabled={draft.status !== 'pending'}
                        className="h-7 px-2.5 text-xs"
                      >
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => rejectMutation.mutate(draft.id)}
                        loading={rejectMutation.isPending}
                        disabled={draft.status !== 'pending'}
                        className="h-7 px-2.5 text-xs text-red-600 border-red-200 hover:bg-red-50"
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Leads needing attention ── */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Leads Needing Attention</CardTitle>
            <a href="/leads" className="text-xs text-primary-500 hover:underline">
              View all leads
            </a>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {overdueLeads.length === 0 ? (
            <div className="text-center py-10 text-[var(--muted)]">
              <Users className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No leads need attention right now</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    <th className="text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wide px-6 py-3">
                      Name
                    </th>
                    <th className="text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wide px-3 py-3 hidden md:table-cell">
                      Property Interest
                    </th>
                    <th className="text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wide px-3 py-3 hidden lg:table-cell">
                      Last Contact
                    </th>
                    <th className="text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wide px-3 py-3">
                      Status
                    </th>
                    <th className="text-right text-xs font-medium text-[var(--muted)] uppercase tracking-wide px-6 py-3">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {overdueLeads.map((lead) => (
                    <tr
                      key={lead.id}
                      className="hover:bg-[var(--muted-bg)] transition-colors cursor-pointer"
                      onClick={() => setSelectedLead(lead)}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-primary-100 text-primary-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                            {lead.full_name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-medium text-[var(--foreground)]">{lead.full_name}</p>
                            <p className="text-xs text-[var(--muted)]">{lead.email || lead.phone || '—'}</p>
                          </div>
                          {lead.temperature === 'hot' && (
                            <span title="Hot lead" className="text-base">🔥</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-4 hidden md:table-cell text-[var(--muted)]">
                        {lead.property_interest || '—'}
                      </td>
                      <td className="px-3 py-4 hidden lg:table-cell text-[var(--muted)]">
                        {formatRelativeTime(lead.last_contact_at)}
                      </td>
                      <td className="px-3 py-4">
                        <Badge variant={statusVariant[lead.status]}>
                          {lead.status.replace(/_/g, ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2.5 text-xs gap-1"
                            onClick={() => setSelectedLead(lead)}
                          >
                            <Eye className="w-3 h-3" />
                            View
                          </Button>
                          <Button
                            size="sm"
                            variant="default"
                            className="h-7 px-2.5 text-xs gap-1"
                            onClick={() => {
                              // Would open send follow-up modal in full implementation
                              toast.info('Send follow-up — opening lead detail');
                              setSelectedLead(lead);
                            }}
                          >
                            <Send className="w-3 h-3" />
                            Follow-up
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Lead detail slide-over */}
      {selectedLead && (
        <LeadDetailPanel lead={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  );
}
