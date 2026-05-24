'use client';

import * as React from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { TagInput } from '@/components/tag-input';
import { FileUpload } from '@/components/file-upload';
import { Modal } from '@/components/ui/modal';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import {
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Building2,
  Briefcase,
  Users,
} from 'lucide-react';
import type {
  CompanyProfile,
  BusinessRules,
  BrandVoice,
  Vertical,
  PreferredChannel,
  Integration,
} from '@/lib/types';

// ─── Page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-[var(--foreground)]">Settings</h1>
        <p className="text-sm text-[var(--muted)] mt-0.5">
          Configure your business profile, rules, integrations and vertical
        </p>
      </div>

      <Tabs.Root defaultValue="profile">
        <Tabs.List className="flex items-center gap-1 bg-[var(--muted-bg)] p-1 rounded-xl mb-6 overflow-x-auto">
          {[
            { value: 'profile', label: 'Company Profile' },
            { value: 'rules', label: 'Business Rules' },
            { value: 'integrations', label: 'Integrations' },
            { value: 'vertical', label: 'Vertical' },
          ].map((tab) => (
            <Tabs.Trigger
              key={tab.value}
              value={tab.value}
              className={cn(
                'flex-1 min-w-max px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                'text-[var(--muted)] hover:text-[var(--foreground)]',
                'data-[state=active]:bg-white data-[state=active]:text-[var(--foreground)] data-[state=active]:shadow-sm'
              )}
            >
              {tab.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="profile">
          <CompanyProfileTab />
        </Tabs.Content>
        <Tabs.Content value="rules">
          <BusinessRulesTab />
        </Tabs.Content>
        <Tabs.Content value="integrations">
          <IntegrationsTab />
        </Tabs.Content>
        <Tabs.Content value="vertical">
          <VerticalTab />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

// ─── Tab 1: Company Profile ───────────────────────────────────────────────

function CompanyProfileTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ['settings-profile'],
    queryFn: () => api.settings.getCompanyProfile(),
  });

  const [form, setForm] = React.useState<Partial<CompanyProfile>>({});
  const [logoFiles, setLogoFiles] = React.useState<File[]>([]);

  React.useEffect(() => {
    if (profile) setForm(profile);
  }, [profile]);

  const saveMutation = useMutation({
    mutationFn: (data: CompanyProfile) => api.settings.saveCompanyProfile(data),
    onSuccess: () => {
      toast.success('Company profile saved');
      queryClient.invalidateQueries({ queryKey: ['settings-profile'] });
    },
    onError: () => toast.error('Failed to save'),
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const set = (key: keyof CompanyProfile, value: any) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  if (isLoading) return <SettingsLoadingSkeleton />;

  const brandVoiceOptions: { value: BrandVoice; label: string; description: string }[] = [
    { value: 'formal', label: 'Formal', description: 'Professional, structured, corporate tone' },
    { value: 'friendly', label: 'Friendly', description: 'Warm, approachable, conversational' },
    { value: 'luxury', label: 'Luxury', description: 'Elegant, aspirational, exclusive' },
  ];

  return (
    <div className="space-y-8">
      <Section title="Business Details">
        <div className="grid sm:grid-cols-2 gap-4">
          <Input
            label="Company Name *"
            value={form.company_name ?? ''}
            onChange={(e) => set('company_name', e.target.value)}
            placeholder="e.g. Pinnacle Properties"
          />
          <Input
            label="Tagline"
            value={form.tagline ?? ''}
            onChange={(e) => set('tagline', e.target.value)}
            placeholder="Your brand tagline"
          />
          <Input
            label="Owner Name *"
            value={form.owner_name ?? ''}
            onChange={(e) => set('owner_name', e.target.value)}
            placeholder="Full name"
          />
          <Input
            label="Phone *"
            value={form.phone ?? ''}
            onChange={(e) => set('phone', e.target.value)}
            placeholder="+60 12-345 6789"
            type="tel"
          />
          <Input
            label="Email *"
            value={form.email ?? ''}
            onChange={(e) => set('email', e.target.value)}
            placeholder="contact@myagency.com"
            type="email"
          />
          <Input
            label="License Number"
            value={form.license_number ?? ''}
            onChange={(e) => set('license_number', e.target.value)}
            placeholder="E/RES/01234"
          />
        </div>
        <Textarea
          label="Office Address"
          value={form.office_address ?? ''}
          onChange={(e) => set('office_address', e.target.value)}
          placeholder="Full office address"
          className="mt-4"
        />
      </Section>

      <Section title="Brand Voice">
        <div className="grid sm:grid-cols-3 gap-3">
          {brandVoiceOptions.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => set('brand_voice', opt.value)}
              className={cn(
                'text-left p-4 rounded-xl border-2 transition-colors',
                form.brand_voice === opt.value
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-[var(--border)] hover:border-primary-200'
              )}
            >
              <p className="font-medium text-sm text-[var(--foreground)]">{opt.label}</p>
              <p className="text-xs text-[var(--muted)] mt-0.5">{opt.description}</p>
            </button>
          ))}
        </div>
      </Section>

      <Section title="Social Media">
        <div className="grid sm:grid-cols-2 gap-4">
          <Input
            label="Instagram URL"
            value={form.instagram_url ?? ''}
            onChange={(e) => set('instagram_url', e.target.value)}
            placeholder="https://instagram.com/youragency"
          />
          <Input
            label="Facebook URL"
            value={form.facebook_url ?? ''}
            onChange={(e) => set('facebook_url', e.target.value)}
            placeholder="https://facebook.com/youragency"
          />
          <Input
            label="TikTok URL"
            value={form.tiktok_url ?? ''}
            onChange={(e) => set('tiktok_url', e.target.value)}
            placeholder="https://tiktok.com/@youragency"
          />
          <Input
            label="LinkedIn URL"
            value={form.linkedin_url ?? ''}
            onChange={(e) => set('linkedin_url', e.target.value)}
            placeholder="https://linkedin.com/in/yourname"
          />
        </div>
      </Section>

      <Section title="Company Logo">
        <FileUpload
          label="Upload Logo"
          description="PNG, JPG, SVG. Recommended: 400×400px or larger."
          accept={{ 'image/*': ['.png', '.jpg', '.jpeg', '.svg', '.webp'] }}
          maxFiles={1}
          multiple={false}
          onFilesChange={setLogoFiles}
        />
        {form.logo_url && logoFiles.length === 0 && (
          <div className="mt-3 flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={form.logo_url} alt="Logo" className="w-16 h-16 rounded-xl object-contain border border-[var(--border)]" />
            <p className="text-sm text-[var(--muted)]">Current logo</p>
          </div>
        )}
      </Section>

      <div className="flex justify-end">
        <Button
          onClick={() => saveMutation.mutate(form as CompanyProfile)}
          loading={saveMutation.isPending}
          className="min-w-[120px]"
        >
          Save Changes
        </Button>
      </div>
    </div>
  );
}

