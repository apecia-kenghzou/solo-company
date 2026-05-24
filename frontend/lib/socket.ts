import { io, Socket } from 'socket.io-client';
import type { AgentAction, ContentDraft, Lead } from './types';

// ─── Singleton Socket ────────────────────────────────────────────────────────

let socket: Socket | null = null;

export function connectSocket(token: string): Socket {
  if (socket?.connected) {
    return socket;
  }

  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8000';

  socket = io(wsUrl, {
    auth: { token },
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 2000,
    reconnectionDelayMax: 10000,
  });

  socket.on('connect', () => {
    console.log('[Socket] Connected:', socket?.id);
  });

  socket.on('disconnect', (reason) => {
    console.log('[Socket] Disconnected:', reason);
  });

  socket.on('connect_error', (err) => {
    console.error('[Socket] Connection error:', err.message);
  });

  return socket;
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}

export function getSocket(): Socket | null {
  return socket;
}

// ─── Event Listeners ─────────────────────────────────────────────────────────

export function onAgentAction(callback: (action: AgentAction) => void): () => void {
  if (!socket) return () => {};
  socket.on('agent:action', callback);
  return () => socket?.off('agent:action', callback);
}

export function onApprovalNeeded(callback: (draft: ContentDraft) => void): () => void {
  if (!socket) return () => {};
  socket.on('approval:needed', callback);
  return () => socket?.off('approval:needed', callback);
}

export function onEscalation(callback: (lead: Lead) => void): () => void {
  if (!socket) return () => {};
  socket.on('lead:escalation', callback);
  return () => socket?.off('lead:escalation', callback);
}

export function onLeadUpdate(callback: (lead: Lead) => void): () => void {
  if (!socket) return () => {};
  socket.on('lead:update', callback);
  return () => socket?.off('lead:update', callback);
}

export function onKbIndexed(callback: (data: { listing_id: string; success: boolean }) => void): () => void {
  if (!socket) return () => {};
  socket.on('listing:kb_indexed', callback);
  return () => socket?.off('listing:kb_indexed', callback);
}
