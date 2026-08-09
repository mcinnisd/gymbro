import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

export type MetricType = 'sleep' | 'hrv' | 'rhr' | 'load';

export interface RecoveryDataPoint {
  date: string;
  dayLabel?: string;
  sleep?: number;
  sleepHours?: number;
  hrv?: number;
  rhr?: number;
  load?: number;
}

interface RecoveryChartProps {
  dataPoints: RecoveryDataPoint[];
  onConsultCoach?: (summaryText: string) => void;
}

export default function RecoveryChart({ dataPoints, onConsultCoach }: RecoveryChartProps) {
  const router = useRouter();

  // Active layered metrics state
  const [activeMetrics, setActiveMetrics] = useState<Record<MetricType, boolean>>({
    sleep: true,
    hrv: true,
    rhr: true,
    load: false,
  });

  // Selected day index for detailed inspector card
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | null>(
    dataPoints.length > 0 ? dataPoints.length - 1 : null
  );

  const toggleMetric = (metric: MetricType) => {
    setActiveMetrics((prev) => {
      const updated = { ...prev, [metric]: !prev[metric] };
      // Ensure at least one metric remains active
      if (!Object.values(updated).some(Boolean)) {
        return prev;
      }
      return updated;
    });
  };

  const selectedPoint =
    selectedDayIndex !== null && dataPoints[selectedDayIndex]
      ? dataPoints[selectedDayIndex]
      : dataPoints[dataPoints.length - 1];

  const metricConfigs: Record<
    MetricType,
    {
      label: string;
      unit: string;
      color: string;
      bgColor: string;
      icon: keyof typeof Ionicons.glyphMap;
      min: number;
      max: number;
    }
  > = {
    sleep: {
      label: 'Sleep',
      unit: 'pts',
      color: '#2563EB',
      bgColor: 'rgba(37, 99, 235, 0.12)',
      icon: 'moon',
      min: 40,
      max: 100,
    },
    hrv: {
      label: 'HRV',
      unit: 'ms',
      color: '#059669',
      bgColor: 'rgba(5, 150, 105, 0.12)',
      icon: 'pulse',
      min: 30,
      max: 110,
    },
    rhr: {
      label: 'Resting HR',
      unit: 'bpm',
      color: '#DC2626',
      bgColor: 'rgba(220, 38, 38, 0.12)',
      icon: 'heart',
      min: 45,
      max: 85,
    },
    load: {
      label: 'Training Load',
      unit: 'AU',
      color: '#D97706',
      bgColor: 'rgba(217, 119, 6, 0.12)',
      icon: 'flash',
      min: 0,
      max: 500,
    },
  };

  const getNormalizedHeight = (val: number | undefined, min: number, max: number) => {
    if (val === undefined || val === null) return 0;
    const clamped = Math.max(min, Math.min(max, val));
    return ((clamped - min) / (max - min)) * 75 + 15;
  };

  const handleConsultCoachPress = () => {
    if (!selectedPoint) return;
    const summary = `Hey Coach Bro! Checking out my recovery trends for ${selectedPoint.date}: Sleep ${selectedPoint.sleep ?? 'N/A'}/100, HRV ${selectedPoint.hrv ?? 'N/A'}ms, Resting HR ${selectedPoint.rhr ?? 'N/A'}bpm, Training Load ${selectedPoint.load ?? 'N/A'}. How should I adjust today's training?`;
    if (onConsultCoach) {
      onConsultCoach(summary);
    } else {
      router.push({
        pathname: '/(tabs)/chat',
        params: { initialPrompt: summary },
      });
    }
  };

  return (
    <View style={styles.container}>
      {/* Header & Title */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.title}>Layered Recovery Trends</Text>
          <Text style={styles.subtitle}>Toggle metrics to correlate sleep, HRV & training load</Text>
        </View>
        <TouchableOpacity style={styles.coachBadge} onPress={handleConsultCoachPress}>
          <Ionicons name="chatbubbles-outline" size={14} color="#2563EB" />
          <Text style={styles.coachBadgeText}>Ask Coach</Text>
        </TouchableOpacity>
      </View>

      {/* Interactive Metric Toggle Buttons */}
      <View style={styles.toggleRow}>
        {(Object.keys(metricConfigs) as MetricType[]).map((key) => {
          const cfg = metricConfigs[key];
          const isActive = activeMetrics[key];
          return (
            <TouchableOpacity
              key={key}
              style={[
                styles.toggleBtn,
                isActive ? { backgroundColor: cfg.bgColor, borderColor: cfg.color } : styles.toggleBtnInactive,
              ]}
              onPress={() => toggleMetric(key)}
              activeOpacity={0.7}
            >
              <Ionicons name={cfg.icon} size={14} color={isActive ? cfg.color : '#94A3B8'} style={{ marginRight: 4 }} />
              <Text style={[styles.toggleBtnText, { color: isActive ? cfg.color : '#64748B' }]}>
                {cfg.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Layered Trend Graph Area */}
      <View style={styles.chartBox}>
        {/* Y-Axis Grid Lines */}
        <View style={styles.gridLinesContainer}>
          <View style={styles.gridLine} />
          <View style={styles.gridLine} />
          <View style={styles.gridLine} />
        </View>

        {/* Data Columns */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scrollGraphContent}>
          {dataPoints.map((pt, idx) => {
            const isSelected = selectedDayIndex === idx;
            return (
              <TouchableOpacity
                key={idx}
                style={[styles.colContainer, isSelected && styles.colSelected]}
                onPress={() => setSelectedDayIndex(idx)}
                activeOpacity={0.8}
              >
                <View style={styles.barsGroup}>
                  {(Object.keys(metricConfigs) as MetricType[]).map((mKey) => {
                    if (!activeMetrics[mKey]) return null;
                    const cfg = metricConfigs[mKey];
                    const val = pt[mKey];
                    const normH = getNormalizedHeight(val, cfg.min, cfg.max);
                    return (
                      <View
                        key={mKey}
                        style={[
                          styles.metricBar,
                          {
                            height: `${normH}%`,
                            backgroundColor: cfg.color,
                            opacity: isSelected ? 1 : 0.8,
                          },
                        ]}
                      />
                    );
                  })}
                </View>
                <Text style={[styles.dayText, isSelected && styles.dayTextSelected]}>
                  {pt.dayLabel || pt.date.slice(5)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Point Detail Inspector Card */}
      {selectedPoint && (
        <View style={styles.inspectorCard}>
          <View style={styles.inspectorHeader}>
            <Text style={styles.inspectorDate}>📅 {selectedPoint.date}</Text>
            <TouchableOpacity style={styles.consultBtnInline} onPress={handleConsultCoachPress}>
              <Ionicons name="sparkles" size={13} color="#FFFFFF" style={{ marginRight: 4 }} />
              <Text style={styles.consultBtnInlineText}>Consult Coach Bro</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.inspectorGrid}>
            {activeMetrics.sleep && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="moon" size={14} color="#2563EB" style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>Sleep</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: '#2563EB' }]}>
                  {selectedPoint.sleep ?? '--'} <Text style={styles.inspectorUnit}>/ 100</Text>
                </Text>
              </View>
            )}

            {activeMetrics.hrv && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="pulse" size={14} color="#059669" style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>HRV</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: '#059669' }]}>
                  {selectedPoint.hrv ?? '--'} <Text style={styles.inspectorUnit}>ms</Text>
                </Text>
              </View>
            )}

            {activeMetrics.rhr && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="heart" size={14} color="#DC2626" style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>Resting HR</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: '#DC2626' }]}>
                  {selectedPoint.rhr ?? '--'} <Text style={styles.inspectorUnit}>bpm</Text>
                </Text>
              </View>
            )}

            {activeMetrics.load && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="flash" size={14} color="#D97706" style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>Training Load</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: '#D97706' }]}>
                  {selectedPoint.load ?? '--'} <Text style={styles.inspectorUnit}>AU</Text>
                </Text>
              </View>
            )}
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 16,
    marginBottom: 16,
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0F172A',
  },
  subtitle: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  coachBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(37, 99, 235, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(37, 99, 235, 0.2)',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  coachBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#2563EB',
    marginLeft: 4,
  },
  toggleRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 14,
  },
  toggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
  },
  toggleBtnInactive: {
    backgroundColor: '#F8FAFC',
    borderColor: '#E2E8F0',
  },
  toggleBtnText: {
    fontSize: 11,
    fontWeight: '600',
  },
  chartBox: {
    height: 140,
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    paddingTop: 10,
    paddingBottom: 4,
    justifyContent: 'flex-end',
    position: 'relative',
    overflow: 'hidden',
  },
  gridLinesContainer: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 8,
  },
  gridLine: {
    height: 1,
    backgroundColor: '#E2E8F0',
    width: '100%',
  },
  scrollGraphContent: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    gap: 12,
  },
  colContainer: {
    alignItems: 'center',
    width: 36,
    height: '100%',
    justifyContent: 'flex-end',
    paddingBottom: 4,
    borderRadius: 8,
  },
  colSelected: {
    backgroundColor: 'rgba(37, 99, 235, 0.06)',
  },
  barsGroup: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 100,
    gap: 2,
  },
  metricBar: {
    width: 6,
    borderRadius: 3,
    minHeight: 4,
  },
  dayText: {
    fontSize: 9,
    fontWeight: '600',
    color: '#94A3B8',
    marginTop: 4,
  },
  dayTextSelected: {
    color: '#2563EB',
    fontWeight: '700',
  },
  inspectorCard: {
    marginTop: 12,
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 12,
  },
  inspectorHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  inspectorDate: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0F172A',
  },
  consultBtnInline: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2563EB',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  consultBtnInlineText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '600',
  },
  inspectorGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  inspectorItem: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 8,
  },
  inspectorLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: '#64748B',
  },
  inspectorVal: {
    fontSize: 14,
    fontWeight: '800',
    marginTop: 2,
  },
  inspectorUnit: {
    fontSize: 9,
    fontWeight: '400',
    color: '#94A3B8',
  },
});
