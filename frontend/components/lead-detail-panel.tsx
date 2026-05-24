'use client';

import * as React from 'react';
import { X, MessageCircle, Mail, Calendar, ArrowUp, Phone, Send } from 'lucide-react';
import { cn, formatDateTime, formatRelativeTime, formatCurrency } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import type { Lead, LeadStatus, LeadMessage } from '@/lib/types';

// ─── Status badge colour ──────────────────────────────────────────────────

const statusVariant: Record<LeadStatus, 'default' | 'success' | 'warning' | 'destructive' | 'outline'> = {
  new: 'default',
  warm: 'warning',
  hot: 'destructive',
  viewing_scheduled: 'success',
  offer: 'success',
  closed: 'outline',
  lost: 'outline',
};

const statusOptions = [
  { value: 'new', label: 'New' },
  { value: 'warm', label: 'Warm' },
  { value: 'hot', label: 'Hot' },
  { value: 'viewing_scheduled', label: 'Viewing Scheduled' },
  { value: 'offer', label: 'Offer' },
  { value: 'closed', label: 'Closed' },
  { value: 'lost', label: 'Lost' },
];

// ─── Props ────────────────────────────────────────────────────────────────

interface LeadDetailPanelProps {
  lead: Lead;
  onClose: () => void;
}

// ─── Chat Bubble ──────────────────────────────────────────────────────────

function ChatBubble({ message }: { message: LeadMessage }) {
  const isOutbound = message.direction === 'outbound';
  return (
    <div className={cn('flex', isOutbound ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm',
          isOutbound
            ? 'bg-primary-500 text-white rounded-br-sm'
            : 'bg-[var(--muted-bg)] text-[var(--foreground)] rounded-bl-sm'
        )}
      >
        <p className="leading-relaxed">{message.content}</p>
        <p className={cn('text-xs mt-1', isOutbound ? 'text-primary-200' : 'text-[var(--muted)]')}>
          {formatDateTime(message.timestamp)} · {message.channel}
        </p>
      </div>
    </div>
  );
}

// ─── Main panel ──────────────────────────────────────────────────────────