// ─── Tab 2: Business Rules ─────────────────────────────────────────────────

function BusinessRulesTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: rules, isLoading } = useQuery({
    queryKey: ['settings-rules'],
    queryFn: () => api.settings.getBusinessRules(),
  });

  const [form, setForm] = React.useState<Partial<BusinessRules>>({
    questions_to_ask: [],
    escalation_triggers: ['offer', 'urgent', 'cancel', 'angry'],
    follow_up_stages: [
      { label: 'Cold Lead', intervals_days: [3, 7, 14] },
      { label: 'Warm Lead', intervals_days: [1, 3, 7] },
      { label: 'Post-Showing', intervals_days: [1, 2, 5] },
    ],
    preferred_channel: 'whatsapp',
    viewing_availability: {
      weekdays: { enabled: true, start: '09:00', end: '18:00' },
      saturday: { enabled: true, start: '10:00', end: '16:00' },
      sunday: { enabled: false, start: '10:00', end: '14:00' },
    },
  });

  React.useEffect(() => {
    if (rules) setForm(rules);
  }, [rules]);

  const saveMutation = useMutation({
    mutationFn: (data: BusinessRules) => api.settings.saveBusinessRules(data),
    onSuccess: () => {
      toast.success('Business rules saved');
      queryClient.invalidateQueries({ queryKey: ['settings-rules'] });
    },
    onError: () => toast.error('Failed to save'),
  });

  const set = <K extends keyof BusinessRules>(key: K, value: BusinessRules[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  if (isLoading) return <SettingsLoadingSkeleton />;

  return (
    <div className="space-y-8">
      <Section title="Qualification Questions">
        <TagInput
          label="Questions to always ask"
          value={form.questions_to_ask ?? []}
          onChange={(v) => set('questions_to_ask', v)}
          placeholder="What is your budget? Are you a first-time buyer?..."
        />
      </Section>

      <Section title="Compliance & Boundaries">
        <Textarea
          label="Things to never promise (one per line)"
          value={form.things_never_promise ?? ''}
          onChange={(e) => set('things_never_promise', e.target.value)}
          placeholder={"Guaranteed rental returns\nCapital appreciation guarantees\nFixed price locks"}
          className="min-h-[100px]"
        />
        <div className="mt-4">
          <Textarea
            label="Compliance Notes"
            value={form.compliance_notes ?? ''}
            onChange={(e) => set('compliance_notes', e.target.value)}
            placeholder="Any regulatory requirements or compliance notes for your area..."
          />
        </div>
      </Section>

      <Section title="Escalation Triggers">
        <TagInput
          label="Keywords that trigger human escalation"
          value={form.escalation_triggers ?? []}
          onChange={(v) => set('escalation_triggers', v)}
          placeholder="offer, urgent, cancel, angry..."
        />
      </Section>

      <Section title="Follow-Up Sequences">
        <div className="space-y-4">
          {(form.follow_up_stages ?? []).map((stage, idx) => (
            <div key={idx} className="flex items-center gap-4 p-4 rounded-xl border border-[var(--border)]">
              <div className="w-28 flex-shrink-0">
                <p className="text-sm font-medium text-[var(--foreground)]">{stage.label}</p>
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--muted)] mb-1.5">Follow-up days after contact</p>
                <div className="flex items-center gap-2">
                  {stage.intervals_days.map((day, i) => (
                    <React.Fragment key={i}>
                      <span className="w-10 h-8 rounded-lg bg-primary-100 text-primary-700 text-sm font-semibold flex items-center justify-center">
                        {day}d
                      </span>
                      {i < stage.intervals_days.length - 1 && (
                        <span className="text-[var(--muted)] text-xs">→</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Contact Preferences">
        <div>
          <p className="text-sm font-medium text-[var(--foreground)] mb-3">Preferred contact channel</p>
          <div className="flex gap-3">
            {[
              { value: 'whatsapp' as PreferredChannel, label: 'WhatsApp first', icon: '💬' },
              { value: 'email' as PreferredChannel, label: 'Email first', icon: '📧' },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => set('preferred_channel', opt.value)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 rounded-xl border-2 text-sm font-medium transition-colors',
                  form.preferred_channel === opt.value
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-[var(--border)] text-[var(--muted)] hover:border-primary-200'
                )}
              >
                <span>{opt.icon}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Viewing Availability">
        {(['weekdays', 'saturday', 'sunday'] as const).map((day) => {
          const window = form.viewing_availability?.[day];
          if (!window) return null;
          const labels: Record<string, string> = {
            weekdays: 'Mon – Fri',
            saturday: 'Saturday',
            sunday: 'Sunday',
          };
          return (
            <div key={day} className="flex items-center gap-4 py-3 border-b border-[var(--border)] last:border-0">
              <div className="flex items-center gap-3 w-36 flex-shrink-0">
                <input
                  type="checkbox"
                  checked={window.enabled}
                  onChange={(e) =>
                    set('viewing_availability', {
                      ...form.viewing_availability!,
                      [day]: { ...window, enabled: e.target.checked },
                    })
                  }
                  className="w-4 h-4 accent-primary-500 rounded"
                />
                <span className="text-sm font-medium text-[var(--foreground)]">{labels[day]}</span>
              </div>
              <div className={cn('flex items-center gap-2', !window.enabled && 'opacity-40 pointer-events-none')}>
                <input
                  type="time"
                  value={window.start}
                  onChange={(e) =>
                    set('viewing_availability', {
                      ...form.viewing_availability!,
                      [day]: { ...window, start: e.target.value },
                    })
                  }
                  className="h-8 px-2 rounded-lg border border-[var(--border)] text-sm text-[var(--foreground)] bg-white focus:outline-none focus:ring-2 focus:ring-primary-400"
                />
                <span className="text-[var(--muted)] text-sm">to</span>
                <input
                  type="time"
                  value={window.end}
                  onChange={(e) =>
                    set('viewing_availability', {
                      ...form.viewing_availability!,
                      [day]: { ...window, end: e.target.value },
                    })
                  }
                  className="h-8 px-2 rounded-lg border border-[var(--border)] text-sm text-[var(--foreground)] bg-white focus:outline-none focus:ring-2 focus:ring-primary-400"
                />
              </div>
            </div>
          );
        })}
      </Section>

      <div className="flex justify-end">
        <Button
          onClick={() => saveMutation.mutate(form as BusinessRules)}
          loading={saveMutation.isPending}
          className="min-w-[120px]"
        >
          Save Rules
        </Button>
      </div>
    </div>
  );
}

// ─── Tab 3: Integrations ──────────────────────────────────────────────────

const INTEGRATION_CONFIGS = [
  {
    id: 'gmail' as const,
    name: 'Gmail',
    icon: '📧',
    description: 'Connect Gmail to send and receive emails through your agents',
    connectLabel: 'Connect with Google',
  },
  {
    id: 'whatsapp' as const,
    name: 'WhatsApp Business',
    icon: '💬',
    description: 'Connect WhatsApp Business API for automated messaging',
    connectLabel: 'Setup WhatsApp',
  },
  {
    id: 'google_calendar' as const,
    name: 'Google Calendar',
    icon: '📅',
    description: 'Sync viewing appointments and follow-ups to your calendar',
    connectLabel: 'Connect Calendar',
  },
  {
    id: 'instagram' as const,
    name: 'Instagram / Facebook',
    icon: '📸',
    description: 'Connect Meta Business Suite to publish content automatically',
    connectLabel: 'Connect with Meta',
  },
];

function IntegrationsTab() {
  const { toast } = useToast();
  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ['settings-integrations'],
    queryFn: () => api.settings.getIntegrations(),
  });

  const getIntegration = (id: string): Integration | undefined =>
    integrations.find((i) => i.type === id);

  if (isLoading) return <SettingsLoadingSkeleton />;

  return (
    <div className="space-y-4">
      {INTEGRATION_CONFIGS.map((cfg) => {
        const integration = getIntegration(cfg.id);
        const connected = integration?.connected ?? false;

        return (
          <div
            key={cfg.id}
            className="flex items-center gap-5 p-5 bg-white rounded-2xl border border-[var(--border)] shadow-card"
          >
            <div className="text-3xl flex-shrink-0">{cfg.icon}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <h3 className="text-sm font-semibold text-[var(--foreground)]">{cfg.name}</h3>
                {connected ? (
                  <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                    <CheckCircle className="w-3.5 h-3.5" />
                    Connected
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs text-amber-600 font-medium">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Not Connected
                  </span>
                )}
              </div>
              <p className="text-xs text-[var(--muted)]">{cfg.description}</p>
              {connected && integration?.account_identifier && (
                <p className="text-xs text-primary-600 mt-1 font-medium">
                  {integration.account_identifier}
                </p>
              )}
            </div>
            <div className="flex-shrink-0">
              {connected ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => toast.info('Disconnect — feature coming soon')}
                  className="text-red-600 border-red-200 hover:bg-red-50"
                >
                  Disconnect
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => toast.info(`${cfg.connectLabel} — OAuth flow coming soon`)}
                >
                  {cfg.connectLabel}
                </Button>
              )}
            </div>
          </div>
        );
      })}

      {/* WhatsApp QR code placeholder */}
      <div className="p-5 bg-green-50 rounded-2xl border border-green-200">
        <h3 className="text-sm font-semibold text-green-800 mb-2">WhatsApp Setup Guide</h3>
        <ol className="text-xs text-green-700 space-y-1 list-decimal list-inside">
          <li>Apply for WhatsApp Business API via Meta Business Suite</li>
          <li>Obtain your Phone Number ID and Access Token</li>
          <li>Enter your API credentials in the WhatsApp integration above</li>
          <li>Verify your business phone number</li>
          <li>Your agents will then be able to send and receive WhatsApp messages</li>
        </ol>
      </div>
    </div>
  );
}

// ─── Tab 4: Vertical ──────────────────────────────────────────────────────

function VerticalTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ['settings-profile'],
    queryFn: () => api.settings.getCompanyProfile(),
  });

  const [switchTarget, setSwitchTarget] = React.useState<Vertical | null>(null);

  const switchMutation = useMutation({
    mutationFn: (vertical: Vertical) =>
      api.settings.saveCompanyProfile({ ...profile!, vertical }),
    onSuccess: (_, vertical) => {
      toast.success(`Switched to ${vertical} vertical. KB re-indexing started.`);
      queryClient.invalidateQueries({ queryKey: ['settings-profile'] });
      setSwitchTarget(null);
    },
    onError: () => toast.error('Failed to switch vertical'),
  });

  const verticals: {
    value: Vertical;
    label: string;
    icon: React.ReactNode;
    description: string;
    features: string[];
  }[] = [
    {
      value: 'real_estate',
      label: 'Real Estate Agent',
      icon: <Building2 className="w-6 h-6" />,
      description: 'For property agents managing listings, leads, and viewings',
      features: ['Listing KB indexing', 'Viewing scheduler', 'Property research agent'],
    },
    {
      value: 'consultant',
      label: 'Freelance Consultant',
      icon: <Briefcase className="w-6 h-6" />,
      description: 'For consultants managing projects, clients, and proposals',
      features: ['Project pipeline', 'Proposal generator', 'Client nurturing'],
    },
    {
      value: 'recruiter',
      label: 'Recruiter',
      icon: <Users className="w-6 h-6" />,
      description: 'For independent recruiters managing candidates and employers',
      features: ['Candidate pipeline', 'Job matching AI', 'Employer outreach'],
    },
  ];

  if (isLoading) return <SettingsLoadingSkeleton />;

  const currentVertical = profile?.vertical ?? 'real_estate';

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-[var(--muted)] mb-4">
          Your vertical determines how your AI agents are configured and what features are available.
          Switching verticals will re-index your knowledge base.
        </p>

        <div className="grid gap-4">
          {verticals.map((v) => {
            const isCurrent = currentVertical === v.value;
            return (
              <div
                key={v.value}
                className={cn(
                  'p-5 rounded-2xl border-2 transition-colors',
                  isCurrent
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-[var(--border)] bg-white hover:border-primary-200'
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        'w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0',
                        isCurrent ? 'bg-primary-500 text-white' : 'bg-[var(--muted-bg)] text-[var(--muted)]'
                      )}
                    >
                      {v.icon}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <h3 className="text-sm font-semibold text-[var(--foreground)]">{v.label}</h3>
                        {isCurrent && (
                          <span className="text-xs bg-primary-100 text-primary-700 font-medium px-2 py-0.5 rounded-full">
                            Current
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[var(--muted)] mb-2">{v.description}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {v.features.map((f) => (
                          <span
                            key={f}
                            className="text-xs bg-white border border-[var(--border)] text-[var(--muted)] px-2 py-0.5 rounded-md"
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  {!isCurrent && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSwitchTarget(v.value)}
                      className="flex-shrink-0"
                    >
                      Switch
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Confirm switch modal */}
      <Modal
        open={!!switchTarget}
        onOpenChange={(open) => !open && setSwitchTarget(null)}
        title="Switch Vertical"
        description="Are you sure you want to switch your vertical?"
        footer={
          <>
            <Button variant="outline" onClick={() => setSwitchTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => switchTarget && switchMutation.mutate(switchTarget)}
              loading={switchMutation.isPending}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Switch & Re-index KB
            </Button>
          </>
        }
      >
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          <p className="font-medium mb-1">⚠️ Knowledge base will be re-indexed</p>
          <p>
            Switching verticals will update your AI agent configurations and trigger a full
            knowledge base re-indexing. This may take a few minutes.
          </p>
        </div>
      </Modal>
    </div>
  );
}

// ─── Shared sub-components ────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-[var(--foreground)] mb-4 pb-2 border-b border-[var(--border)]">
        {title}
      </h2>
      {children}
    </div>
  );
}

function SettingsLoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="space-y-3">
          <div className="h-4 bg-[var(--muted-bg)] rounded w-1/4" />
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="h-9 bg-[var(--muted-bg)] rounded-lg" />
            <div className="h-9 bg-[var(--muted-bg)] rounded-lg" />
          </div>
        </div>
      ))}
    </div>
  );
}
