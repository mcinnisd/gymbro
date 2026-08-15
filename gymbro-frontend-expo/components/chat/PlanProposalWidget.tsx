import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Colors from '../../constants/Colors';
import { ChatWidgetEnvelope, CalendarProposalPayload } from '../../services/widgetProtocol';

interface PlanProposalWidgetProps {
  widget: ChatWidgetEnvelope<CalendarProposalPayload>;
  onExecuteAction?: (widgetId: string, actionId: string) => void;
}

export const PlanProposalWidget: React.FC<PlanProposalWidgetProps> = ({
  widget,
  onExecuteAction,
}) => {
  const { title, subtitle, payload, actions, state } = widget;
  const { horizon, target_volume_km, sessions } = payload;

  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const toggleExpand = (idx: number) => {
    setExpandedIndex((prev) => (prev === idx ? null : idx));
  };

  const isConfirmed = state === 'confirmed' || state === 'executed';

  return (
    <View style={styles.container}>
      {/* Widget Header */}
      <View style={styles.header}>
        <View style={styles.headerTitleBox}>
          <View style={styles.iconBadge}>
            <Ionicons name="calendar" size={14} color={Colors.light.vitality} />
          </View>
          <View>
            <View style={styles.horizonTag}>
              <Text style={styles.horizonTagText}>{horizon} horizon</Text>
            </View>
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

      {/* Target Volume & Session Summary */}
      <View style={styles.summaryRow}>
        <Text style={styles.summaryText}>
          🎯 Volume: <Text style={styles.summaryBold}>{target_volume_km ?? '--'} km</Text>
        </Text>
        <Text style={styles.summaryText}>
          📋 Sessions: <Text style={styles.summaryBold}>{sessions.length}</Text>
        </Text>
      </View>

      {/* Planned Sessions List */}
      <View style={styles.sessionsList}>
        {sessions.map((s, idx) => {
          const isExpanded = expandedIndex === idx;
          return (
            <TouchableOpacity
              key={idx}
              style={[styles.sessionItem, isExpanded && styles.sessionItemExpanded]}
              onPress={() => toggleExpand(idx)}
              activeOpacity={0.7}
            >
              <View style={styles.sessionHeaderRow}>
                <View style={styles.sessionLeft}>
                  <Text style={styles.sessionDay}>{s.day_name}</Text>
                  <Text style={styles.sessionTitle}>{s.title}</Text>
                </View>
                <View style={styles.sessionTag}>
                  <Text style={styles.sessionTagText}>{s.tag}</Text>
                </View>
              </View>

              {isExpanded && (
                <View style={styles.sessionDetails}>
                  <Text style={styles.sessionDetailText}>
                    ⏱ Duration: {s.duration} min {s.distance ? `• Distance: ${s.distance} km` : ''}
                  </Text>
                  {s.description ? (
                    <Text style={styles.sessionDescText}>{s.description}</Text>
                  ) : null}
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Action Buttons */}
      {actions.length > 0 && (
        <View style={styles.actionsContainer}>
          {actions.map((act) => (
            <TouchableOpacity
              key={act.id}
              style={[styles.actionBtnPrimary, isConfirmed && styles.actionBtnConfirmed]}
              onPress={() => {
                if (!isConfirmed && onExecuteAction) {
                  onExecuteAction(widget.widget_id, act.id);
                }
              }}
              disabled={isConfirmed}
            >
              <Ionicons
                name={isConfirmed ? 'checkmark-circle' : 'calendar-outline'}
                size={16}
                color="#FFFFFF"
                style={{ marginRight: 6 }}
              />
              <Text style={styles.actionBtnPrimaryText}>
                {isConfirmed ? 'Committed to Calendar' : act.label}
              </Text>
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
    backgroundColor: 'rgba(5, 150, 105, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  horizonTag: {
    alignSelf: 'flex-start',
    backgroundColor: Colors.light.primaryLight,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    marginBottom: 2,
  },
  horizonTagText: {
    fontSize: 9,
    fontWeight: '700',
    color: Colors.light.primary,
    textTransform: 'uppercase',
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
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: Colors.light.cardSubtle,
    padding: 8,
    borderRadius: 8,
    marginBottom: 10,
  },
  summaryText: {
    fontSize: 11,
    color: Colors.light.secondaryText,
  },
  summaryBold: {
    fontWeight: '700',
    color: Colors.light.text,
  },
  sessionsList: {
    gap: 6,
  },
  sessionItem: {
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 8,
    padding: 8,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
  },
  sessionItemExpanded: {
    borderColor: Colors.light.primary,
  },
  sessionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sessionLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  sessionDay: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.light.text,
    width: 34,
  },
  sessionTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.light.text,
    flex: 1,
  },
  sessionTag: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  sessionTagText: {
    fontSize: 10,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
  sessionDetails: {
    marginTop: 6,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: Colors.light.borderSubtle,
  },
  sessionDetailText: {
    fontSize: 11,
    color: Colors.light.mutedText,
    fontWeight: '600',
  },
  sessionDescText: {
    fontSize: 11,
    color: Colors.light.secondaryText,
    marginTop: 2,
  },
  actionsContainer: {
    marginTop: 12,
  },
  actionBtnPrimary: {
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
});
