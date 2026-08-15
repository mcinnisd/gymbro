import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Colors from '../../constants/Colors';
import { ChatWidgetEnvelope, MacroSliderPayload } from '../../services/widgetProtocol';

interface MacroSliderWidgetProps {
  widget: ChatWidgetEnvelope<MacroSliderPayload>;
  onExecuteAction?: (widgetId: string, actionId: string, payload?: any) => void;
}

export const MacroSliderWidget: React.FC<MacroSliderWidgetProps> = ({
  widget,
  onExecuteAction,
}) => {
  const { title, subtitle, payload, actions, state } = widget;
  const { presets } = payload;

  const [protein, setProtein] = useState<number>(payload.protein_g);
  const [carbs, setCarbs] = useState<number>(payload.carbs_g);
  const [fats, setFats] = useState<number>(payload.fats_g);

  const totalCalories = protein * 4 + carbs * 4 + fats * 9;
  const pCal = protein * 4;
  const cCal = carbs * 4;
  const fCal = fats * 9;

  const pPct = totalCalories > 0 ? Math.round((pCal / totalCalories) * 100) : 0;
  const cPct = totalCalories > 0 ? Math.round((cCal / totalCalories) * 100) : 0;
  const fPct = totalCalories > 0 ? Math.round((fCal / totalCalories) * 100) : 0;

  const applyPreset = (preset: typeof presets[0]) => {
    setProtein(preset.protein_g);
    setCarbs(preset.carbs_g);
    setFats(preset.fats_g);
  };

  const adjustValue = (macro: 'p' | 'c' | 'f', delta: number) => {
    if (macro === 'p') setProtein((prev) => Math.max(60, Math.min(300, prev + delta)));
    if (macro === 'c') setCarbs((prev) => Math.max(20, Math.min(500, prev + delta)));
    if (macro === 'f') setFats((prev) => Math.max(20, Math.min(200, prev + delta)));
  };

  const isConfirmed = state === 'confirmed' || state === 'executed';

  return (
    <View style={styles.container}>
      {/* Widget Header */}
      <View style={styles.header}>
        <View style={styles.headerTitleBox}>
          <View style={styles.iconBadge}>
            <Ionicons name="nutrition" size={14} color={Colors.light.primary} />
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

      {/* Daily Calories & Ratio Header */}
      <View style={styles.kcalCard}>
        <View>
          <Text style={styles.kcalLabel}>Target Daily Calories</Text>
          <Text style={styles.kcalVal}>
            {totalCalories.toLocaleString()} <Text style={styles.kcalUnit}>kcal</Text>
          </Text>
        </View>
        <View style={styles.ratioLabelsBox}>
          <Text style={styles.ratioText}>
            <Text style={{ color: '#E11D48', fontWeight: '700' }}>{pPct}% P</Text> •{' '}
            <Text style={{ color: '#D97706', fontWeight: '700' }}>{cPct}% C</Text> •{' '}
            <Text style={{ color: '#059669', fontWeight: '700' }}>{fPct}% F</Text>
          </Text>
        </View>
      </View>

      {/* Macro Ratio Proportion Bar */}
      <View style={styles.ratioBar}>
        <View style={[styles.ratioSeg, { width: `${pPct}%`, backgroundColor: '#E11D48' }]} />
        <View style={[styles.ratioSeg, { width: `${cPct}%`, backgroundColor: '#D97706' }]} />
        <View style={[styles.ratioSeg, { width: `${fPct}%`, backgroundColor: '#059669' }]} />
      </View>

      {/* Preset Chips */}
      {presets.length > 0 && (
        <View style={styles.presetChipsRow}>
          {presets.map((pre) => (
            <TouchableOpacity
              key={pre.id}
              style={styles.presetChip}
              onPress={() => applyPreset(pre)}
            >
              <Text style={styles.presetChipText}>{pre.name}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Interactive Macro Adjusters */}
      <View style={styles.adjustersContainer}>
        {/* Protein */}
        <View style={styles.adjusterRow}>
          <View style={styles.macroLabelBox}>
            <Ionicons name="fitness" size={12} color="#E11D48" style={{ marginRight: 4 }} />
            <Text style={styles.macroName}>Protein</Text>
          </View>
          <View style={styles.stepperBox}>
            <TouchableOpacity style={styles.stepBtn} onPress={() => adjustValue('p', -5)}>
              <Ionicons name="remove" size={14} color={Colors.light.text} />
            </TouchableOpacity>
            <Text style={[styles.macroVal, { color: '#E11D48' }]}>{protein}g</Text>
            <TouchableOpacity style={styles.stepBtn} onPress={() => adjustValue('p', 5)}>
              <Ionicons name="add" size={14} color={Colors.light.text} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Carbs */}
        <View style={styles.adjusterRow}>
          <View style={styles.macroLabelBox}>
            <Ionicons name="flame" size={12} color="#D97706" style={{ marginRight: 4 }} />
            <Text style={styles.macroName}>Carbs</Text>
          </View>
          <View style={styles.stepperBox}>
            <TouchableOpacity style={styles.stepBtn} onPress={() => adjustValue('c', -10)}>
              <Ionicons name="remove" size={14} color={Colors.light.text} />
            </TouchableOpacity>
            <Text style={[styles.macroVal, { color: '#D97706' }]}>{carbs}g</Text>
            <TouchableOpacity style={styles.stepBtn} onPress={() => adjustValue('c', 10)}>
              <Ionicons name="add" size={14} color={Colors.light.text} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Fats */}
        <View style={styles.adjusterRow}>
          <View style={styles.macroLabelBox}>
            <Ionicons name="leaf" size={12} color="#059669" style={{ marginRight: 4 }} />
            <Text style={styles.macroName}>Fats</Text>
          </View>
          <View style={styles.stepperBox}>
            <TouchableOpacity style={styles.stepBtn} onPress={() => adjustValue('f', -5)}>
              <Ionicons name="remove" size={14} color={Colors.light.text} />
            </TouchableOpacity>
            <Text style={[styles.macroVal, { color: '#059669' }]}>{fats}g</Text>
            <TouchableOpacity style={styles.stepBtn} onPress={() => adjustValue('f', 5)}>
              <Ionicons name="add" size={14} color={Colors.light.text} />
            </TouchableOpacity>
          </View>
        </View>
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
                  onExecuteAction(widget.widget_id, act.id, {
                    protein_g: protein,
                    carbs_g: carbs,
                    fats_g: fats,
                    total_calories: totalCalories,
                  });
                }
              }}
              disabled={isConfirmed}
            >
              <Ionicons
                name={isConfirmed ? 'checkmark-circle' : 'save-outline'}
                size={16}
                color="#FFFFFF"
                style={{ marginRight: 6 }}
              />
              <Text style={styles.actionBtnPrimaryText}>
                {isConfirmed ? 'Saved to Profile' : act.label}
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
  kcalCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    backgroundColor: Colors.light.cardSubtle,
    padding: 10,
    borderRadius: 10,
    marginBottom: 8,
  },
  kcalLabel: {
    fontSize: 10,
    color: Colors.light.secondaryText,
    fontWeight: '600',
  },
  kcalVal: {
    fontSize: 18,
    fontWeight: '800',
    color: Colors.light.text,
  },
  kcalUnit: {
    fontSize: 12,
    fontWeight: '500',
    color: Colors.light.mutedText,
  },
  ratioLabelsBox: {
    alignItems: 'flex-end',
  },
  ratioText: {
    fontSize: 11,
  },
  ratioBar: {
    height: 6,
    borderRadius: 3,
    flexDirection: 'row',
    overflow: 'hidden',
    backgroundColor: Colors.light.borderSubtle,
    marginBottom: 10,
  },
  ratioSeg: {
    height: '100%',
  },
  presetChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 10,
  },
  presetChip: {
    backgroundColor: Colors.light.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  presetChipText: {
    fontSize: 10,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
  adjustersContainer: {
    gap: 6,
  },
  adjusterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.light.cardSubtle,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  macroLabelBox: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 80,
  },
  macroName: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.light.text,
  },
  stepperBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  stepBtn: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: Colors.light.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  macroVal: {
    fontSize: 13,
    fontWeight: '700',
    minWidth: 44,
    textAlign: 'center',
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
