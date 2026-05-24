'use client';

import * as React from 'react';
import { Search, Download, Users, Flame, Calendar, DollarSign, Eye } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import { LeadDetailPanel } from '@/components/lead-detail-panel';
import { cn, formatRelativeTime, formatCurrency, downloadBlob } from '@/lib/utils';
import type { Lead, LeadStatus } from '@/lib/types';

// ─── Helpers ──────────────────────────────────────────────────────────────

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'new', label: 'New' },
  { value: 'warm', label: 'Warm' },
  { value: 'hot', label: 'Hot' },
  { value: 'viewing_scheduled', label: 'Viewing Scheduled' },
  { value: 'offer', label: 'Offer' },
  { value: 'closed', label: 'Closed' },
  { value: 'lost', label: 'Lost' },
];

const statusVariant: Record<LeadStatus, 'default' | 'success' | 'warning' | 'destructive' | 'outline'> = {
  new: 'default',
  warm: 'warning',
  hot: 'destructive',
  viewing_scheduled: 'success',
  offer: 'success',
  closed: 'outline',
  lost: 'outline',
};

const statusColors: Record<LeadStatus, string> = {
  new: 'bg-blue-500',
  warm: 'bg-amber-500',
  hot: 'bg-red-500',
  viewing_scheduled: 'bg-green-500',
  offer: 'bg-teal-500',
  closed: 'bg-gray-400',
  lost: 'bg-gray-300',
};

// ─── Page ─────────────────────────────────────────────────────────────────

