import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  PanResponder,
  GestureResponderEvent,
  LayoutChangeEvent,
} from 'react-native';
import Svg, {
  Path,
  Defs,
  LinearGradient as SvgGradient,
  Stop,
  Circle,
  Line as SvgLine,
  Rect,
} from 'react-native-svg';
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
  const { title, subtitle, payload, actions } = widget;
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

  const [chartWidth, setChartWidth] = useState<number>(320);
  const chartHeight = 130;
  const padLeft = 24;
  const padRight = 24;
  const padTop = 14;
  const padBottom = 22;

  const toggleMetric = (key: string) => {
    setActiveMetricKeys((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      if (!Object.values(next).some(Boolean)) return prev;
      return next;
    });
  };

  const handleLayout = (e: LayoutChangeEvent) => {
    const { width } = e.nativeEvent.layout;
    if (width > 0) {
      setChartWidth(width);
    }
  };

  const updateScrubIndex = (touchX: number) => {
    if (points.length <= 1) return;
    const innerW = chartWidth - padLeft - padRight;
    const relX = Math.max(0, Math.min(innerW, touchX - padLeft));
    const step = innerW / (points.length - 1);
    const newIdx = Math.round(relX / step);
    const clamped = Math.max(0, Math.min(points.length - 1, newIdx));
    setSelectedIndex(clamped);
  };

  const panResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (evt: GestureResponderEvent) => {
      updateScrubIndex(evt.nativeEvent.locationX);
    },
    onPanResponderMove: (evt: GestureResponderEvent) => {
      updateScrubIndex(evt.nativeEvent.locationX);
    },
  });

  const selectedPoint = points[selectedIndex] || points[points.length - 1];

  // Helper to compute coordinates for metric
  const computeMetricCoordinates = (mKey: string, minOverride?: number, maxOverride?: number) => {
    if (points.length === 0) return [];
    
    // Find min and max across all points
    const vals = points.map((p) => Number(p.values[mKey] ?? 0));
    let minV = minOverride ?? Math.min(...vals);
    let maxV = maxOverride ?? Math.max(...vals);
    if (minV === maxV) {
      minV = minV - 5;
      maxV = maxV + 5;
    }

    const innerW = chartWidth - padLeft - padRight;
    const innerH = chartHeight - padTop - padBottom;
    const step = points.length > 1 ? innerW / (points.length - 1) : innerW;

    return points.map((pt, i) => {
      const val = Number(pt.values[mKey] ?? minV);
      const normY = (val - minV) / (maxV - minV);
      const x = padLeft + i * step;
      const y = chartHeight - padBottom - normY * innerH;
      return { x, y, val };
    });
  };

  // Build SVG smooth bezier path
  const buildSmoothPath = (coords: { x: number; y: number }[]): string => {
    if (coords.length === 0) return '';
    if (coords.length === 1) return `M ${coords[0].x} ${coords[0].y}`;

    let d = `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`;
    for (let i = 0; i < coords.length - 1; i++) {
      const p0 = coords[i === 0 ? 0 : i - 1];
      const p1 = coords[i];
      const p2 = coords[i + 1];
      const p3 = coords[i + 2 >= coords.length ? coords.length - 1 : i + 2];

      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;

      d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
    }
    return d;
  };

  const selectedX =
    points.length > 1
      ? padLeft + (selectedIndex * (chartWidth - padLeft - padRight)) / (points.length - 1)
      : chartWidth / 2;

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
            {payload.time_range ? `${payload.time_range.toUpperCase()} TREND` : 'TREND'}
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

      {/* SVG Interactive Line Chart Box */}
      <View
        style={styles.chartBox}
        onLayout={handleLayout}
        {...panResponder.panHandlers}
      >
        <Svg width="100%" height={chartHeight}>
          <Defs>
            {metrics.map((m) => (
              <SvgGradient key={m.key} id={`grad_${m.key}`} x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0%" stopColor={m.color} stopOpacity="0.25" />
                <Stop offset="100%" stopColor={m.color} stopOpacity="0.0" />
              </SvgGradient>
            ))}
          </Defs>

          {/* Horizontal Grid lines */}
          <SvgLine
            x1={padLeft}
            y1={padTop}
            x2={chartWidth - padRight}
            y2={padTop}
            stroke={Colors.light.borderSubtle}
            strokeWidth={1}
            strokeDasharray="2 2"
          />
          <SvgLine
            x1={padLeft}
            y1={(padTop + chartHeight - padBottom) / 2}
            x2={chartWidth - padRight}
            y2={(padTop + chartHeight - padBottom) / 2}
            stroke={Colors.light.borderSubtle}
            strokeWidth={1}
            strokeDasharray="2 2"
          />
          <SvgLine
            x1={padLeft}
            y1={chartHeight - padBottom}
            x2={chartWidth - padRight}
            y2={chartHeight - padBottom}
            stroke={Colors.light.borderSubtle}
            strokeWidth={1}
          />

          {/* Continuous Line & Area Paths for active metrics */}
          {metrics.map((m) => {
            if (!activeMetricKeys[m.key]) return null;
            const coords = computeMetricCoordinates(m.key, m.min, m.max);
            if (coords.length === 0) return null;

            const lineD = buildSmoothPath(coords);
            const lastX = coords[coords.length - 1].x;
            const firstX = coords[0].x;
            const areaD = `${lineD} L ${lastX.toFixed(1)} ${(chartHeight - padBottom).toFixed(1)} L ${firstX.toFixed(1)} ${(chartHeight - padBottom).toFixed(1)} Z`;

            return (
              <React.Fragment key={m.key}>
                {/* Gradient Area Fill */}
                <Path d={areaD} fill={`url(#grad_${m.key})`} />
                {/* Main Curve Line */}
                <Path
                  d={lineD}
                  stroke={m.color}
                  strokeWidth={2.5}
                  fill="none"
                  strokeLinecap="round"
                />
              </React.Fragment>
            );
          })}

          {/* Vertical Crosshair Guideline */}
          {points.length > 0 && (
            <SvgLine
              x1={selectedX}
              y1={padTop}
              x2={selectedX}
              y2={chartHeight - padBottom}
              stroke={Colors.light.primary}
              strokeWidth={1.5}
              strokeDasharray="3 3"
            />
          )}

          {/* Crosshair Dots at active metrics */}
          {metrics.map((m) => {
            if (!activeMetricKeys[m.key]) return null;
            const coords = computeMetricCoordinates(m.key, m.min, m.max);
            const pt = coords[selectedIndex];
            if (!pt) return null;

            return (
              <React.Fragment key={m.key}>
                <Circle cx={pt.x} cy={pt.y} r={6} fill={m.color} opacity={0.3} />
                <Circle cx={pt.x} cy={pt.y} r={3.5} fill={m.color} />
                <Circle cx={pt.x} cy={pt.y} r={1.5} fill="#FFFFFF" />
              </React.Fragment>
            );
          })}
        </Svg>

        {/* Date Labels under SVG */}
        <View style={[styles.datesRow, { paddingHorizontal: padLeft }]}>
          {points.map((p, idx) => {
            const isSel = idx === selectedIndex;
            // Only show every other label if many points
            if (points.length > 8 && idx % 2 !== 0 && idx !== points.length - 1) return null;
            return (
              <TouchableOpacity
                key={idx}
                onPress={() => setSelectedIndex(idx)}
                hitSlop={{ top: 10, bottom: 10, left: 5, right: 5 }}
              >
                <Text style={[styles.dateText, isSel && styles.dateTextSelected]}>
                  {p.label || p.date.slice(5)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
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
                    {m.label}: {val ?? '--'} {m.unit}
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

      {/* Action Buttons */}
      {actions.filter((a) => !a.label.toLowerCase().includes('discuss')).length > 0 && (
        <View style={styles.actionsContainer}>
          {actions
            .filter((a) => !a.label.toLowerCase().includes('discuss'))
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
  stateBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    textTransform: 'uppercase',
    color: Colors.light.primary,
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
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
    paddingVertical: 8,
    position: 'relative',
  },
  datesRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  dateText: {
    fontSize: 9,
    fontWeight: '600',
    color: Colors.light.mutedText,
  },
  dateTextSelected: {
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

