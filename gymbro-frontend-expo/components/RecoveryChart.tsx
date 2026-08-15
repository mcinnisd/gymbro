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
import { Colors } from '../constants/Colors';

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
      color: Colors.light.sleepDusk,
      bgColor: 'rgba(79, 70, 229, 0.10)',
      icon: 'moon',
      min: 40,
      max: 100,
    },
    hrv: {
      label: 'HRV',
      unit: 'ms',
      color: Colors.light.vitality,
      bgColor: 'rgba(5, 150, 105, 0.10)',
      icon: 'pulse',
      min: 30,
      max: 110,
    },
    rhr: {
      label: 'Resting HR',
      unit: 'bpm',
      color: Colors.light.cardio,
      bgColor: 'rgba(225, 29, 72, 0.10)',
      icon: 'heart',
      min: 45,
      max: 85,
    },
    load: {
      label: 'Training Load',
      unit: 'AU',
      color: Colors.light.primary,
      bgColor: 'rgba(217, 119, 6, 0.10)',
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
    const summary = `Reviewing my recovery biometrics for ${selectedPoint.date}: Sleep ${selectedPoint.sleep ?? 'N/A'}/100, HRV ${selectedPoint.hrv ?? 'N/A'}ms, Resting HR ${selectedPoint.rhr ?? 'N/A'}bpm, Training Load ${selectedPoint.load ?? 'N/A'}. How should this shape today's training?`;
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
          <Text style={styles.subtitle}>Correlate sleep, HRV, resting heart rate & load</Text>
        </View>
        <TouchableOpacity style={styles.coachBadge} onPress={handleConsultCoachPress}>
          <Ionicons name="sparkles" size={13} color={Colors.light.primary} />
          <Text style={styles.coachBadgeText}>Ask Agent</Text>
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
              <Ionicons name={cfg.icon} size={14} color={isActive ? cfg.color : Colors.light.mutedText} style={{ marginRight: 5 }} />
              <Text style={[styles.toggleBtnText, { color: isActive ? cfg.color : Colors.light.secondaryText }]}>
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
                            opacity: isSelected ? 1 : 0.85,
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
              <Ionicons name="sparkles" size={12} color="#FFFFFF" style={{ marginRight: 4 }} />
              <Text style={styles.consultBtnInlineText}>Discuss with Agent</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.inspectorGrid}>
            {activeMetrics.sleep && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="moon" size={13} color={Colors.light.sleepDusk} style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>Sleep Score</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: Colors.light.sleepDusk }]}>
                  {selectedPoint.sleep ?? '--'} <Text style={styles.inspectorUnit}>/ 100</Text>
                </Text>
              </View>
            )}

            {activeMetrics.hrv && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="pulse" size={13} color={Colors.light.vitality} style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>HRV</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: Colors.light.vitality }]}>
                  {selectedPoint.hrv ?? '--'} <Text style={styles.inspectorUnit}>ms</Text>
                </Text>
              </View>
            )}

            {activeMetrics.rhr && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="heart" size={13} color={Colors.light.cardio} style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>Resting HR</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: Colors.light.cardio }]}>
                  {selectedPoint.rhr ?? '--'} <Text style={styles.inspectorUnit}>bpm</Text>
                </Text>
              </View>
            )}

            {activeMetrics.load && (
              <View style={styles.inspectorItem}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Ionicons name="flash" size={13} color={Colors.light.primary} style={{ marginRight: 4 }} />
                  <Text style={styles.inspectorLabel}>Training Load</Text>
                </View>
                <Text style={[styles.inspectorVal, { color: Colors.light.primary }]}>
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
    backgroundColor: Colors.light.card,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.light.border,
    padding: 16,
    marginBottom: 16,
    shadowColor: Colors.light.shadowColor,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
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
    color: Colors.light.text,
    letterSpacing: -0.2,
  },
  subtitle: {
    fontSize: 12,
    color: Colors.light.secondaryText,
    marginTop: 2,
  },
  coachBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  coachBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.light.primary,
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
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
  },
  toggleBtnInactive: {
    backgroundColor: Colors.light.cardSubtle,
    borderColor: Colors.light.borderSubtle,
  },
  toggleBtnText: {
    fontSize: 11,
    fontWeight: '600',
  },
  chartBox: {
    height: 140,
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
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
    backgroundColor: Colors.light.borderSubtle,
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
    backgroundColor: 'rgba(217, 119, 6, 0.08)',
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
    fontSize: 10,
    fontWeight: '600',
    color: Colors.light.mutedText,
    marginTop: 4,
  },
  dayTextSelected: {
    color: Colors.light.primary,
    fontWeight: '700',
  },
  inspectorCard: {
    marginTop: 12,
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.light.border,
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
    color: Colors.light.text,
  },
  consultBtnInline: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  consultBtnInlineText: {
    color: '#FFFFFF',
    fontSize: 11,
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
    backgroundColor: Colors.light.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
    padding: 10,
  },
  inspectorLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
  inspectorVal: {
    fontSize: 15,
    fontWeight: '800',
    marginTop: 2,
  },
  inspectorUnit: {
    fontSize: 10,
    fontWeight: '400',
    color: Colors.light.mutedText,
  },
});
