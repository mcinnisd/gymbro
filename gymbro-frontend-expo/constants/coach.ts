/**
 * Coach display name helpers.
 * Default: "Coach". Persisted as goals.coach_name via /auth/profile.
 */

export const DEFAULT_COACH_NAME = 'Coach';

export function resolveCoachName(goals?: Record<string, any> | null): string {
  const raw = goals?.coach_name;
  if (typeof raw === 'string' && raw.trim().length > 0) {
    return raw.trim().slice(0, 32);
  }
  return DEFAULT_COACH_NAME;
}
