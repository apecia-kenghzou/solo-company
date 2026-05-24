import { create } from 'zustand';
import type { AgentAction } from '@/lib/types';

interface ClerkUser {
  id: string;
  firstName: string | null;
  lastName: string | null;
  emailAddresses: { emailAddress: string }[];
  imageUrl: string;
}

interface AppState {
  // Agent activity
  agentActions: AgentAction[];
  addAgentAction: (action: AgentAction) => void;
  setAgentActions: (actions: AgentAction[]) => void;

  // Approvals
  pendingApprovals: number;
  setPendingApprovals: (n: number) => void;

  // Sidebar
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  // Current user (from Clerk)
  currentUser: ClerkUser | null;
  setCurrentUser: (user: ClerkUser | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Agent activity — keep last 100
  agentActions: [],
  addAgentAction: (action) =>
    set((state) => ({
      agentActions: [action, ...state.agentActions].slice(0, 100),
    })),
  setAgentActions: (actions) => set({ agentActions: actions }),

  // Approvals
  pendingApprovals: 0,
  setPendingApprovals: (n) => set({ pendingApprovals: n }),

  // Sidebar
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  // Current user
  currentUser: null,
  setCurrentUser: (user) => set({ currentUser: user }),
}));
