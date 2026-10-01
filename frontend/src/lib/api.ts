/**
 * Typed API Client for RecruitRadar Backend
 */

export interface Role {
  id: string;
  title: string;
  jd_version: number;
  created_at: string;
}

export interface Candidate {
  id: string;
  display_alias: string;
  role_id: string;
  status: string;
  created_at: string;
}

export interface RequirementMatch {
  requirement_id: string;
  status: 'MET' | 'PARTIAL' | 'UNCERTAIN' | 'MISSING';
  strength: number;
  evidence_ids: string[];
}

export interface NoiseFlag {
  type: string;
  severity: 'LOW' | 'MED' | 'HIGH';
  detail: string;
  dismissed?: boolean;
}

export interface ShortlistEntry {
  rank: number;
  candidate_id: string;
  display_alias: string;
  fit_score: number;
  confidence: number;
  confidence_label: string;
  rationale: string;
  matches: RequirementMatch[];
  noise_flags: NoiseFlag[];
  gaps: Array<{ requirement_id: string; status: string; suggested_probe: string }>;
}

export interface EvidenceItem {
  id: string;
  skill_id: string;
  quote: string;
  grade: 'listed' | 'contextual' | 'demonstrated' | 'outcome_backed';
  role_ref?: string;
  duration_months?: number;
  last_used?: string;
  outcome_text?: string;
  verified: boolean;
  span_start: number;
  span_end: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function fetchWithAuth<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('rr_token') : null;
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error?.message || err.detail || 'API request failed');
  }
  return res.json();
}
