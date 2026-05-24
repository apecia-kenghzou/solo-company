'use client';

import * as React from 'react';
import { CheckSquare, Filter } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Modal } from '@/components/ui/modal';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { formatRelativeTime } from '@/lib/utils';
import type { ContentDraft, ContentType } from '@/lib/types';

// ─── Type icons ───────────────────────────────────────────────────────────

const typeIcons: Record<ContentType, string> = {
  email: '📧',
  instagram: '📸',
  whatsapp: '💬',
  facebook: '👥',
  tiktok: '🎵',
};

const typeLabels: Record<ContentType, string> = {
  email: 'Email',
  instagram: 'Instagram',
  whatsapp: 'WhatsApp',
  facebook: 'Facebook',
  tiktok: 'TikTok',
};

const typeBadgeVariant: Record<ContentType, 'default' | 'success' | 'warning' | 'destructive' | 'outline'> = {
  email: 'default',
  instagram: 'warning',
  whatsapp: 'success',
  facebook: 'default',
  tiktok: 'destructive',
};

// ─── Filter options ────────────────────────────────────────────────────────

const filterOptions: { value: string; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'email', label: 'Email' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'tiktok', label: 'TikTok' },
];

// ─── Page ─────────────────────────────────────────────────────────────────

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [changesTarget, setChangesTarget] = React.useState<ContentDraft | null>(null);
  const [changesNotes, setChangesNotes] = React.useState('');

  const { data: drafts = [], isLoading } = useQuery({
    queryKey: ['approvals'],
    queryFn: () => api.approvals.list(),
    refetchInterval: 30_000,
  });

  const pendingDrafts = drafts
    .filter((d) => d.status === 'pending')
    .filter((d) => typeFilter === 'all' || d.type === typeFilter)
    .sort((a, b) => new Date(a.generated_at).getTime() - new Date(b.generated_at).getTime());

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
    onSuccess: () => toast.success('Content approved and scheduled'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['approvals'] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => api.approvals.reject(id, 'Rejected'),
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

  const changesMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) =>
      api.approvals.requestChanges(id, notes),
    onSuccess: () => {
      toast.success('Changes requested — agent will regenerate');
      setChangesTarget(null);
      setChangesNotes('');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
    onError: () => toast.error('Failed to request changes'),
  });

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[var(--foreground)]">Approval Queue</h1>
          <p className="text-sm text-[var(--muted)] mt-0.5">
            {pendingDrafts.length} item{pendingDrafts.length !== 1 ? 's' : ''} waiting for your review
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[var(--muted)]" />
          <div className="flex items-center gap-1 bg-[var(--muted-bg)] p-1 rounded-lg">
            {filterOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setTypeFilter(opt.value)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  typeFilter === opt.value
                    ? 'bg-white text-[var(--foreground)] shadow-sm'
                    : 'text-[var(--muted)] hover:text-[var(--foreground)]'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white rounded-2xl border border-[var(--border)] p-5 animate-pulse">
              <div className="h-4 bg-[var(--muted-bg)] rounded w-1/4 mb-3" />
              <div className="h-3 bg-[var(--muted-bg)] rounded w-full mb-2" />
              <div className="h-3 bg-[var(--muted-bg)] rounded w-3/4" />
            </div>
          ))}
        </div>
      ) : pendingDrafts.length === 0 ? (
        <div className="text-center py-20 text-[var(--muted)]">
          <CheckSquare className="w-12 h-12 mx-auto mb-3 opacity-25" />
          <p className="font-medium text-[var(--foreground)]">All caught up!</p>
          <p className="text-sm mt-1">No content waiting for approval</p>
        </div>
      ) : (
        <div className="space-y-4">
          {pendingDrafts.map((draft) => (
            <ApprovalCard
              key={draft.id}
              draft={draft}
              onApprove={() => approveMutation.mutate(draft.id)}
              onReject={() => rejectMutation.mutate(draft.id)}
              onRequestChanges={() => {
                setChangesTarget(draft);
                setChangesNotes('');
              }}
              approving={approveMutation.isPending}
              rejecting={rejectMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Request Changes Modal */}
      <Modal
        open={!!changesTarget}
        onOpenChange={(open) => !open && setChangesTarget(null)}
        title="Request Changes"
        description="Describe what needs to be changed. The AI agent will regenerate the content."
        footer={
          <>
            <Button variant="outline" onClick={() => setChangesTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                changesTarget && changesMutation.mutate({ id: changesTarget.id, notes: changesNotes })
              }
              loading={changesMutation.isPending}
              disabled={!changesNotes.trim()}
            >
              Request Changes
            </Button>
          </>
        }
      >
        <Textarea
          value={changesNotes}
          onChange={(e) => setChangesNotes(e.target.value)}
          placeholder="e.g. Make the tone more formal, include the price range, add a call-to-action..."
          className="min-h-[120px]"
        />
      </Modal>
    </div>
  );
}

// ─── Approval Card ────────────────────────────────────────────────────────

interface ApprovalCardProps {
  draft: ContentDraft;
  onApprove: () => void;
  onReject: () => void;
  onRequestChanges: () => void;
  approving: boolean;
  rejecting: boolean;
}

function ApprovalCard({
  draft,
  onApprove,
  onReject,
  onRequestChanges,
  approving,
  rejecting,
}: ApprovalCardProps) {
  const [expanded, setExpanded] = React.useState(false);

  return (
    <div className="bg-white rounded-2xl border border-[var(--border)] shadow-card overflow-hidden">
      {/* Header */}
      <div className="flex items-start gap-4 p-5 pb-4">
        <span className="text-2xl flex-shrink-0 mt-0.5">{typeIcons[draft.type]}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <Badge variant={typeBadgeVariant[draft.type]}>{typeLabels[draft.type]}</Badge>
            {draft.listing_name && (
              <span className="text-xs text-[var(--muted)]">for {draft.listing_name}</span>
            )}
            <span className="text-xs text-[var(--muted)] ml-auto">
              by {draft.agent_name} · {formatRelativeTime(draft.generated_at)}
            </span>
          </div>
          {draft.subject && (
            <p className="text-sm font-medium text-[var(--foreground)] truncate">{draft.subject}</p>
          )}
        </div>
      </div>

      {/* Content preview */}
      <div className="px-5 pb-4">
        {draft.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={draft.image_url}
            alt="Content preview"
            className="w-full max-h-48 object-cover rounded-xl mb-3"
          />
        )}
        <div
          className={`text-sm text-[var(--foreground)] leading-relaxed ${!expanded ? 'line-clamp-4' : ''}`}
          style={{ whiteSpace: 'pre-line' }}
        >
          {draft.body}
        </div>
        {draft.body.length > 300 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-primary-500 mt-1 hover:underline"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
        {draft.scheduled_for && (
          <p className="text-xs text-[var(--muted)] mt-2">
            Scheduled for: {new Date(draft.scheduled_for).toLocaleString()}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-5 py-4 bg-[var(--muted-bg)]/50 border-t border-[var(--border)]">
        <Button
          size="sm"
          variant="success"
          onClick={onApprove}
          loading={approving}
          className="gap-1.5"
        >
          ✓ Approve
        </Button>
        <Button
          size="sm"
          onClick={onRequestChanges}
          className="bg-amber-500 hover:bg-amber-600 text-white gap-1.5"
        >
          ✏ Request Changes
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={onReject}
          loading={rejecting}
          className="gap-1.5"
        >
          ✕ Reject
        </Button>
      </div>
    </div>
  );
}
