import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { AuthContext } from '../../context/AuthContext';
import Colors from '../../constants/Colors';
import { DEFAULT_COACH_NAME, resolveCoachName } from '../../constants/coach';

type CalendarEvent = {
  id: number;
  date: string;
  title: string;
  description?: string;
  event_type?: string;
  status?: 'planned' | 'completed' | 'skipped' | string;
};

type WellnessSnapshot = {
  sleep?: number | null;
  sleepHours?: number | null;
  hrv?: number | null;
  rhr?: number | null;
  bodyBattery?: number | null;
  recoveryScore?: number | null;
  source?: string | null;
};

function todayISO(): string {
  return new Date().toISOString().split('T')[0];
}

function addDaysISO(base: string, days: number): string {
  const d = new Date(`${base}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().split('T')[0];
}

function formatDayLabel(dateStr: string, today: string): string {
  if (dateStr === today) return 'Today';
  if (dateStr === addDaysISO(today, 1)) return 'Tomorrow';
  const d = new Date(`${dateStr}T12:00:00`);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

function computeReadiness(w: WellnessSnapshot): { score: number | null; label: string; tone: string } {
  const parts: number[] = [];
  if (typeof w.recoveryScore === 'number') parts.push(Math.min(100, Math.max(0, w.recoveryScore)));
  if (typeof w.bodyBattery === 'number') parts.push(Math.min(100, Math.max(0, w.bodyBattery)));
  if (typeof w.sleep === 'number') parts.push(Math.min(100, Math.max(0, w.sleep)));
  if (typeof w.hrv === 'number') {
    // Map typical HRV ms into a soft 0–100 readiness contribution
    parts.push(Math.min(100, Math.max(20, Math.round((w.hrv / 80) * 100))));
  }
  if (parts.length === 0) {
    return { score: null, label: 'Connect a wearable for readiness', tone: Colors.light.mutedText };
  }
  const score = Math.round(parts.reduce((a, b) => a + b, 0) / parts.length);
  if (score >= 75) return { score, label: 'Ready to train', tone: Colors.light.vitality };
  if (score >= 55) return { score, label: 'Steady — listen to the plan', tone: Colors.light.primary };
  return { score, label: 'Prioritize recovery today', tone: Colors.light.warning };
}

function buildMorningBriefing(
  readiness: { score: number | null; label: string },
  wellness: WellnessSnapshot,
  todayEvents: CalendarEvent[],
  coachName: string
): string {
  const bits: string[] = [];
  if (readiness.score != null) {
    bits.push(`Readiness is ${readiness.score}/100 — ${readiness.label.toLowerCase()}.`);
  } else {
    bits.push(`${coachName} is waiting on fresh biometrics. Sync Garmin or log a journal check-in.`);
  }
  if (wellness.sleepHours != null) {
    bits.push(`Sleep ${wellness.sleepHours}h${wellness.sleep != null ? ` (score ${wellness.sleep})` : ''}.`);
  } else if (wellness.sleep != null) {
    bits.push(`Sleep score ${wellness.sleep}.`);
  }
  if (wellness.hrv != null) bits.push(`HRV ${wellness.hrv} ms.`);
  if (wellness.rhr != null) bits.push(`RHR ${wellness.rhr} bpm.`);

  const planned = todayEvents.filter((e) => e.status !== 'skipped');
  if (planned.length === 0) {
    bits.push('No Calendar Sessions on the Daily Horizon yet — open Training to schedule or generate a plan.');
  } else {
    const titles = planned.map((e) => e.title).slice(0, 2).join(', ');
    bits.push(
      planned.length === 1
        ? `On deck: ${titles}.`
        : `${planned.length} sessions today, starting with ${titles}.`
    );
  }
  return bits.join(' ');
}

export default function TodayScreen() {
  const router = useRouter();
  const { authToken, apiUrl, user } = useContext(AuthContext);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [wellness, setWellness] = useState<WellnessSnapshot>({});
  const [coachName, setCoachName] = useState(DEFAULT_COACH_NAME);

  const today = useMemo(() => todayISO(), []);

  const load = useCallback(async () => {
    if (!authToken) {
      setLoading(false);
      return;
    }
    try {
      const [calRes, analyticsRes, profileRes] = await Promise.all([
        fetch(`${apiUrl}/calendar/events`, {
          headers: { Authorization: `Bearer ${authToken}` },
        }),
        fetch(`${apiUrl}/analytics/summary?days=7`, {
          headers: { Authorization: `Bearer ${authToken}` },
        }),
        fetch(`${apiUrl}/auth/profile`, {
          headers: { Authorization: `Bearer ${authToken}` },
        }),
      ]);

      if (calRes.ok) {
        const data = await calRes.json();
        setEvents(data.events || []);
      }

      if (analyticsRes.ok) {
        const data = await analyticsRes.json();
        const w = data.wellness || {};
        const last = (arr: any[] | undefined) =>
          Array.isArray(arr) && arr.length > 0 ? arr[arr.length - 1] : null;
        const sleepPt = last(w.sleep_trend);
        const hrvPt = last(w.hrv_trend);
        const rhrPt = last(w.rhr_trend);
        const bbPt = last(w.body_battery_trend);
        const recPt = last(w.recovery_trend);
        setWellness({
          sleep: sleepPt?.val ?? null,
          sleepHours: sleepPt?.hours ?? null,
          hrv: hrvPt?.val ?? null,
          rhr: rhrPt?.val ?? null,
          bodyBattery: bbPt?.val ?? null,
          recoveryScore: recPt?.val ?? sleepPt?.val ?? null,
          source: w.primary_source || null,
        });
      }

      if (profileRes.ok) {
        const data = await profileRes.json();
        const goals = data.profile?.goals || data.user?.goals || {};
        setCoachName(resolveCoachName(goals));
      } else if (user?.goals) {
        setCoachName(resolveCoachName(user.goals as any));
      }
    } catch (err) {
      console.error('[Today] load failed:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [authToken, apiUrl, user]);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const readiness = useMemo(() => computeReadiness(wellness), [wellness]);

  const todayEvents = useMemo(
    () => events.filter((e) => e.date === today).sort((a, b) => a.id - b.id),
    [events, today]
  );

  const lookAhead = useMemo(() => {
    const end = addDaysISO(today, 3);
    return events
      .filter((e) => e.date > today && e.date <= end)
      .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.id - b.id));
  }, [events, today]);

  const briefing = useMemo(
    () => buildMorningBriefing(readiness, wellness, todayEvents, coachName),
    [readiness, wellness, todayEvents, coachName]
  );

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    const hello = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
    const name = user?.name?.split(' ')[0];
    return name ? `${hello}, ${name}` : hello;
  }, [user?.name]);

  const dateLine = useMemo(
    () =>
      new Date().toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
      }),
    []
  );

  const quickActions = [
    {
      key: 'meal',
      label: 'Log meal',
      icon: 'restaurant-outline' as const,
      route: '/(tabs)/nutrition' as const,
    },
    {
      key: 'journal',
      label: 'Journal',
      icon: 'book-outline' as const,
      route: '/(tabs)/recovery' as const,
    },
    {
      key: 'coach',
      label: `Ask ${coachName}`,
      icon: 'chatbubbles-outline' as const,
      route: '/(tabs)/coach' as const,
    },
    {
      key: 'session',
      label: 'Training',
      icon: 'barbell-outline' as const,
      route: '/(tabs)/training' as const,
    },
  ];

  const eventIcon = (type?: string) => {
    switch (type) {
      case 'run':
        return 'walk-outline' as const;
      case 'strength':
        return 'barbell-outline' as const;
      case 'rest':
        return 'moon-outline' as const;
      case 'race':
        return 'trophy-outline' as const;
      default:
        return 'calendar-outline' as const;
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.light.primary} />
      }
    >
      <View style={styles.hero}>
        <Text style={styles.dateLine}>{dateLine}</Text>
        <Text style={styles.greeting}>{greeting}</Text>
        <Text style={styles.heroSub}>Your Daily Horizon at a glance</Text>
      </View>

      {/* Readiness */}
      <LinearGradient
        colors={[Colors.light.primaryLight, Colors.light.vitalityLight]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.readinessCard}
      >
        <View style={styles.readinessTop}>
          <View>
            <Text style={styles.sectionEyebrow}>Readiness</Text>
            <Text style={[styles.readinessLabel, { color: readiness.tone }]}>{readiness.label}</Text>
          </View>
          <View style={styles.scoreRing}>
            <Text style={styles.scoreValue}>{readiness.score != null ? readiness.score : '—'}</Text>
            {readiness.score != null && <Text style={styles.scoreUnit}>/100</Text>}
          </View>
        </View>
        <View style={styles.metricRow}>
          <MetricChip label="Sleep" value={wellness.sleep != null ? String(wellness.sleep) : '—'} />
          <MetricChip label="HRV" value={wellness.hrv != null ? `${wellness.hrv}` : '—'} />
          <MetricChip label="RHR" value={wellness.rhr != null ? `${wellness.rhr}` : '—'} />
          <MetricChip
            label="Battery"
            value={wellness.bodyBattery != null ? String(wellness.bodyBattery) : '—'}
          />
        </View>
        {wellness.source ? (
          <Text style={styles.sourceHint}>Telemetry · {wellness.source}</Text>
        ) : (
          <TouchableOpacity onPress={() => router.push('/(tabs)/analytics')}>
            <Text style={styles.sourceLink}>Connect Garmin in Analytics →</Text>
          </TouchableOpacity>
        )}
      </LinearGradient>

      {/* Morning briefing */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Ionicons name="sunny-outline" size={18} color={Colors.light.primary} />
          <Text style={styles.sectionTitle}>Morning briefing</Text>
        </View>
        <Text style={styles.briefingText}>{briefing}</Text>
        <TouchableOpacity style={styles.briefingCta} onPress={() => router.push('/(tabs)/coach')}>
          <Text style={styles.briefingCtaText}>Continue with {coachName}</Text>
          <Ionicons name="arrow-forward" size={16} color={Colors.light.primary} />
        </TouchableOpacity>
      </View>

      {/* Quick actions */}
      <View style={styles.section}>
        <Text style={styles.sectionTitleSolo}>Quick actions</Text>
        <View style={styles.actionsGrid}>
          {quickActions.map((action) => (
            <TouchableOpacity
              key={action.key}
              style={styles.actionBtn}
              onPress={() => router.push(action.route)}
              activeOpacity={0.85}
            >
              <View style={styles.actionIcon}>
                <Ionicons name={action.icon} size={20} color={Colors.light.secondary} />
              </View>
              <Text style={styles.actionLabel} numberOfLines={1}>
                {action.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Today's sessions */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Ionicons name="calendar-outline" size={18} color={Colors.light.secondary} />
          <Text style={styles.sectionTitle}>Scheduled today</Text>
          <TouchableOpacity onPress={() => router.push('/(tabs)/training')} style={styles.seeAll}>
            <Text style={styles.seeAllText}>Training</Text>
          </TouchableOpacity>
        </View>
        {todayEvents.length === 0 ? (
          <View style={styles.emptyBlock}>
            <Text style={styles.emptyText}>No Calendar Sessions for today.</Text>
            <TouchableOpacity style={styles.emptyBtn} onPress={() => router.push('/(tabs)/training')}>
              <Text style={styles.emptyBtnText}>Open Training calendar</Text>
            </TouchableOpacity>
          </View>
        ) : (
          todayEvents.map((ev) => (
            <TouchableOpacity
              key={ev.id}
              style={styles.sessionRow}
              onPress={() => router.push('/(tabs)/training')}
              activeOpacity={0.85}
            >
              <View style={styles.sessionIcon}>
                <Ionicons name={eventIcon(ev.event_type)} size={18} color={Colors.light.primary} />
              </View>
              <View style={styles.sessionBody}>
                <Text style={styles.sessionTitle}>{ev.title}</Text>
                {!!ev.description && (
                  <Text style={styles.sessionDesc} numberOfLines={2}>
                    {ev.description}
                  </Text>
                )}
              </View>
              <Text style={styles.sessionStatus}>{ev.status || 'planned'}</Text>
            </TouchableOpacity>
          ))
        )}
      </View>

      {/* Look-ahead */}
      <View style={[styles.section, styles.lastSection]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="eye-outline" size={18} color={Colors.light.secondary} />
          <Text style={styles.sectionTitle}>Next 3 days</Text>
        </View>
        {lookAhead.length === 0 ? (
          <Text style={styles.emptyText}>Nothing scheduled ahead — generate a Micro Horizon in Coach.</Text>
        ) : (
          lookAhead.map((ev) => (
            <View key={`${ev.id}-${ev.date}`} style={styles.lookRow}>
              <Text style={styles.lookDay}>{formatDayLabel(ev.date, today)}</Text>
              <Text style={styles.lookTitle} numberOfLines={1}>
                {ev.title}
              </Text>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.chip}>
      <Text style={styles.chipLabel}>{label}</Text>
      <Text style={styles.chipValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  content: {
    paddingBottom: 32,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.light.background,
  },
  hero: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 16,
  },
  dateLine: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.light.secondaryText,
    letterSpacing: 0.2,
    marginBottom: 4,
  },
  greeting: {
    fontSize: 28,
    fontWeight: '800',
    color: Colors.light.text,
    letterSpacing: -0.6,
  },
  heroSub: {
    marginTop: 4,
    fontSize: 14,
    color: Colors.light.secondaryText,
  },
  readinessCard: {
    marginHorizontal: 16,
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
  },
  readinessTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  sectionEyebrow: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.light.secondaryText,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  readinessLabel: {
    fontSize: 16,
    fontWeight: '700',
    maxWidth: 200,
  },
  scoreRing: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: Colors.light.card,
    borderWidth: 2,
    borderColor: Colors.light.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreValue: {
    fontSize: 24,
    fontWeight: '800',
    color: Colors.light.text,
  },
  scoreUnit: {
    fontSize: 10,
    color: Colors.light.mutedText,
    marginTop: -2,
  },
  metricRow: {
    flexDirection: 'row',
    gap: 8,
  },
  chip: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.72)',
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 6,
    alignItems: 'center',
  },
  chipLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: Colors.light.secondaryText,
    marginBottom: 2,
  },
  chipValue: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.light.text,
  },
  sourceHint: {
    marginTop: 10,
    fontSize: 11,
    color: Colors.light.secondaryText,
  },
  sourceLink: {
    marginTop: 10,
    fontSize: 12,
    fontWeight: '600',
    color: Colors.light.primary,
  },
  section: {
    marginTop: 22,
    marginHorizontal: 16,
    backgroundColor: Colors.light.card,
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
  },
  lastSection: {
    marginBottom: 12,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  sectionTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '700',
    color: Colors.light.text,
  },
  sectionTitleSolo: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.light.text,
    marginBottom: 12,
  },
  briefingText: {
    fontSize: 15,
    lineHeight: 22,
    color: Colors.light.text,
  },
  briefingCta: {
    marginTop: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  briefingCtaText: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.light.primary,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  actionBtn: {
    width: '47%',
    flexGrow: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 14,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
  },
  actionIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: Colors.light.vitalityLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionLabel: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    color: Colors.light.text,
  },
  seeAll: {
    paddingHorizontal: 4,
    paddingVertical: 2,
  },
  seeAllText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.light.primary,
  },
  emptyBlock: {
    paddingVertical: 8,
  },
  emptyText: {
    fontSize: 14,
    color: Colors.light.secondaryText,
    lineHeight: 20,
  },
  emptyBtn: {
    marginTop: 12,
    alignSelf: 'flex-start',
    backgroundColor: Colors.light.primary,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  emptyBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.light.borderSubtle,
    gap: 10,
  },
  sessionIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: Colors.light.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sessionBody: {
    flex: 1,
  },
  sessionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: Colors.light.text,
  },
  sessionDesc: {
    fontSize: 12,
    color: Colors.light.secondaryText,
    marginTop: 2,
  },
  sessionStatus: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.light.mutedText,
    textTransform: 'capitalize',
  },
  lookRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.light.borderSubtle,
  },
  lookDay: {
    width: 88,
    fontSize: 12,
    fontWeight: '700',
    color: Colors.light.secondary,
  },
  lookTitle: {
    flex: 1,
    fontSize: 14,
    color: Colors.light.text,
    fontWeight: '500',
  },
});
