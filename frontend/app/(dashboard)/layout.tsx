'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  Building2,
  CheckSquare,
  FileText,
  Settings,
  Menu,
  X,
  Bell,
} from 'lucide-react';
import { UserButton } from '@clerk/nextjs';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store/useAppStore';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

// ─── Nav items ────────────────────────────────────────────────────────────

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/leads', label: 'Leads', icon: Users },
  { href: '/listings', label: 'Listings', icon: Building2 },
  { href: '/approvals', label: 'Approvals', icon: CheckSquare },
  { href: '/content', label: 'Content', icon: FileText },
  { href: '/settings', label: 'Settings', icon: Settings },
];

// ─── Layout ───────────────────────────────────────────────────────────────

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar, setSidebarOpen, pendingApprovals, setPendingApprovals } =
    useAppStore();

  // Fetch pending approval count every 60s
  const { data: approvalCount } = useQuery({
    queryKey: ['approvals-count'],
    queryFn: async () => {
      const drafts = await api.approvals.list();
      return drafts.filter((d) => d.status === 'pending').length;
    },
    refetchInterval: 60_000,
  });

  React.useEffect(() => {
    if (approvalCount !== undefined) {
      setPendingApprovals(approvalCount);
    }
  }, [approvalCount, setPendingApprovals]);

  // Close sidebar on mobile when navigating
  React.useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* ── Mobile backdrop ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={cn(
          'fixed md:relative inset-y-0 left-0 z-50 flex flex-col w-60 bg-primary-500 text-white transition-transform duration-300 ease-in-out',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-0 md:overflow-hidden'
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-5 border-b border-primary-400/40 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-white/20 flex items-center justify-center font-bold text-sm">
              S
            </div>
            <span className="font-semibold text-sm tracking-tight">Solo Agent OS</span>
          </div>
          <button
            className="md:hidden p-1 rounded-lg hover:bg-white/10 transition-colors"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 overflow-y-auto scrollbar-hide">
          <ul className="space-y-0.5">
            {navItems.map(({ href, label, icon: Icon }) => {
              const isActive = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));
              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors relative',
                      isActive
                        ? 'bg-white/20 text-white'
                        : 'text-white/70 hover:bg-white/10 hover:text-white'
                    )}
                  >
                    <Icon className="w-4.5 h-4.5 flex-shrink-0 w-[18px] h-[18px]" />
                    <span>{label}</span>
                    {label === 'Approvals' && pendingApprovals > 0 && (
                      <span className="ml-auto bg-white text-primary-600 text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
                        {pendingApprovals > 9 ? '9+' : pendingApprovals}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User section */}
        <div className="p-4 border-t border-primary-400/40 flex-shrink-0">
          <div className="flex items-center gap-3">
            <UserButton
              appearance={{
                elements: {
                  avatarBox: 'w-8 h-8',
                  userButtonPopoverCard: 'z-[100]',
                },
              }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">My Account</p>
            </div>
            <button className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-white/70 hover:text-white">
              <Bell className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar (mobile) */}
        <header className="md:hidden flex items-center h-14 px-4 bg-white border-b border-[var(--border)] flex-shrink-0">
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg text-[var(--muted)] hover:bg-[var(--muted-bg)] transition-colors mr-3"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-primary-500 flex items-center justify-center font-bold text-white text-xs">
              S
            </div>
            <span className="font-semibold text-sm text-[var(--foreground)]">Solo Agent OS</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto bg-background scrollbar-thin">
          {children}
        </main>
      </div>
    </div>
  );
}
