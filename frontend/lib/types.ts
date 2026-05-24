// ─── Lead Types ─────────────────────────────────────────────────────────────

export type LeadStatus =
  | 'new'
  | 'warm'
  | 'hot'
  | 'viewing_scheduled'
  | 'offer'
  | 'closed'
  | 'lost';

export type LeadTemperature = 'cold' | 'warm' | 'hot';

export type ContactChannel = 'whatsapp' | 'email' | 'phone' | 'social';

export interface LeadMessage {
  id: string;
  direction: 'inbound' | 'outbound';
  channel: ContactChannel;
  content: string;
  timestamp: string;
  read: boolean;
}

export interface Lead {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  status: LeadStatus;
  temperature: LeadTemperature;
  property_interest: string | null;
  budget_min: number | null;
  budget_max: number | null;
  preferred_location: string | null;
  preferred_bedrooms: number | null;
  source: string | null;
  assigned_listing_id: string | null;
  last_contact_at: string | null;
  next_follow_up_at: string | null;
  notes: string | null;
  messages: LeadMessage[];
  created_at: string;
  updated_at: string;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ─── Listing Types ───────────────────────────────────────────────────────────

export type PropertyType = 'condo' | 'landed' | 'commercial';
export type TenureType = 'freehold' | 'leasehold';
export type ListingStatus = 'active' | 'sold' | 'withdrawn';
export type FurnishingType = 'unfurnished' | 'partly' | 'fully';

export interface ListingMedia {
  id: string;
  type: 'photo' | 'floor_plan' | 'brochure' | 'video';
  url: string;
  filename: string;
  is_primary: boolean;
}

export interface Listing {
  id: string;
  property_name: string;
  address: string;
  property_type: PropertyType;
  tenure: TenureType;
  developer: string | null;
  status: ListingStatus;
  price_min: number | null;
  price_max: number | null;
  price_per_sqft: number | null;
  available_units: number | null;
  payment_scheme: string | null;
  promotions: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  land_area_sqft: number | null;
  built_up_sqft: number | null;
  furnishing: FurnishingType | null;
  facilities: string[];
  selling_points: string[];
  target_buyer: string | null;
  nearby_amenities: string[];
  investment_potential: string | null;
  video_url: string | null;
  media: ListingMedia[];
  kb_indexed: boolean;
  kb_indexed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ListingListResponse {
  items: Listing[];
  total: number;
}

export type CreateListingInput = Omit<
  Listing,
  'id' | 'media' | 'kb_indexed' | 'kb_indexed_at' | 'created_at' | 'updated_at'
>;

// ─── Content Draft / Approval Types ─────────────────────────────────────────

export type ContentType = 'email' | 'instagram' | 'whatsapp' | 'facebook' | 'tiktok';
export type DraftStatus = 'pending' | 'approved' | 'rejected' | 'changes_requested';

export interface ContentDraft {
  id: string;
  type: ContentType;
  status: DraftStatus;
  subject: string | null;
  body: string;
  image_url: string | null;
  listing_id: string | null;
  listing_name: string | null;
  agent_name: string;
  generated_at: string;
  scheduled_for: string | null;
  reviewer_notes: string | null;
}

// ─── Agent Action Types ──────────────────────────────────────────────────────

export type AgentActionStatus = 'success' | 'pending' | 'failed' | 'running';

export type AgentName =
  | 'FrontDeskAgent'
  | 'ResearchAgent'
  | 'MarketingAgent'
  | 'NurturingAgent'
  | 'EscalationAgent'
  | 'BriefingAgent';

export interface AgentAction {
  id: string;
  agent: AgentName;
  action: string;
  description: string;
  status: AgentActionStatus;
  lead_id: string | null;
  listing_id: string | null;
  draft_id: string | null;
  metadata: Record<string, unknown>;
  timestamp: string;
  duration_ms: number | null;
}

export interface AgentActionListResponse {
  items: AgentAction[];
  total: number;
  page: number;
}

export interface AgentStatusResponse {
  agents: {
    name: AgentName;
    status: 'idle' | 'running' | 'error';
    last_run: string | null;
    runs_today: number;
  }[];
  pending_approvals: number;
  active_leads: number;
}

// ─── Settings Types ──────────────────────────────────────────────────────────

export type BrandVoice = 'formal' | 'friendly' | 'luxury';
export type Vertical = 'real_estate' | 'consultant' | 'recruiter';
export type PreferredChannel = 'whatsapp' | 'email';

export interface CompanyProfile {
  company_name: string;
  tagline: string | null;
  owner_name: string;
  phone: string;
  email: string;
  office_address: string | null;
  license_number: string | null;
  brand_voice: BrandVoice;
  instagram_url: string | null;
  facebook_url: string | null;
  tiktok_url: string | null;
  linkedin_url: string | null;
  logo_url: string | null;
  vertical: Vertical;
}

export interface FollowUpStage {
  label: string;
  intervals_days: number[];
}

export interface ViewingWindow {
  enabled: boolean;
  start: string;
  end: string;
}

export interface BusinessRules {
  questions_to_ask: string[];
  things_never_promise: string;
  escalation_triggers: string[];
  follow_up_stages: FollowUpStage[];
  preferred_channel: PreferredChannel;
  viewing_availability: {
    weekdays: ViewingWindow;
    saturday: ViewingWindow;
    sunday: ViewingWindow;
  };
  compliance_notes: string | null;
}

// ─── Dashboard Stats ─────────────────────────────────────────────────────────

export interface DashboardStats {
  new_leads_today: number;
  new_leads_trend: number;
  pending_approvals: number;
  active_listings: number;
  hot_leads: number;
  hot_leads_trend: number;
}

// ─── Integration Types ───────────────────────────────────────────────────────

export interface Integration {
  id: string;
  type: 'gmail' | 'whatsapp' | 'google_calendar' | 'instagram' | 'facebook';
  connected: boolean;
  account_identifier: string | null;
  connected_at: string | null;
}

// ─── Content Calendar ────────────────────────────────────────────────────────

export interface ContentPost {
  id: string;
  platform: ContentType;
  caption: string;
  image_url: string | null;
  listing_id: string | null;
  listing_name: string | null;
  scheduled_at: string;
  published_at: string | null;
  status: 'scheduled' | 'published' | 'failed';
  likes: number | null;
  reach: number | null;
  comments: number | null;
}
