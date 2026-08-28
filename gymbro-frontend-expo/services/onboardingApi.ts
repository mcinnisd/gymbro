/**
 * GYMBro Onboarding REST API Client.
 * Interfaces with backend /onboarding state machine routes.
 */

import { apiFetch } from './api';

export interface AthleteProfile {
  age?: number | null;
  weight?: number | null;
  height?: number | null;
  biological_sex?: string | null;
  sport_history?: string | null;
  running_experience?: string | null;
  past_injuries?: string | null;
  lifestyle?: string | null;
  weekly_availability?: string | null;
  terrain_preference?: string | null;
  equipment?: string | null;
}

export interface PrepopulatedBiometrics {
  data_available: boolean;
  age?: number | null;
  weight?: number | null;
  height?: number | null;
  biological_sex?: string | null;
  sport_history?: string;
  running_experience?: string;
  resting_hr?: number;
  hrv?: number | null;
  hrv_ms?: number | null;
  sleep_hours?: number;
  weekly_volume?: number;
  acute_weekly_volume_km?: number;
  connected_providers?: string[];
  personal_records?: {
    run_5k?: string | null;
    run_10k?: string | null;
    run_half?: string | null;
    bike_longest?: string | null;
    swim_100m?: string | null;
    hike_peak?: string | null;
  };
}

export interface GoalSetDraft {
  primary_goal: string;
  secondary_goals?: string[];
  days_available: string[];
  target_date?: string | null;
  target_race?: string | null;
  horizon?: string;
  units?: string;
  llm_model?: string;
  equipment?: string;
}

export interface DataRealityCheck {
  status: 'aligned' | 'caution' | 'ramp_needed';
  historical_weekly_volume_km: number;
  target_weekly_volume_km: number;
  feedback: string;
  recommendation: string;
}

export interface OnboardingStateResponse {
  user_id: number;
  step: number;
  coach_status: 'not_started' | 'in_onboarding' | 'active' | string;
  is_completed: boolean;
  athlete_profile: AthleteProfile;
  prepopulated_biometrics: PrepopulatedBiometrics;
  goal_set: GoalSetDraft;
  reality_check: DataRealityCheck;
  proposal?: any;
}

export interface StepSaveResponse {
  success: boolean;
  current_step: number;
  coach_status: string;
  data: Record<string, any>;
}

export interface CommitResponse {
  success: boolean;
  coach_status: 'active';
  events_created: number;
  welcome_briefing: string;
  first_session: {
    title: string;
    description: string;
  };
  plan_name?: string;
}

export async function fetchOnboardingState(): Promise<OnboardingStateResponse> {
  const res = await apiFetch('/onboarding/state', { method: 'GET' });
  if (!res.ok) {
    throw new Error(`Failed to fetch onboarding state: ${res.statusText}`);
  }
  return res.json();
}

export async function saveOnboardingStep(
  step: number,
  data: Record<string, any>,
  nextStep?: number
): Promise<StepSaveResponse> {
  const res = await apiFetch('/onboarding/step', {
    method: 'POST',
    body: JSON.stringify({
      step,
      data,
      next_step: nextStep,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to save onboarding step ${step}: ${res.statusText}`);
  }
  return res.json();
}

export async function prepopulateTelemetry(
  rawPayload?: Record<string, any>
): Promise<PrepopulatedBiometrics> {
  const res = await apiFetch('/onboarding/prepopulate', {
    method: 'POST',
    body: JSON.stringify(rawPayload || {}),
  });
  if (!res.ok) {
    throw new Error(`Failed to prepopulate telemetry: ${res.statusText}`);
  }
  return res.json();
}

export async function generateOnboardingProposal(
  horizon: string = '4_week_foundation',
  customNotes?: string
): Promise<{ proposal: any; widget: any; reality_check: DataRealityCheck }> {
  const res = await apiFetch('/onboarding/generate-proposal', {
    method: 'POST',
    body: JSON.stringify({
      horizon,
      custom_notes: customNotes,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to generate proposal: ${res.statusText}`);
  }
  return res.json();
}

export async function commitOnboarding(proposal?: any): Promise<CommitResponse> {
  const res = await apiFetch('/onboarding/commit', {
    method: 'POST',
    body: JSON.stringify({ proposal }),
  });
  if (!res.ok) {
    throw new Error(`Failed to commit onboarding: ${res.statusText}`);
  }
  return res.json();
}
