import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Colors from '../../constants/Colors';
import { ChatWidgetEnvelope, ReadinessActionPayload } from '../../services/widgetProtocol';

interface ReadinessActionWidgetProps {
  widget: ChatWidgetEnvelope<ReadinessActionPayload>;
  onExecuteAction?: (widgetId: string, actionId: string) => void;
}

export const ReadinessActionWidget: React.FC<ReadinessActionWidgetProps> = ({
  widget,
  onExecuteAction,
}) => {
  const { title, subtitle, payload, actions, state } = widget;
  const { readiness_score, hrv_anomaly_pct, recommendation, original_session, suggested_session } = payload;

  const isConfirmed = state === 'confirmed' || state === 'executed';
  const isDismissed = state === 'dismissed';

  return (
    <View style={styles.container}>
      {/* Widget Header */}
      <View style={styles.header}>
        <View style={styles.headerTitleBox}>
          <View style={styles.iconBadge}>
            <Ionicons name="pulse" size={14} color={Colors.light.cardio} />
          </View>
          <View>
            <Text style={styles.title}>{title}</Text>
            {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          </View>
        </View>
        <View style={[styles.stateBadge, isConfirmed && styles.stateBadgeConfirmed]}>
          <Text style={[styles.stateBadgeText, isConfirmed && styles.stateBadgeTextConfirmed]}>
            {state}
          </Text>
        </View>
      </View>

      {/* Readiness Gauge & Anomaly Banner */}
      <View style={styles.gaugeCard}>
        <View style={styles.scoreCircle}>
          <Text style={styles.scoreVal}>{readiness_score}</Text>
          <Text style={styles.scoreLabel}>Score</Text>
        </View>
        <View style={styles.gaugeRight}>
          <View style={styles.anomalyPill}>
            <Ionicons name="trending-down" size={12} color="#E11D48" style={{ marginRight: 4 }} />
            <Text style={styles.anomalyText}>HRV {hrv_anomaly_pct > 0 ? `+${hrv_anomaly_pct}` : hrv_anomaly_pct}% vs baseline</Text>
          </View>
          <Text style={styles.recommendationText}>{recommendation}</Text>
        </View>
      </View>

      {/* Side-by-Side Session Comparison */}
      <View style={styles.comparisonGrid}>
        {/* Original Scheduled */}
        <View style={styles.comparisonCardOriginal}>
          <Text style={styles.compHeaderOriginal}>Original Workout</Text>
          <Text style={styles.compTitle}>{original_session.title}</Text>
          <Text style={styles.compMeta}>{original_session.duration} min • {original_session.intensity}</Text>
        </View>

        {/* Suggested Swap */}
        <View style={styles.comparisonCardSuggested}>
          <Text style={styles.compHeaderSuggested}>Suggested Swap</Text>
          <Text style={styles.compTitle}>{suggested_session.title}</Text>
          <Text style={styles.compMeta}>{suggested_session.duration} min • {suggested_session.intensity}</Text>
        </View>
      </View>

      {/* Action Buttons */}
      {!isDismissed && actions.length > 0 && (
        <View style={styles.actionsContainer}>
          {actions.map((act) => {
            const isPrimary = act.style === 'primary' || act.id === 'accept_reschedule';
            return (
              <TouchableOpacity
                key={act.id}
                style={[
                  isPrimary ? styles.actionBtnPrimary : styles.actionBtnGhost,
                  isConfirmed && isPrimary && styles.actionBtnConfirmed,
                ]}
                onPress={() => {
                  if (!isConfirmed && onExecuteAction) {
                    onExecuteAction(widget.widget_id, act.id);
                  }
                }}
                disabled={isConfirmed}
              >
                {isPrimary && (
                  <Ionicons
                    name={isConfirmed ? 'checkmark-circle' : 'swap-horizontal'}
                    size={15}
                    color="#FFFFFF"
                    style={{ marginRight: 6 }}
                  />
                )}
                <Text
                  style={[
                    isPrimary ? styles.actionBtnPrimaryText : styles.actionBtnGhostText,
                  ]}
                >
                  {isConfirmed && isPrimary ? 'Rescheduled on Calendar' : act.label}
                </Text>
              </TouchableOpacity>
            );
          })}
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
    backgroundColor: 'rgba(225, 29, 72, 0.12)',
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
  gaugeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.cardSubtle,
    padding: 10,
    borderRadius: 10,
    marginBottom: 10,
    gap: 12,
  },
  scoreCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#F59E0B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreVal: {
    fontSize: 16,
    fontWeight: '800',
    color: '#FFFFFF',
    lineHeight: 18,
  },
  scoreLabel: {
    fontSize: 8,
    fontWeight: '700',
    color: '#FFFFFF',
    textTransform: 'uppercase',
  },
  gaugeRight: {
    flex: 1,
  },
  anomalyPill: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 2,
  },
  anomalyText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#E11D48',
  },
  recommendationText: {
    fontSize: 11,
    color: Colors.light.secondaryText,
  },
  comparisonGrid: {
    flexDirection: 'row',
    gap: 8,
  },
  comparisonCardOriginal: {
    flex: 1,
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 8,
    padding: 8,
    borderLeftWidth: 3,
    borderLeftColor: Colors.light.border,
  },
  compHeaderOriginal: {
    fontSize: 10,
    fontWeight: '600',
    color: Colors.light.mutedText,
    marginBottom: 2,
  },
  comparisonCardSuggested: {
    flex: 1,
    backgroundColor: 'rgba(5, 150, 105, 0.08)',
    borderRadius: 8,
    padding: 8,
    borderLeftWidth: 3,
    borderLeftColor: Colors.light.vitality,
  },
  compHeaderSuggested: {
    fontSize: 10,
    fontWeight: '700',
    color: Colors.light.vitality,
    marginBottom: 2,
  },
  compTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.light.text,
  },
  compMeta: {
    fontSize: 10,
    color: Colors.light.secondaryText,
    marginTop: 2,
  },
  actionsContainer: {
    marginTop: 12,
    flexDirection: 'row',
    gap: 8,
  },
  actionBtnPrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.light.primary,
    paddingVertical: 9,
    borderRadius: 10,
  },
  actionBtnConfirmed: {
    backgroundColor: Colors.light.vitality,
  },
  actionBtnPrimaryText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 12,
  },
  actionBtnGhost: {
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.light.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionBtnGhostText: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
});