export default function LeadsPage() {
  const [statusFilter, setStatusFilter] = React.useState('');
  const [searchQuery, setSearchQuery] = React.useState('');
  const [selectedLead, setSelectedLead] = React.useState<Lead | null>(null);
  const [page, setPage] = React.useState(1);
  const [exportLoading, setExportLoading] = React.useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['leads', { status: statusFilter, search: searchQuery, page }],
    queryFn: () =>
      api.leads.list({ status: statusFilter || undefined, search: searchQuery || undefined, page }),
    keepPreviousData: true,
  } as Parameters<typeof useQuery>[0]);

  const leads = data?.items ?? [];
  const total = data?.total ?? 0;

  // Derived stats
  const hotCount = leads.filter((l) => l.temperature === 'hot').length;
  const viewingCount = leads.filter((l) => l.status === 'viewing_scheduled').length;
  const offerCount = leads.filter((l) => l.status === 'offer').length;

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const blob = await api.leads.exportCsv();
      downloadBlob(blob, `leads-${new Date().toISOString().slice(0, 10)}.csv`);
    } catch {
      // handled silently
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[var(--foreground)]">Leads</h1>
          <p className="text-sm text-[var(--muted)] mt-0.5">
            {total} total leads managed by your agents
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleExport}
          loading={exportLoading}
          className="gap-2"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </Button>
      </div>

      {/* Stats chips */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2 bg-white border border-[var(--border)] rounded-xl px-4 py-2.5 shadow-card">
          <Users className="w-4 h-4 text-primary-500" />
          <span className="text-sm font-semibold text-[var(--foreground)]">{total}</span>
          <span className="text-xs text-[var(--muted)]">Total</span>
        </div>
        <div className="flex items-center gap-2 bg-white border border-[var(--border)] rounded-xl px-4 py-2.5 shadow-card">
          <Flame className="w-4 h-4 text-red-500" />
          <span className="text-sm font-semibold text-[var(--foreground)]">{hotCount}</span>
          <span className="text-xs text-[var(--muted)]">Hot</span>
        </div>
        <div className="flex items-center gap-2 bg-white border border-[var(--border)] rounded-xl px-4 py-2.5 shadow-card">
          <Calendar className="w-4 h-4 text-green-500" />
          <span className="text-sm font-semibold text-[var(--foreground)]">{viewingCount}</span>
          <span className="text-xs text-[var(--muted)]">Viewing Scheduled</span>
        </div>
        <div className="flex items-center gap-2 bg-white border border-[var(--border)] rounded-xl px-4 py-2.5 shadow-card">
          <DollarSign className="w-4 h-4 text-teal-500" />
          <span className="text-sm font-semibold text-[var(--foreground)]">{offerCount}</span>
          <span className="text-xs text-[var(--muted)]">Offers</span>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search by name or email..."
            className="w-full h-9 pl-9 pr-3 rounded-lg border border-[var(--border)] bg-white text-sm text-[var(--foreground)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-primary-400"
          />
        </div>
        <div className="w-full sm:w-52">
          <Select
            options={statusOptions}
            value={statusFilter}
            onValueChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            placeholder="Filter by status"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-[var(--border)] shadow-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted-bg)]/50">
                <th className="text-left text-xs font-semibold text-[var(--muted)] uppercase tracking-wide px-6 py-3.5">
                  Name
                </th>
                <th className="text-left text-xs font-semibold text-[var(--muted)] uppercase tracking-wide px-3 py-3.5 hidden md:table-cell">
                  Contact
                </th>
                <th className="text-left text-xs font-semibold text-[var(--muted)] uppercase tracking-wide px-3 py-3.5 hidden lg:table-cell">
                  Property Interest
                </th>
                <th className="text-left text-xs font-semibold text-[var(--muted)] uppercase tracking-wide px-3 py-3.5 hidden xl:table-cell">
                  Budget
                </th>
                <th className="text-left text-xs font-semibold text-[var(--muted)] uppercase tracking-wide px-3 py-3.5">
                  Status
                </th>
                <th className="text-left text-xs font-semibold text-[var(--muted)] uppercase tracking-wide px-3 py-3.5 hidden lg:table-cell">
                  Last Activity
                </th>
                <th className="text-right text-xs font-semibold text-[var(--muted)] uppercase tracking-wide px-6 py-3.5">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {isLoading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(7)].map((__, j) => (
                      <td key={j} className="px-6 py-4">
                        <div className="h-4 bg-[var(--muted-bg)] rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-16 text-[var(--muted)]">
                    <Users className="w-10 h-10 mx-auto mb-3 opacity-25" />
                    <p className="font-medium">No leads found</p>
                    <p className="text-xs mt-1">
                      {searchQuery || statusFilter
                        ? 'Try adjusting your filters'
                        : 'Leads will appear here as your agents capture them'}
                    </p>
                  </td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr
                    key={lead.id}
                    className="hover:bg-[var(--muted-bg)]/50 transition-colors cursor-pointer"
                    onClick={() => setSelectedLead(lead)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            'w-2 h-2 rounded-full flex-shrink-0',
                            statusColors[lead.status]
                          )}
                        />
                        <div>
                          <p className="font-medium text-[var(--foreground)]">{lead.full_name}</p>
                          {lead.source && (
                            <p className="text-xs text-[var(--muted)]">via {lead.source}</p>
                          )}
                        </div>
                        {lead.temperature === 'hot' && (
                          <span title="Hot lead">🔥</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-4 hidden md:table-cell text-[var(--muted)]">
                      <p>{lead.phone || '—'}</p>
                      <p className="text-xs truncate max-w-[140px]">{lead.email || ''}</p>
                    </td>
                    <td className="px-3 py-4 hidden lg:table-cell text-[var(--muted)] max-w-[160px]">
                      <p className="truncate">{lead.property_interest || '—'}</p>
                    </td>
                    <td className="px-3 py-4 hidden xl:table-cell text-[var(--muted)]">
                      {lead.budget_min || lead.budget_max
                        ? `${formatCurrency(lead.budget_min)} – ${formatCurrency(lead.budget_max)}`
                        : '—'}
                    </td>
                    <td className="px-3 py-4">
                      <Badge variant={statusVariant[lead.status]}>
                        {lead.status.replace(/_/g, ' ')}
                      </Badge>
                    </td>
                    <td className="px-3 py-4 hidden lg:table-cell text-[var(--muted)] text-xs">
                      {formatRelativeTime(lead.last_contact_at)}
                    </td>
                    <td
                      className="px-6 py-4 text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2.5 text-xs gap-1"
                        onClick={() => setSelectedLead(lead)}
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 20 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-[var(--border)]">
            <p className="text-sm text-[var(--muted)]">
              Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page * 20 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Lead detail slide-over */}
      {selectedLead && (
        <LeadDetailPanel lead={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  );
}
