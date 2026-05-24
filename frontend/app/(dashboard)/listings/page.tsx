'use client';

import * as React from 'react';
import { Plus, Search } from 'lucide-react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { ListingCard } from '@/components/listing-card';
import { Modal } from '@/components/ui/modal';
import { useToast } from '@/components/ui/toast';
import type { Listing } from '@/lib/types';

// ─── Status filter options ─────────────────────────────────────────────────

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'active', label: 'Active' },
  { value: 'sold', label: 'Sold' },
  { value: 'withdrawn', label: 'Withdrawn' },
];

// ─── Page ─────────────────────────────────────────────────────────────────

export default function ListingsPage() {
  const [statusFilter, setStatusFilter] = React.useState('');
  const [searchQuery, setSearchQuery] = React.useState('');
  const [deleteTarget, setDeleteTarget] = React.useState<Listing | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data, isLoading } = useQuery({
    queryKey: ['listings', { status: statusFilter, search: searchQuery }],
    queryFn: () =>
      api.listings.list({
        status: statusFilter || undefined,
        search: searchQuery || undefined,
      }),
  });

  const listings = data?.items ?? [];

  // Filter locally by search too (client-side supplement)
  const filtered = React.useMemo(() => {
    if (!searchQuery) return listings;
    const q = searchQuery.toLowerCase();
    return listings.filter(
      (l) =>
        l.property_name.toLowerCase().includes(q) ||
        l.address.toLowerCase().includes(q)
    );
  }, [listings, searchQuery]);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.listings.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      toast.success('Listing deleted');
      setDeleteTarget(null);
    },
    onError: () => toast.error('Failed to delete listing'),
  });

  const markSoldMutation = useMutation({
    mutationFn: (id: string) => api.listings.markSold(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      toast.success('Listing marked as sold');
    },
    onError: () => toast.error('Failed to mark sold'),
  });

  const activeCount = listings.filter((l) => l.status === 'active').length;
  const soldCount = listings.filter((l) => l.status === 'sold').length;
  const kbIndexedCount = listings.filter((l) => l.kb_indexed).length;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[var(--foreground)]">Listings</h1>
          <p className="text-sm text-[var(--muted)] mt-0.5">
            {activeCount} active · {soldCount} sold · {kbIndexedCount} KB indexed
          </p>
        </div>
        <Link href="/listings/new">
          <Button className="gap-2">
            <Plus className="w-4 h-4" />
            Add Listing
          </Button>
        </Link>
      </div>

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search listings..."
            className="w-full h-9 pl-9 pr-3 rounded-lg border border-[var(--border)] bg-white text-sm text-[var(--foreground)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-primary-400"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            options={statusOptions}
            value={statusFilter}
            onValueChange={setStatusFilter}
            placeholder="Filter by status"
          />
        </div>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="rounded-xl border border-[var(--border)] overflow-hidden animate-pulse">
              <div className="h-44 bg-[var(--muted-bg)]" />
              <div className="p-4 space-y-2">
                <div className="h-4 bg-[var(--muted-bg)] rounded w-3/4" />
                <div className="h-3 bg-[var(--muted-bg)] rounded w-1/2" />
                <div className="h-3 bg-[var(--muted-bg)] rounded w-1/4" />
              </div>
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-[var(--muted)]">
          <div className="w-16 h-16 rounded-2xl bg-[var(--muted-bg)] flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </div>
          <p className="font-medium text-[var(--foreground)]">No listings found</p>
          <p className="text-sm mt-1">
            {searchQuery || statusFilter ? 'Try adjusting your filters' : 'Add your first listing to get started'}
          </p>
          {!searchQuery && !statusFilter && (
            <Link href="/listings/new" className="mt-4 inline-block">
              <Button className="gap-2 mt-4">
                <Plus className="w-4 h-4" />
                Add Your First Listing
              </Button>
            </Link>
          )}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {filtered.map((listing) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              onEdit={() => {
                // Would navigate to edit page
              }}
              onViewResearch={() => {
                // Would open research panel
              }}
              onMarkSold={() => markSoldMutation.mutate(listing.id)}
              onDelete={() => setDeleteTarget(listing)}
            />
          ))}
        </div>
      )}

      {/* Delete confirmation modal */}
      <Modal
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete Listing"
        description={`Are you sure you want to delete "${deleteTarget?.property_name}"? This action cannot be undone.`}
        footer={
          <>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              loading={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
            >
              Delete Listing
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--muted)]">
          This will permanently remove the listing and all associated media from the knowledge base.
        </p>
      </Modal>
    </div>
  );
}
