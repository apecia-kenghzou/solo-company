import * as React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';

interface StatsCardProps {
  title: string;
  value: number | string;
  trend?: number; // percentage change, positive = up, negative = down
  icon?: React.ReactNode;
  description?: string;
  loading?: boolean;
  className?: string;
}

export function StatsCard({
  title,
  value,
  trend,
  icon,
  description,
  loading,
  className,
}: StatsCardProps) {
  const trendPositive = trend !== undefined && trend > 0;
  const trendNegative = trend !== undefined && trend < 0;
  const trendNeutral = trend !== undefined && trend === 0;

  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[var(--muted)] truncate">{title}</p>
            {loading ? (
              <div className="h-8 w-20 bg-[var(--muted-bg)] rounded animate-pulse mt-1.5" />
            ) : (
              <p className="text-3xl font-bold text-[var(--foreground)] mt-1 leading-none">
                {value}
              </p>
            )}
            {description && !loading && (
              <p className="text-xs text-[var(--muted)] mt-1.5 truncate">{description}</p>
            )}
            {trend !== undefined && !loading && (
              <div className={cn(
                'inline-flex items-center gap-1 mt-2 text-xs font-medium',
                trendPositive && 'text-green-600',
                trendNegative && 'text-red-600',
                trendNeutral && 'text-[var(--muted)]'
              )}>
                {trendPositive && <TrendingUp className="w-3.5 h-3.5" />}
                {trendNegative && <TrendingDown className="w-3.5 h-3.5" />}
                {trendNeutral && <Minus className="w-3.5 h-3.5" />}
                <span>
                  {trendPositive ? '+' : ''}{trend}% from yesterday
                </span>
              </div>
            )}
          </div>
          {icon && (
            <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-900/20 flex items-center justify-center flex-shrink-0 text-primary-500">
              {icon}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
