/**
 * GYMBro In-Chat Native Interactive Chart & Action Widget Protocol (gymbro.widget/v1)
 * TypeScript interfaces and schema validators for Expo client.
 */

export const GYMBRO_WIDGET_PROTOCOL = 'gymbro.widget/v1' as const;

export type WidgetType =
  | 'interactive_chart'
  | 'calendar_proposal'
  | 'macro_slider'
  | 'readiness_action'
  | 'session_editor';

export type WidgetState =
  | 'proposed'
  | 'active'
  | 'confirmed'
  | 'executed'
  | 'dismissed'
  | 'error';

export type ActionStyle = 'primary' | 'secondary' | 'ghost' | 'danger' | 'vitality';
export type ActionType = 'api_call' | 'client_mutation' | 'prompt_trigger';

export interface WidgetAction {
  id: string;
  label: string;
  style?: ActionStyle;
  action_type: ActionType;
  endpoint?: string;
  method?: 'POST' | 'PUT' | 'DELETE';
  payload?: Record<string, any>;
  prompt_text?: string;
  confirmation_message?: string;
}

export interface WidgetTelemetryPoint {
  date: string;
  label?: string;
  values: Record<string, number | null | undefined>;
  annotation?: string;
  flag?: 'optimal' | 'warning' | 'alert' | 'pr';
}

export interface InteractiveChartPayload {
  chart_id: string;
  title?: string;
  subtitle?: string;
  time_range: '7d' | '14d' | '30d' | '90d' | '1y';
  metrics: {
    key: string;
    label: string;
    unit: string;
    color: string;
    y_axis: 'left' | 'right';
    chart_type: 'line' | 'bar' | 'area';
    min?: number;
    max?: number;
    baseline?: number;
  }[];
  points: WidgetTelemetryPoint[];
  summary_insight?: string;
  interactive_scrubbing: boolean;
}

export interface CalendarSessionItem {
  day_name: string;
  title: string;
  tag: string;
  duration: number;
  distance?: number;
  description?: string;
}

export interface CalendarProposalPayload {
  horizon: 'micro' | 'meso' | 'macro';
  target_volume_km?: number;
  total_sessions: number;
  sessions: CalendarSessionItem[];
}

export interface MacroPreset {
  id: string;
  name: string;
  protein_g: number;
  carbs_g: number;
  fats_g: number;
  ratio_label: string;
}

export interface MacroSliderPayload {
  goal_type: 'endurance' | 'recomp' | 'hypertrophy' | 'cutting' | 'custom';
  target_weight_kg?: number;
  protein_g: number;
  carbs_g: number;
  fats_g: number;
  presets: MacroPreset[];
}

export interface ReadinessActionPayload {
  readiness_score: number;
  hrv_anomaly_pct: number;
  sleep_score: number;
  recommendation: string;
  original_session: {
    title: string;
    duration: number;
    intensity: string;
  };
  suggested_session: {
    title: string;
    duration: number;
    intensity: string;
  };
}

export interface ChatWidgetEnvelope<T = any> {
  protocol: typeof GYMBRO_WIDGET_PROTOCOL;
  widget_id: string;
  widget_type: WidgetType;
  title: string;
  subtitle?: string;
  state: WidgetState;
  payload: T;
  actions: WidgetAction[];
  emitted_at: string;
  last_action_result?: string;
}

/**
 * Checks whether an incoming UI payload adheres to gymbro.widget/v1
 */
export function isGymbroWidget(payload: any): payload is ChatWidgetEnvelope {
  return (
    payload &&
    typeof payload === 'object' &&
    (payload.protocol === GYMBRO_WIDGET_PROTOCOL ||
      ['interactive_chart', 'calendar_proposal', 'macro_slider', 'readiness_action'].includes(
        payload.widget_type
      ))
  );
}
