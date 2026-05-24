'use client';

import * as React from 'react';
import { format, startOfWeek, addDays, isSameDay } from 'date-fns';
import { ChevronLeft, ChevronRight, Sparkles, Heart, Eye, MessageCircle } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/components/ui/toast';
import { cn, formatNumber } from '@/lib/utils';
import type { ContentPost, ContentType } from '@/lib/types';

// ─── Platform icons & colors ──────────────────────────────────────────────

const platformIcon: Record<ContentType, string> = {
  email: '📧',
  instagram: '📸',
  whatsapp: '💬',
  facebook: '👥',
  tiktok: '🎵',
};

const platformColor: Record<ContentType, string> = {
  email: 'bg-blue-100 text-blue-700',
  instagram: 'bg-pink-100 text-pink-700',
  whatsapp: 'bg-green-100 text-green-700',
  facebook: 'bg-indigo-100 text-indigo-700',
  tiktok: 'bg-gray-900 text-white',
};

// ─── Helpers ──────────────────────────────────────────────────────────────

function getWeekDays(weekStart: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
}

// ─── Page ─────────────────────────────────────────────────────────────────

export default function ContentPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = React.useState(() => startOfWeek(new Date(), { weekStartsOn: 1 }));

  const weekEnd = addDays(weekStart, 6);
  const weekDays = getWeekDays(weekStart);

  const { data: calendarPosts = [], isLoading: calLoading } = useQuery({
    queryKey: ['content-calendar', weekStart.toISOString()],
    queryFn: () =>
      api.content.getCalendar({
        start: format(weekStart, 'yyyy-MM-dd'),
        end: format(weekEnd, 'yyyy-MM-dd'),
      }),
  });

  const { data: publishedPosts = [], isLoading: publishedLoading } = useQuery({
    queryKey: ['content-published'],
    queryFn: () => api.content.getPublished(),
  });

  const generateMutation = useMutation({
    mutationFn: () => api.content.generateWeek(),
    onSuccess: () => {
      toast.success('Week of content generation started! Check Approvals for drafts.');
      queryClient.invalidateQueries({ queryKey: ['content-calendar'] });
    },
    onError: () => toast.error('Failed to trigger content generation'),
  });

  const getPostsForDay = (day: Date): ContentPost[] => {
    return calendarPosts.filter((post) => {
      const postDate = new Date(post.scheduled_at);
      return isSameDay(postDate, day);
    });
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[var(--foreground)]">Content Calendar</h1>
          <p className="text-sm text-[var(--muted)] mt-0.5">
            Manage scheduled and published content across all platforms
          </p>
        </div>
        <Button
          onClick={() => generateMutation.mutate()}
          loading={generateMutation.isPending}
          className="gap-2"
        >
          <Sparkles className="w-4 h-4" />
          Generate Content Week
        </Button>
      </div>

      {/* Week navigation */}
      <div className="bg-white rounded-2xl border border-[var(--border)] shadow-card overflow-hidden">
        {/* Week header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <button
            onClick={() => setWeekStart((w) => addDays(w, -7))}
            className="p-2 rounded-lg hover:bg-[var(--muted-bg)] transition-colors text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <h2 className="text-sm font-semibold text-[var(--foreground)]">
            {format(weekStart, 'MMM d')} – {format(weekEnd, 'MMM d, yyyy')}
          </h2>
          <button
            onClick={() => setWeekStart((w) => addDays(w, 7))}
            className="p-2 rounded-lg hover:bg-[var(--muted-bg)] transition-colors text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Week grid */}
        <div className="grid grid-cols-7 divide-x divide-[var(--border)]">
          {weekDays.map((day) => {
            const dayPosts = getPostsForDay(day);
            const isToday = isSameDay(day, new Date());

            return (
              <div key={day.toISOString()} className="min-h-[160px]">
                {/* Day header */}
                <div
                  className={cn(
                    'text-center py-3 border-b border-[var(--border)]',
                    isToday && 'bg-primary-50'
                  )}
                >
                  <p className="text-xs text-[var(--muted)] font-medium uppercase tracking-wide">
                    {format(day, 'EEE')}
                  </p>
                  <div
                    className={cn(
                      'text-sm font-bold mt-0.5',
                      isToday
                        ? 'w-7 h-7 rounded-full bg-primary-500 text-white flex items-center justify-center mx-auto'
                        : 'text-[var(--foreground)]'
                    )}
                  >
                    {format(day, 'd')}
                  </div>
                </div>

                {/* Day posts */}
                <div className="p-1.5 space-y-1">
                  {calLoading ? (
                    <div className="h-8 bg-[var(--muted-bg)] rounded animate-pulse" />
                  ) : (
                    dayPosts.map((post) => (
                      <div
                        key={post.id}
                        className={cn(
                          'rounded-md px-1.5 py-1 text-xs cursor-pointer hover:opacity-80 transition-opacity',
                          platformColor[post.platform]
                        )}
                        title={post.caption}
                      >
                        <p className="font-medium flex items-center gap-1">
                          <span>{platformIcon[post.platform]}</span>
                          <span className="truncate">{format(new Date(post.scheduled_at), 'HH:mm')}</span>
                        </p>
                        <p className="truncate opacity-75">{post.listing_name || post.caption.slice(0, 20)}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Published posts */}
      <Card>
        <CardHeader>
          <CardTitle>Published Posts</CardTitle>
        </CardHeader>
        <CardContent>
          {publishedLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-16 bg-[var(--muted-bg)] rounded-xl animate-pulse" />
              ))}
            </div>
          ) : publishedPosts.length === 0 ? (
            <div className="text-center py-10 text-[var(--muted)]">
              <p className="text-sm">No published posts yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {publishedPosts.map((post) => (
                <PublishedPostRow key={post.id} post={post} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Published post row ───────────────────────────────────────────────────

function PublishedPostRow({ post }: { post: ContentPost }) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-xl border border-[var(--border)] hover:bg-[var(--muted-bg)]/50 transition-colors">
      {/* Platform icon */}
      <div
        className={cn(
          'w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0',
          platformColor[post.platform]
        )}
      >
        {platformIcon[post.platform]}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Badge variant="secondary" className="capitalize text-xs">
            {post.platform}
          </Badge>
          {post.listing_name && (
            <span className="text-xs text-[var(--muted)]">{post.listing_name}</span>
          )}
          <span className="text-xs text-[var(--muted)] ml-auto">
            {post.published_at ? format(new Date(post.published_at), 'MMM d, HH:mm') : '—'}
          </span>
        </div>
        <p className="text-sm text-[var(--foreground)] line-clamp-2">{post.caption}</p>
      </div>

      {/* Stats */}
      {(post.likes != null || post.reach != null || post.comments != null) && (
        <div className="flex items-center gap-4 text-xs text-[var(--muted)] flex-shrink-0">
          {post.likes != null && (
            <span className="flex items-center gap-1">
              <Heart className="w-3.5 h-3.5 text-red-400" />
              {formatNumber(post.likes)}
            </span>
          )}
          {post.reach != null && (
            <span className="flex items-center gap-1">
              <Eye className="w-3.5 h-3.5 text-blue-400" />
              {formatNumber(post.reach)}
            </span>
          )}
          {post.comments != null && (
            <span className="flex items-center gap-1">
              <MessageCircle className="w-3.5 h-3.5 text-green-400" />
              {formatNumber(post.comments)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
