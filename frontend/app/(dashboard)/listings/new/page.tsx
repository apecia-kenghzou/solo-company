'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { CheckCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { TagInput } from '@/components/tag-input';
import { FileUpload } from '@/components/file-upload';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import type { CreateListingInput } from '@/lib/types';

// ─── Schema ───────────────────────────────────────────────────────────────

const listingSchema = z.object({
  // Step 1
  property_name: z.string().min(1, 'Property name is required'),
  address: z.string().min(1, 'Address is required'),
  property_type: z.enum(['condo', 'landed', 'commercial']),
  tenure: z.enum(['freehold', 'leasehold']),
  developer: z.string().optional().nullable(),
  status: z.enum(['active', 'sold', 'withdrawn']).default('active'),
  // Step 2
  price_min: z.number().nullable().optional(),
  price_max: z.number().nullable().optional(),
  price_per_sqft: z.number().nullable().optional(),
  available_units: z.number().nullable().optional(),
  payment_scheme: z.string().nullable().optional(),
  promotions: z.string().nullable().optional(),
  // Step 3
  bedrooms: z.number().nullable().optional(),
  bathrooms: z.number().nullable().optional(),
  land_area_sqft: z.number().nullable().optional(),
  built_up_sqft: z.number().nullable().optional(),
  furnishing: z.enum(['unfurnished', 'partly', 'fully']).nullable().optional(),
  facilities: z.array(z.string()).default([]),
  // Step 4 — handled separately as files
  video_url: z.string().nullable().optional(),
  // Step 5
  selling_points: z.array(z.string()).default([]),
  target_buyer: z.string().nullable().optional(),
  nearby_amenities: z.array(z.string()).default([]),
  investment_potential: z.string().nullable().optional(),
});

type ListingFormValues = z.infer<typeof listingSchema>;

// ─── Steps config ─────────────────────────────────────────────────────────

const steps = [
  { label: 'Basic Info', description: 'Property details' },
  { label: 'Pricing', description: 'Price & units' },
  { label: 'Details', description: 'Specs & facilities' },
  { label: 'Media', description: 'Photos & documents' },
  { label: 'Marketing', description: 'Selling points' },
  { label: 'Review', description: 'Confirm & submit' },
];

// ─── Helper select options ────────────────────────────────────────────────

const propertyTypeOptions = [
  { value: 'condo', label: 'Condo' },
  { value: 'landed', label: 'Landed' },
  { value: 'commercial', label: 'Commercial' },
];

const tenureOptions = [
  { value: 'freehold', label: 'Freehold' },
  { value: 'leasehold', label: 'Leasehold' },
];

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'sold', label: 'Sold' },
  { value: 'withdrawn', label: 'Withdrawn' },
];

const furnishingOptions = [
  { value: 'unfurnished', label: 'Unfurnished' },
  { value: 'partly', label: 'Partly Furnished' },
  { value: 'fully', label: 'Fully Furnished' },
];

// ─── Number field helper ──────────────────────────────────────────────────