export function LeadDetailPanel({ lead, onClose }: LeadDetailPanelProps) {
  const [notes, setNotes] = React.useState(lead.notes || '');
  const [messageText, setMessageText] = React.useState('');
  const [messageChannel, setMessageChannel] = React.useState<'whatsapp' | 'email'>('whatsapp');
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Lead>) => api.leads.update(lead.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      toast.success('Lead updated');
    },
    onError: () => toast.error('Failed to update lead'),
  });

  const sendMessageMutation = useMutation({
    mutationFn: () => api.leads.sendMessage(lead.id, messageChannel, messageText),
    onSuccess: () => {
      setMessageText('');
      toast.success('Message sent');
      queryClient.invalidateQueries({ queryKey: ['leads', lead.id] });
    },
    onError: () => toast.error('Failed to send message'),
  });

  const escalateMutation = useMutation({
    mutationFn: () => api.leads.escalate(lead.id),
    onSuccess: () => {
      toast.success('Lead escalated to human');
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
    onError: () => toast.error('Failed to escalate'),
  });

  const saveNotes = () => {
    updateMutation.mutate({ notes });
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="w-full max-w-xl bg-white dark:bg-surface-dark shadow-2xl flex flex-col overflow-hidden animate-slide-in-right">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-[var(--border)]">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-semibold text-[var(--foreground)]">{lead.full_name}</h2>
              <Badge variant={statusVariant[lead.status]}>
                {lead.status.replace(/_/g, ' ')}
              </Badge>
              {lead.temperature === 'hot' && <span title="Hot lead">🔥</span>}
            </div>
            <p className="text-sm text-[var(--muted)]">
              {lead.property_interest || 'No property interest specified'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--muted)] hover:bg-[var(--muted-bg)] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {/* Contact info */}
          <div className="p-5 border-b border-[var(--border)]">
            <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-3">
              Contact Info
            </h3>
            <div className="space-y-2">
              {lead.phone && (
                <div className="flex items-center gap-2 text-sm">
                  <Phone className="w-4 h-4 text-[var(--muted)]" />
                  <a href={`tel:${lead.phone}`} className="text-[var(--foreground)] hover:text-primary-500">
                    {lead.phone}
                  </a>
                </div>
              )}
              {lead.email && (
                <div className="flex items-center gap-2 text-sm">
                  <Mail className="w-4 h-4 text-[var(--muted)]" />
                  <a href={`mailto:${lead.email}`} className="text-[var(--foreground)] hover:text-primary-500">
                    {lead.email}
                  </a>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="w-4 h-4 text-[var(--muted)]" />
                <span className="text-[var(--muted)]">
                  Last contact: {formatRelativeTime(lead.last_contact_at)}
                </span>
              </div>
            </div>
          </div>

          {/* Property interest */}
          <div className="p-5 border-b border-[var(--border)]">
            <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-3">
              Property Interest
            </h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-[var(--muted)] text-xs mb-0.5">Interest</p>
                <p className="text-[var(--foreground)]">{lead.property_interest || '—'}</p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-xs mb-0.5">Budget</p>
                <p className="text-[var(--foreground)]">
                  {lead.budget_min || lead.budget_max
                    ? `${formatCurrency(lead.budget_min)} – ${formatCurrency(lead.budget_max)}`
                    : '—'}
                </p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-xs mb-0.5">Location</p>
                <p className="text-[var(--foreground)]">{lead.preferred_location || '—'}</p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-xs mb-0.5">Bedrooms</p>
                <p className="text-[var(--foreground)]">{lead.preferred_bedrooms ?? '—'}</p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-xs mb-0.5">Source</p>
                <p className="text-[var(--foreground)]">{lead.source || '—'}</p>
              </div>
            </div>
          </div>

          {/* Status change */}
          <div className="p-5 border-b border-[var(--border)]">
            <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-3">
              Change Status
            </h3>
            <Select
              options={statusOptions}
              value={lead.status}
              onValueChange={(v) => updateMutation.mutate({ status: v as LeadStatus })}
            />
          </div>

          {/* Conversation history */}
          <div className="p-5 border-b border-[var(--border)]">
            <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-3">
              Conversation History
            </h3>
            {lead.messages.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">No messages yet</p>
            ) : (
              <div className="flex flex-col gap-2 max-h-64 overflow-y-auto scrollbar-thin pr-1">
                {lead.messages.map((msg) => (
                  <ChatBubble key={msg.id} message={msg} />
                ))}
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="p-5 border-b border-[var(--border)]">
            <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-3">
              Notes
            </h3>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add private notes about this lead..."
              className="text-sm min-h-[80px]"
            />
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              loading={updateMutation.isPending}
              onClick={saveNotes}
            >
              Save Notes
            </Button>
          </div>
        </div>

        {/* Quick actions footer */}
        <div className="p-5 border-t border-[var(--border)] space-y-3">
          {/* Send message */}
          <div className="flex gap-2">
            <select
              value={messageChannel}
              onChange={(e) => setMessageChannel(e.target.value as 'whatsapp' | 'email')}
              className="h-9 rounded-lg border border-[var(--border)] bg-white text-sm px-2 text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-primary-400"
            >
              <option value="whatsapp">WhatsApp</option>
              <option value="email">Email</option>
            </select>
            <input
              type="text"
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              placeholder="Type a message..."
              className="flex-1 h-9 rounded-lg border border-[var(--border)] bg-white text-sm px-3 text-[var(--foreground)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-primary-400"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && messageText.trim()) {
                  sendMessageMutation.mutate();
                }
              }}
            />
            <Button
              size="icon"
              onClick={() => sendMessageMutation.mutate()}
              disabled={!messageText.trim()}
              loading={sendMessageMutation.isPending}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="flex-1 gap-1.5"
              onClick={() => {
                // Schedule viewing — would open a date picker modal in full implementation
                toast.info('Schedule viewing — coming soon');
              }}
            >
              <Calendar className="w-4 h-4" />
              Schedule Viewing
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="flex-1 gap-1.5"
              loading={escalateMutation.isPending}
              onClick={() => escalateMutation.mutate()}
            >
              <ArrowUp className="w-4 h-4" />
              Escalate
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
