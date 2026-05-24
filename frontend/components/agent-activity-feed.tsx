'use client';

import * as React from 'react';
import { formatDistanceToNow } from 'date-fns';
import { CheckCircle, Clock, XCircle, Loader2, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store/useAppStore';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { connectSocket, onAgentAction } from '@/lib/socket';
import { useAuth } from '@clerk/nextjs';
import type { AgentAction, AgentActionStatus, AgentName } from '@/lib/types';

// ─── Agent colour map ──────────────────────────────────────────────────────

const agentColors: Record<AgentName, string> = {
  FrontDeskAgent: 'bg-blue-100 text-blue-700',
  ResearchAgent: 'bg-purple-100 text-purple-700',
  MarketingAgent: 'bg-pink-100 text-pink-700',
  NurturingAgent: 'bg-orange-100 text-orange-700',
  EscalationAgent: 'bg-red-100 text-red-700',
  BriefingAgent: 'bg-teal-100 text-teal-700',
};

const agentShortNames: Record<AgentName, string> = {
  FrontDeskAgent: 'Front Desk',
  ResearchAgent: 'Research',
  MarketingAgent: 'Marketing',
  NurturingAgent: 'Nurturing',
  EscalationAgent: 'Escalation',
  BriefingAgent: 'Briefing',
};

// ─── Status icon ──────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: AgentActionStatus }) {
  if (status === 'success') return <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />;
  if (status === 'failed') return <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />;
  if (status === 'running') return <Loader2 className="w-4 h-4 text-blue-500 flex-shrink-0 animate-spin" />;
  return <Clock className="w-4 h-4 text-amber-500 flex-shrink-0" />;
}

// ─── Main component ───────────────────────────────────────────────────────

export function AgentActivityFeed() {
  const { getToken } = useAuth();
  const { agentActions, setAgentActions, addAgentAction } = useAppStore();
  const bottomRef = React.useRef<HTMLDivElement>(null);

  // Initial fetch
  const { data: actionsData } = useQuery({
    queryKey: ['agent-actions'],
    queryFn: () => api.agents.getActions({ limit: 20 }),
    refetchInterval: 30_000,
  });

  React.useEffect(() => {
    if (actionsData?.items) {
      setAgentActions(actionsData.items);
    }
  }, [actionsData, setAgentActions]);

  // Socket connection
  React.useEffect(() => {
    let cleanup: (() => void) | undefined;

    getToken().then((token) => {
      if (!token) return;
      connectSocket(token);
      cleanup = onAgentAction((action) => {
        addAgentAction(action);
      });
    });

    return () => {
      cleanup?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll to top (newest)
  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [agentActions.length]);

  if (agentActions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-[var(--muted)]">
        <Bot className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">No agent activity yet</p>
        <p className="text-xs mt-1">Agents will appear here when they start working</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0 overflow-y-auto max-h-72 scrollbar-thin pr-1">
      {agentActions.map((action, idx) => (
        <div
          key={action.id}
          className={cn(
            'flex items-start gap-3 py-3 px-1',
            idx < agentActions.length - 1 && 'border-b border-[var(--border)]',
            'hover:bg-[var(--muted-bg)] rounded-lg transition-colors'
          )}
        >
          <StatusIcon status={action.status} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={cn(
                  'text-xs font-medium px-2 py-0.5 rounded-full',
                  agentColors[action.agent]
                )}
              >
                {agentShortNames[action.agent]}
              </span>
              <span className="text-sm text-[var(--foreground)] truncate">
                {action.action}
              </span>
            </div>
            {action.description && (
              <p className="text-xs text-[var(--muted)] mt-0.5 truncate">{action.description}</p>
            )}
          </div>
          <span className="text-xs text-[var(--muted)] flex-shrink-0 whitespace-nowrap">
            {formatDistanceToNow(new Date(action.timestamp), { addSuffix: true })}
          </span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
