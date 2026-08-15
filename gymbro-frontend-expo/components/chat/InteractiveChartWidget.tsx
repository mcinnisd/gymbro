import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Colors from '../../constants/Colors';
import { ChatWidgetEnvelope, InteractiveChartPayload } from '../../services/widgetProtocol';

interface InteractiveChartWidgetProps {
  widget: ChatWidgetEnvelope<InteractiveChartPayload>;
  onTriggerPrompt?: (promptText: string) => void;
  onExecuteAction?: (widgetId: string, actionId: string) => void;
}

export const InteractiveChartWidget: React.FC<InteractiveChartWidgetProps> = ({
  widget,
  onTriggerPrompt,
  onExecuteAction,
}) => {
  const { title, subtitle, payload, actions, state } = widget;
  const { metrics, points, summary_insight } = payload;

  const [activeMetricKeys, setActiveMetricKeys] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    metrics.forEach((m) => {
      init[m.key] = true;
    });
    return init;
  });

  const [selectedIndex, setSelectedIndex] = useState<number>(() =>
    points.length > 0 ? points.length - 1 : 0
  );

  const toggleMetric = (key: string) => {
    setActiveMetricKeys((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      if (!Object.values(next).some(Boolean)) return prev;
      return next;
    });
  };

  const selectedPoint = points[selectedIndex] || points[points.length - 1];

  return (
    <View style={styles.container}>
      {/* Widget Header */}
      <View style={styles.header}>
        <View style={styles.headerTitleBox}>
          <View style={styles.iconBadge}>
            <Ionicons name="stats-chart" size={14} color={Colors.light.primary} />
          </View>
          <View>
            <Text style={styles.title}>{title}</Text>
            {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          </View>
        </View>
        <View style={styles.stateBadge}>
          <Text style={styles.stateBadgeText}>
            {payload.time_range ? `${payload.time_range.toUpperCase()} TREND` : 'METRICS'}
          </Text>
        </View>
      </View>

      {/* Metric Filter Chips */}
      <View style={styles.metricChipsRow}>
        {metrics.map((m) => {
          const isActive = activeMetricKeys[m.key];
          return (
            <TouchableOpacity
              key={m.key}
              style={[
                styles.metricChip,
                isActive ? { backgroundColor: `${m.color}15`, borderColor: m.color } : styles.metricChipInactive,
              ]}
              onPress={() => toggleMetric(m.key)}
              activeOpacity={0.7}
            >
              <View style={[styles.metricDot, { backgroundColor: m.color }]} />
              <Text
                style={[
                  styles.metricChipText,
                  { color: isActive ? m.color : Colors.light.secondaryText },
                ]}
              >
                {m.label} ({m.unit})
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Scrubbing Column Chart Box */}
      <View style={styles.chartBox}>
        {/* Grid lines */}
        <View style={styles.gridLinesContainer}>
          <View style={styles.gridLine} />
          <View style={styles.gridLine} />
          <View style={styles.gridLine} />
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chartScrollContent}
        >
          {points.map((pt, idx) => {
            const isSelected = selectedIndex === idx;
            return (
              <TouchableOpacity
                key={idx}
                style={[styles.colContainer, isSelected && styles.colSelected]}
                onPress={() => setSelectedIndex(idx)}
                activeOpacity={0.8}
              >
                <View style={styles.barsGroup}>
                  {metrics.map((m) => {
                    if (!activeMetricKeys[m.key]) return null;
                    const val = pt.values[m.key] ?? 0;
                    const min = m.min ?? 0;
                    const max = m.max ?? 100;
                    const normH = Math.max(12, Math.min(95, ((val - min) / (max - min)) * 75 + 15));
                    return (
                      <View
                        key={m.key}
                        style={[
                          styles.metricBar,
                          {
                            height: `${normH}%`,
                            backgroundColor: m.color,
                            opacity: isSelected ? 1 : 0.75,
                          },
                        ]}
                      />
                    );
                  })}
                </View>
                <Text style={[styles.dayText, isSelected && styles.dayTextSelected]}>
                  {pt.label || pt.date.slice(5)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Selected Point Inspector */}
      {selectedPoint && (
        <View style={styles.inspectorBox}>
          <View style={styles.inspectorHeader}>
            <Text style={styles.inspectorDate}>📅 {selectedPoint.date} ({selectedPoint.label || ''})</Text>
            <View style={styles.inspectorValsRow}>
              {metrics.map((m) => {
                if (!activeMetricKeys[m.key]) return null;
                const val = selectedPoint.values[m.key];
                return (
                  <Text key={m.key} style={[styles.inspectorValText, { color: m.color }]}>
                    {m.label}: {val ?? '--'}{m.unit}
                  </Text>
                );
              })}
            </View>
          </View>

          {selectedPoint.annotation ? (
            <View style={styles.annotationBox}>
              <Ionicons name="warning-outline" size={13} color={Colors.light.primary} style={{ marginRight: 4 }} />
              <Text style={styles.annotationText}>{selectedPoint.annotation}</Text>
            </View>
          ) : null}
        </View>
      )}

      {/* Summary Insight Note */}
      {summary_insight ? (
        <Text style={styles.summaryInsightText}>💡 {summary_insight}</Text>
      ) : null}

      {/* Action Buttons (excluding redundant discuss with agent) */}
      {actions.filter(a => !a.label.toLowerCase().includes('discuss')).length > 0 && (
        <View style={styles.actionsContainer}>
          {actions
            .filter(a => !a.label.toLowerCase().includes('discuss'))
            .map((act) => (
              <TouchableOpacity
                key={act.id}
                style={styles.actionBtnGhost}
                onPress={() => {
                  if (act.action_type === 'prompt_trigger' && act.prompt_text && onTriggerPrompt) {
                    onTriggerPrompt(act.prompt_text);
                  } else if (onExecuteAction) {
                    onExecuteAction(widget.widget_id, act.id);
                  }
                }}
              >
                <Ionicons name="analytics-outline" size={14} color={Colors.light.primary} style={{ marginRight: 6 }} />
                <Text style={styles.actionBtnGhostText}>{act.label}</Text>
              </TouchableOpacity>
            ))}
        </View>
      )}

    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginTop: 10,
    backgroundColor: Colors.light.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
    padding: 14,
    shadowColor: Colors.light.shadowColor,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  headerTitleBox: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  iconBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.light.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  title: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.light.text,
    letterSpacing: -0.2,
  },
  subtitle: {
    fontSize: 11,
    color: Colors.light.secondaryText,
    marginTop: 1,
  },
  stateBadge: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 10,
    backgroundColor: Colors.light.primaryLight,
  },
  stateBadgeConfirmed: {
    backgroundColor: 'rgba(5, 150, 105, 0.12)',
  },
  stateBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    textTransform: 'uppercase',
    color: Colors.light.primary,
  },
  stateBadgeTextConfirmed: {
    color: Colors.light.vitality,
  },
  metricChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 10,
  },
  metricChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
  },
  metricChipInactive: {
    backgroundColor: Colors.light.cardSubtle,
    borderColor: Colors.light.borderSubtle,
  },
  metricDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 4,
  },
  metricChipText: {
    fontSize: 10,
    fontWeight: '600',
  },
  chartBox: {
    height: 120,
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
    position: 'relative',
    justifyContent: 'flex-end',
    overflow: 'hidden',
  },
  gridLinesContainer: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  gridLine: {
    height: 1,
    backgroundColor: Colors.light.borderSubtle,
    width: '100%',
  },
  chartScrollContent: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 8,
    gap: 10,
  },
  colContainer: {
    alignItems: 'center',
    width: 32,
    height: '100%',
    justifyContent: 'flex-end',
    paddingBottom: 4,
    borderRadius: 6,
  },
  colSelected: {
    backgroundColor: 'rgba(217, 119, 6, 0.10)',
  },
  barsGroup: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 80,
    gap: 2,
  },
  metricBar: {
    width: 5,
    borderRadius: 2.5,
    minHeight: 4,
  },
  dayText: {
    fontSize: 9,
    fontWeight: '600',
    color: Colors.light.mutedText,
    marginTop: 4,
  },
  dayTextSelected: {
    color: Colors.light.primary,
    fontWeight: '700',
  },
  inspectorBox: {
    marginTop: 10,
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
  },
  inspectorHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  inspectorDate: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.light.text,
  },
  inspectorValsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  inspectorValText: {
    fontSize: 11,
    fontWeight: '700',
  },
  annotationBox: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    backgroundColor: 'rgba(217, 119, 6, 0.08)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  annotationText: {
    fontSize: 11,
    color: Colors.light.primary,
    fontWeight: '600',
  },
  summaryInsightText: {
    fontSize: 11,
    color: Colors.light.secondaryText,
    marginTop: 8,
    fontStyle: 'italic',
  },
  actionsContainer: {
    marginTop: 10,
  },
  actionBtnGhost: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.light.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingVertical: 8,
    borderRadius: 10,
  },
  actionBtnGhostText: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.light.primary,
  },
});