function NumberField({
  label,
  error,
  value,
  onChange,
  placeholder,
  prefix,
}: {
  label: string;
  error?: string;
  value: number | null | undefined;
  onChange: (v: number | null) => void;
  placeholder?: string;
  prefix?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-[var(--foreground)]">{label}</label>
      <div className="relative">
        {prefix && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[var(--muted)]">
            {prefix}
          </span>
        )}
        <input
          type="number"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
          placeholder={placeholder}
          className={cn(
            'flex h-9 w-full rounded-lg border border-[var(--border)] bg-white px-3 py-1 text-sm text-[var(--foreground)] shadow-sm transition-colors',
            'placeholder:text-[var(--muted)]',
            'focus:outline-none focus:ring-2 focus:ring-primary-400 focus:border-transparent',
            prefix && 'pl-8',
            error && 'border-red-500'
          )}
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────

export default function NewListingPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [currentStep, setCurrentStep] = React.useState(0);
  const [photos, setPhotos] = React.useState<File[]>([]);
  const [floorPlans, setFloorPlans] = React.useState<File[]>([]);
  const [brochure, setBrochure] = React.useState<File[]>([]);
  const [createdListingId, setCreatedListingId] = React.useState<string | null>(null);
  const [kbIndexing, setKbIndexing] = React.useState(false);

  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ListingFormValues>({
    resolver: zodResolver(listingSchema),
    defaultValues: {
      status: 'active',
      facilities: [],
      selling_points: [],
      nearby_amenities: [],
    },
  });

  const formValues = watch();

  const createMutation = useMutation({
    mutationFn: (data: CreateListingInput) => api.listings.create(data),
    onSuccess: async (listing) => {
      setCreatedListingId(listing.id);

      // Upload media files
      if (photos.length > 0) {
        await api.listings.uploadFiles(listing.id, photos, 'photos').catch(() => {});
      }
      if (floorPlans.length > 0) {
        await api.listings.uploadFiles(listing.id, floorPlans, 'floor_plans').catch(() => {});
      }
      if (brochure.length > 0) {
        await api.listings.uploadFiles(listing.id, brochure, 'brochure').catch(() => {});
      }

      setKbIndexing(true);
      toast.success('Listing created! Knowledge base indexing started...');

      // Simulate KB indexing progress then redirect
      setTimeout(() => {
        setKbIndexing(false);
        router.push('/listings');
      }, 3000);
    },
    onError: () => toast.error('Failed to create listing'),
  });

  const onSubmit = (data: ListingFormValues) => {
    const payload: CreateListingInput = {
      property_name: data.property_name,
      address: data.address,
      property_type: data.property_type,
      tenure: data.tenure,
      developer: data.developer ?? null,
      status: data.status,
      price_min: data.price_min ?? null,
      price_max: data.price_max ?? null,
      price_per_sqft: data.price_per_sqft ?? null,
      available_units: data.available_units ?? null,
      payment_scheme: data.payment_scheme ?? null,
      promotions: data.promotions ?? null,
      bedrooms: data.bedrooms ?? null,
      bathrooms: data.bathrooms ?? null,
      land_area_sqft: data.land_area_sqft ?? null,
      built_up_sqft: data.built_up_sqft ?? null,
      furnishing: data.furnishing ?? null,
      facilities: data.facilities,
      selling_points: data.selling_points,
      target_buyer: data.target_buyer ?? null,
      nearby_amenities: data.nearby_amenities,
      investment_potential: data.investment_potential ?? null,
      video_url: data.video_url ?? null,
    };
    createMutation.mutate(payload);
  };

  const nextStep = () => setCurrentStep((s) => Math.min(s + 1, steps.length - 1));
  const prevStep = () => setCurrentStep((s) => Math.max(s - 1, 0));

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-xl font-bold text-[var(--foreground)]">Add New Listing</h1>
        <p className="text-sm text-[var(--muted)] mt-1">
          Fill in the details to add a property and start AI research
        </p>
      </div>

      {/* Progress indicator */}
      <div className="flex items-center gap-0 mb-10 overflow-x-auto pb-2">
        {steps.map((step, idx) => (
          <React.Fragment key={step.label}>
            <button
              type="button"
              onClick={() => setCurrentStep(idx)}
              className="flex flex-col items-center flex-shrink-0"
            >
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors',
                  idx < currentStep
                    ? 'bg-primary-500 text-white'
                    : idx === currentStep
                    ? 'bg-primary-500 text-white ring-4 ring-primary-100'
                    : 'bg-[var(--muted-bg)] text-[var(--muted)]'
                )}
              >
                {idx < currentStep ? <CheckCircle className="w-4 h-4" /> : idx + 1}
              </div>
              <span
                className={cn(
                  'text-xs mt-1.5 font-medium',
                  idx === currentStep ? 'text-primary-500' : 'text-[var(--muted)]'
                )}
              >
                {step.label}
              </span>
            </button>
            {idx < steps.length - 1 && (
              <div
                className={cn(
                  'flex-1 h-0.5 mx-2 min-w-[16px] transition-colors',
                  idx < currentStep ? 'bg-primary-400' : 'bg-[var(--border)]'
                )}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="bg-white rounded-2xl border border-[var(--border)] shadow-card p-6 min-h-[400px]">
          {/* ── Step 1: Basic Info ── */}
          {currentStep === 0 && (
            <div className="space-y-5">
              <h2 className="text-base font-semibold text-[var(--foreground)]">Basic Information</h2>
              <Input
                label="Property Name *"
                placeholder="e.g. The Pinnacle @ Duxton"
                error={errors.property_name?.message}
                {...register('property_name')}
              />
              <Input
                label="Address *"
                placeholder="e.g. 1 Cantonment Road, Singapore 085301"
                error={errors.address?.message}
                {...register('address')}
              />
              <div className="grid sm:grid-cols-2 gap-4">
                <Controller
                  name="property_type"
                  control={control}
                  render={({ field }) => (
                    <Select
                      label="Property Type *"
                      options={propertyTypeOptions}
                      value={field.value}
                      onValueChange={field.onChange}
                      error={errors.property_type?.message}
                    />
                  )}
                />
                <Controller
                  name="tenure"
                  control={control}
                  render={({ field }) => (
                    <Select
                      label="Tenure *"
                      options={tenureOptions}
                      value={field.value}
                      onValueChange={field.onChange}
                      error={errors.tenure?.message}
                    />
                  )}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="Developer (optional)"
                  placeholder="Developer name"
                  {...register('developer')}
                />
                <Controller
                  name="status"
                  control={control}
                  render={({ field }) => (
                    <Select
                      label="Status"
                      options={statusOptions}
                      value={field.value}
                      onValueChange={field.onChange}
                    />
                  )}
                />
              </div>
            </div>
          )}

          {/* ── Step 2: Pricing ── */}
          {currentStep === 1 && (
            <div className="space-y-5">
              <h2 className="text-base font-semibold text-[var(--foreground)]">Pricing & Units</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <Controller
                  name="price_min"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Price Minimum"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="800000"
                      prefix="RM"
                    />
                  )}
                />
                <Controller
                  name="price_max"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Price Maximum"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="1200000"
                      prefix="RM"
                    />
                  )}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Controller
                  name="price_per_sqft"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Price per sqft"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="650"
                      prefix="RM"
                    />
                  )}
                />
                <Controller
                  name="available_units"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Available Units"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="50"
                    />
                  )}
                />
              </div>
              <Textarea
                label="Payment Scheme"
                placeholder="e.g. 10/90, SPA-linked progressive payment..."
                {...register('payment_scheme')}
              />
              <Textarea
                label="Promotions & Incentives"
                placeholder="e.g. Free legal fees, stamp duty absorption..."
                {...register('promotions')}
              />
            </div>
          )}

          {/* ── Step 3: Property Details ── */}
          {currentStep === 2 && (
            <div className="space-y-5">
              <h2 className="text-base font-semibold text-[var(--foreground)]">Property Details</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <Controller
                  name="bedrooms"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Bedrooms"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="3"
                    />
                  )}
                />
                <Controller
                  name="bathrooms"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Bathrooms"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="2"
                    />
                  )}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Controller
                  name="land_area_sqft"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Land Area (sqft)"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="1200"
                    />
                  )}
                />
                <Controller
                  name="built_up_sqft"
                  control={control}
                  render={({ field }) => (
                    <NumberField
                      label="Built-Up (sqft)"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="1050"
                    />
                  )}
                />
              </div>
              <Controller
                name="furnishing"
                control={control}
                render={({ field }) => (
                  <Select
                    label="Furnishing"
                    options={furnishingOptions}
                    value={field.value ?? ''}
                    onValueChange={field.onChange}
                  />
                )}
              />
              <Controller
                name="facilities"
                control={control}
                render={({ field }) => (
                  <TagInput
                    label="Facilities"
                    value={field.value}
                    onChange={field.onChange}
                    placeholder="Swimming Pool, Gym, BBQ..."
                  />
                )}
              />
            </div>
          )}

          {/* ── Step 4: Media ── */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <h2 className="text-base font-semibold text-[var(--foreground)]">Media Upload</h2>
              <FileUpload
                label="Property Photos"
                description="Upload up to 20 photos. JPG, PNG, WebP supported."
                accept={{ 'image/*': ['.jpg', '.jpeg', '.png', '.webp'] }}
                maxFiles={20}
                onFilesChange={setPhotos}
              />
              <FileUpload
                label="Floor Plans"
                description="Upload floor plan images or PDF."
                accept={{ 'image/*': ['.jpg', '.jpeg', '.png'], 'application/pdf': ['.pdf'] }}
                maxFiles={5}
                onFilesChange={setFloorPlans}
              />
              <FileUpload
                label="Brochure (PDF)"
                description="Upload a single brochure PDF."
                accept={{ 'application/pdf': ['.pdf'] }}
                maxFiles={1}
                multiple={false}
                onFilesChange={setBrochure}
              />
              <Input
                label="Video URL (YouTube / Vimeo / TikTok)"
                placeholder="https://youtube.com/watch?v=..."
                {...register('video_url')}
              />
            </div>
          )}

          {/* ── Step 5: Marketing ── */}
          {currentStep === 4 && (
            <div className="space-y-5">
              <h2 className="text-base font-semibold text-[var(--foreground)]">Marketing Info</h2>
              <Controller
                name="selling_points"
                control={control}
                render={({ field }) => (
                  <TagInput
                    label="Selling Points"
                    value={field.value}
                    onChange={field.onChange}
                    placeholder="Freehold, City view, Near MRT..."
                  />
                )}
              />
              <Textarea
                label="Target Buyer"
                placeholder="Describe the ideal buyer for this property..."
                {...register('target_buyer')}
              />
              <Controller
                name="nearby_amenities"
                control={control}
                render={({ field }) => (
                  <TagInput
                    label="Nearby Amenities"
                    value={field.value}
                    onChange={field.onChange}
                    placeholder="KLCC, LRT station, International school..."
                  />
                )}
              />
              <Textarea
                label="Investment Potential"
                placeholder="Rental yield estimates, capital appreciation outlook..."
                {...register('investment_potential')}
              />
            </div>
          )}

          {/* ── Step 6: Review ── */}
          {currentStep === 5 && (
            <div className="space-y-6">
              <h2 className="text-base font-semibold text-[var(--foreground)]">Review & Submit</h2>

              {kbIndexing && (
                <div className="rounded-xl bg-primary-50 border border-primary-200 p-4 flex items-center gap-3">
                  <div className="w-5 h-5 border-2 border-primary-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-primary-700">Indexing to Knowledge Base...</p>
                    <p className="text-xs text-primary-500">Your AI agents are processing this listing</p>
                  </div>
                </div>
              )}

              <div className="grid sm:grid-cols-2 gap-4 text-sm">
                <ReviewRow label="Property Name" value={formValues.property_name} />
                <ReviewRow label="Address" value={formValues.address} />
                <ReviewRow label="Type" value={formValues.property_type} />
                <ReviewRow label="Tenure" value={formValues.tenure} />
                <ReviewRow
                  label="Price Range"
                  value={
                    formValues.price_min || formValues.price_max
                      ? `RM ${formValues.price_min?.toLocaleString() ?? '—'} – RM ${formValues.price_max?.toLocaleString() ?? '—'}`
                      : null
                  }
                />
                <ReviewRow label="Bedrooms" value={formValues.bedrooms?.toString()} />
                <ReviewRow label="Bathrooms" value={formValues.bathrooms?.toString()} />
                <ReviewRow label="Built-Up" value={formValues.built_up_sqft ? `${formValues.built_up_sqft} sqft` : null} />
                <ReviewRow label="Status" value={formValues.status} />
                <ReviewRow label="Furnishing" value={formValues.furnishing} />
              </div>

              {formValues.facilities.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-2">
                    Facilities
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {formValues.facilities.map((f) => (
                      <span key={f} className="text-xs bg-primary-100 text-primary-700 px-2.5 py-1 rounded-md">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 text-sm text-[var(--muted)]">
                <span>{photos.length} photos</span>
                <span>·</span>
                <span>{floorPlans.length} floor plans</span>
                <span>·</span>
                <span>{brochure.length} brochure</span>
              </div>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="flex items-center justify-between mt-6">
          <Button
            type="button"
            variant="outline"
            onClick={prevStep}
            disabled={currentStep === 0}
            className="gap-2"
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </Button>

          {currentStep < steps.length - 1 ? (
            <Button type="button" onClick={nextStep} className="gap-2">
              Next
              <ChevronRight className="w-4 h-4" />
            </Button>
          ) : (
            <Button
              type="submit"
              loading={createMutation.isPending || kbIndexing}
              className="gap-2 min-w-[200px]"
            >
              Create Listing & Start Research
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="bg-[var(--muted-bg)] rounded-lg p-3">
      <p className="text-xs text-[var(--muted)] mb-0.5">{label}</p>
      <p className="font-medium text-[var(--foreground)] capitalize">{value || '—'}</p>
    </div>
  );
}
