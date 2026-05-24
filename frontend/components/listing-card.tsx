'use client';

import * as React from 'react';
import { MoreVertical, Edit2, Search, CheckSquare, Trash2, BedDouble, Bath, CheckCircle } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { cn, formatCurrency } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import type { Listing, ListingStatus } from '@/lib/types';

// ─── Status badge ─────────────────────────────────────────────────────────

const statusVariant: Record<ListingStatus, 'success' | 'outline' | 'secondary'> = {
  active: 'success',
  sold: 'outline',
  withdrawn: 'secondary',
};

// ─── Props ────────────────────────────────────────────────────────────────

interface ListingCardProps {
  listing: Listing;
  onEdit?: (listing: Listing) => void;
  onViewResearch?: (listing: Listing) => void;
  onMarkSold?: (listing: Listing) => void;
  onDelete?: (listing: Listing) => void;
}

// ─── Card ─────────────────────────────────────────────────────────────────

export function ListingCard({
  listing,
  onEdit,
  onViewResearch,
  onMarkSold,
  onDelete,
}: ListingCardProps) {
  const primaryPhoto = listing.media.find((m) => m.type === 'photo' && m.is_primary) ||
    listing.media.find((m) => m.type === 'photo');

  return (
    <div className="bg-white dark:bg-surface-dark rounded-xl border border-[var(--border)] shadow-card overflow-hidden hover:shadow-card-hover transition-shadow group">
      {/* Photo */}
      <div className="relative h-44 bg-[var(--muted-bg)] overflow-hidden">
        {primaryPhoto ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={primaryPhoto.url}
            alt={listing.property_name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[var(--muted)]">
            <svg className="w-12 h-12 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </div>
        )}

        {/* Status badge overlay */}
        <div className="absolute top-2 left-2">
          <Badge variant={statusVariant[listing.status]} className="capitalize shadow-sm">
            {listing.status}
          </Badge>
        </div>

        {/* KB indexed badge */}
        {listing.kb_indexed && (
          <div className="absolute top-2 right-10">
            <span className="inline-flex items-center gap-1 bg-green-100 text-green-700 text-xs font-medium px-2 py-0.5 rounded-full shadow-sm">
              <CheckCircle className="w-3 h-3" />
              KB
            </span>
          </div>
        )}

        {/* Actions menu */}
        <div className="absolute top-2 right-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className="w-7 h-7 rounded-lg bg-white/90 shadow-sm flex items-center justify-center text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">
                <MoreVertical className="w-4 h-4" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={4}
                className="z-50 min-w-[160px] bg-white dark:bg-surface-dark rounded-xl border border-[var(--border)] shadow-lg p-1 animate-in fade-in-0 zoom-in-95"
              >
                {onEdit && (
                  <DropdownMenu.Item
                    onSelect={() => onEdit(listing)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--foreground)] rounded-lg cursor-pointer hover:bg-[var(--muted-bg)] outline-none"
                  >
                    <Edit2 className="w-4 h-4" /> Edit
                  </DropdownMenu.Item>
                )}
                {onViewResearch && (
                  <DropdownMenu.Item
                    onSelect={() => onViewResearch(listing)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--foreground)] rounded-lg cursor-pointer hover:bg-[var(--muted-bg)] outline-none"
                  >
                    <Search className="w-4 h-4" /> View Research
                  </DropdownMenu.Item>
                )}
                {listing.status === 'active' && onMarkSold && (
                  <DropdownMenu.Item
                    onSelect={() => onMarkSold(listing)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--foreground)] rounded-lg cursor-pointer hover:bg-[var(--muted-bg)] outline-none"
                  >
                    <CheckSquare className="w-4 h-4" /> Mark Sold
                  </DropdownMenu.Item>
                )}
                <DropdownMenu.Separator className="h-px bg-[var(--border)] my-1" />
                {onDelete && (
                  <DropdownMenu.Item
                    onSelect={() => onDelete(listing)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 rounded-lg cursor-pointer hover:bg-red-50 dark:hover:bg-red-900/20 outline-none"
                  >
                    <Trash2 className="w-4 h-4" /> Delete
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="font-semibold text-[var(--foreground)] truncate mb-0.5">
          {listing.property_name}
        </h3>
        <p className="text-xs text-[var(--muted)] truncate mb-3">{listing.address}</p>

        {/* Price range */}
        {(listing.price_min || listing.price_max) && (
          <p className="text-sm font-semibold text-primary-500 mb-3">
            {listing.price_min && listing.price_max
              ? `${formatCurrency(listing.price_min)} – ${formatCurrency(listing.price_max)}`
              : formatCurrency(listing.price_min || listing.price_max)}
          </p>
        )}

        {/* Chips row */}
        <div className="flex items-center gap-3 text-xs text-[var(--muted)]">
          {listing.bedrooms != null && (
            <span className="flex items-center gap-1">
              <BedDouble className="w-3.5 h-3.5" />
              {listing.bedrooms} bed
            </span>
          )}
          {listing.bathrooms != null && (
            <span className="flex items-center gap-1">
              <Bath className="w-3.5 h-3.5" />
              {listing.bathrooms} bath
            </span>
          )}
          <span className={cn(
            'ml-auto capitalize px-2 py-0.5 rounded text-xs',
            listing.property_type === 'condo' ? 'bg-blue-50 text-blue-600' :
            listing.property_type === 'landed' ? 'bg-green-50 text-green-600' :
            'bg-purple-50 text-purple-600'
          )}>
            {listing.property_type}
          </span>
        </div>
      </div>
    </div>
  );
}
