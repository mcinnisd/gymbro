import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/Colors';
import { GoalSetDraft } from '../../services/onboardingApi';

interface Step3GoalSetProps {
  goals: GoalSetDraft;
  onChangeGoals: (updated: Partial<GoalSetDraft>) => void;
}

interface GoalOption {
  key: string;
  name: string;
  emoji: string;
  title: string;
  subtitle: string;
}

const PRIMARY_GOALS: GoalOption[] = [
  {
    key: 'marathon_endurance',
    name: 'Marathon Endurance',
    emoji: '🏃',
    title: '🏃 Marathon & Endurance',
    subtitle: 'High weekly mileage, tempo runs, progressive long runs, aerobic efficiency.',
  },
  {
    key: 'muscle_strength',
    name: 'Hypertrophy & Strength',
    emoji: '🏋️',
    title: '🏋️ Hypertrophy & Strength',
    subtitle: 'Compound lifts, structured progressive overload, hypertrophy volume blocks.',
  },
  {
    key: 'hybrid_fitness',
    name: 'Hybrid Athlete',
    emoji: '⚡',
    title: '⚡ Hybrid Athlete',
    subtitle: 'Balanced simultaneous endurance pacing and resistance training.',
  },
  {
    key: 'fat_loss',
    name: 'Body Recomposition',
    emoji: '🔥',
    title: '🔥 Body Recomposition',
    subtitle: 'Caloric density tracking, zone 2 fat oxidation, lean muscle retention.',
  },
  {
    key: 'longevity_aerobic',
    name: 'Longevity & Aerobic Base',
    emoji: '🌿',
    title: '🌿 Longevity & Aerobic Base',
    subtitle: 'Zone 2 cardio, mobility routines, heart rate variability and recovery.',
  },
];

const DAYS = [
  { short: 'Mon', full: 'Monday' },
  { short: 'Tue', full: 'Tuesday' },
  { short: 'Wed', full: 'Wednesday' },
  { short: 'Thu', full: 'Thursday' },
  { short: 'Fri', full: 'Friday' },
  { short: 'Sat', full: 'Saturday' },
  { short: 'Sun', full: 'Sunday' },
];

const EQUIPMENT_OPTIONS = [
  'Full Commercial Gym',
  'Home Dumbbells & Bench',
  'Bodyweight / Calisthenics',
  'Outdoor Running Trails',
];

export const Step3GoalSet: React.FC<Step3GoalSetProps> = ({
  goals,
  onChangeGoals,
}) => {
  const selectedDays = goals.days_available || ['Monday', 'Wednesday', 'Friday', 'Saturday'];

  const toggleDay = (dayFull: string) => {
    let updated: string[];
    if (selectedDays.includes(dayFull)) {
      if (selectedDays.length <= 2) {
        return; // maintain minimum 2 days
      }
      updated = selectedDays.filter((d) => d !== dayFull);
    } else {
      updated = [...selectedDays, dayFull];
    }
    onChangeGoals({ days_available: updated });
  };

  const handleSelectPrimary = (key: string) => {
    const cleanSecondary = (goals.secondary_goals || []).filter((g) => g !== key);
    onChangeGoals({ primary_goal: key, secondary_goals: cleanSecondary });
  };

  const toggleSecondary = (key: string) => {
    if (key === goals.primary_goal) return;
    const current = goals.secondary_goals || [];
    let updated: string[];
    if (current.includes(key)) {
      updated = current.filter((g) => g !== key);
    } else {
      updated = [...current, key];
    }
    onChangeGoals({ secondary_goals: updated });
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.cardHeader}>
        <View style={styles.iconCircle}>
          <Ionicons name="trophy-outline" size={24} color={Colors.light.primary} />
        </View>
        <View style={styles.headerTextGroup}>
          <Text style={styles.cardTitle}>Ranked Goal Set</Text>
          <Text style={styles.cardSubtitle}>
            Define your core athletic focus, secondary targets, and equipment availability.
          </Text>
        </View>
      </View>

      {/* Primary Goal Section */}
      <View style={styles.section}>
        <Text style={styles.sectionHeader}>1. Primary Athletic Priority</Text>
        <View style={styles.goalList}>
          {PRIMARY_GOALS.map((g) => {
            const isSelected = goals.primary_goal === g.key;
            return (
              <TouchableOpacity
                key={g.key}
                style={[styles.goalCard, isSelected && styles.goalCardSelected]}
                onPress={() => handleSelectPrimary(g.key)}
                activeOpacity={0.75}
              >
                <View style={styles.goalCardTop}>
                  <Text style={[styles.goalTitle, isSelected && styles.goalTitleSelected]}>
                    {g.title}
                  </Text>
                  {isSelected && (
                    <Ionicons name="checkmark-circle" size={20} color={Colors.light.primary} />
                  )}
                </View>
                <Text style={styles.goalSubtitle}>{g.subtitle}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Secondary Priority Section */}
      <View style={styles.section}>
        <Text style={styles.sectionHeader}>2. Secondary Focus (Optional)</Text>
        <View style={styles.secondaryChipsRow}>
          {PRIMARY_GOALS.filter((g) => g.key !== goals.primary_goal).map((g) => {
            const isSecondary = (goals.secondary_goals || []).includes(g.key);
            return (
              <TouchableOpacity
                key={g.key}
                style={[styles.secChip, isSecondary && styles.secChipSelected]}
                onPress={() => toggleSecondary(g.key)}
                activeOpacity={0.75}
              >
                <Text style={[styles.secChipText, isSecondary && styles.secChipTextSelected]}>
                  {isSecondary ? `✓ ${g.name}` : `+ ${g.name}`}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Weekly Training Days */}
      <View style={styles.section}>
        <View style={styles.daysHeaderRow}>
          <Text style={styles.sectionHeader}>3. Available Workout Days</Text>
          <Text style={styles.daysCountBadge}>{selectedDays.length} days/wk</Text>
        </View>
        <View style={styles.dayGrid}>
          {DAYS.map((d) => {
            const isSelected = selectedDays.includes(d.full);
            return (
              <TouchableOpacity
                key={d.short}
                style={[styles.dayChip, isSelected && styles.dayChipSelected]}
                onPress={() => toggleDay(d.full)}
                activeOpacity={0.75}
              >
                <Text style={[styles.dayChipText, isSelected && styles.dayChipTextSelected]}>
                  {d.short}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Equipment Access Section */}
      <View style={styles.section}>
        <Text style={styles.sectionHeader}>4. Equipment & Facility Access</Text>
        <View style={styles.equipmentRow}>
          {EQUIPMENT_OPTIONS.map((eq) => {
            const isSelected = (goals.equipment || EQUIPMENT_OPTIONS[0]) === eq;
            return (
              <TouchableOpacity
                key={eq}
                style={[styles.equipmentChip, isSelected && styles.equipmentChipSelected]}
                onPress={() => onChangeGoals({ equipment: eq })}
                activeOpacity={0.75}
              >
                <Text style={[styles.equipmentChipText, isSelected && styles.equipmentChipTextSelected]}>
                  {isSelected ? `✓ ${eq}` : eq}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.light.card,
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: Colors.light.border,
    shadowColor: Colors.light.shadowColor,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 20,
  },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.light.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTextGroup: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.light.text,
  },
  cardSubtitle: {
    fontSize: 13,
    color: Colors.light.secondaryText,
    marginTop: 2,
    lineHeight: 18,
  },
  section: {
    marginBottom: 20,
  },
  sectionHeader: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.light.text,
    marginBottom: 10,
  },
  goalList: {
    gap: 10,
  },
  goalCard: {
    backgroundColor: Colors.light.cardElevated,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1.5,
    borderColor: Colors.light.border,
  },
  goalCardSelected: {
    borderColor: Colors.light.primary,
    backgroundColor: Colors.light.primaryLight,
  },
  goalCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  goalTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: Colors.light.text,
  },
  goalTitleSelected: {
    color: Colors.light.primaryHover,
  },
  goalSubtitle: {
    fontSize: 12,
    color: Colors.light.secondaryText,
    lineHeight: 16,
  },
  secondaryChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  secChip: {
    backgroundColor: Colors.light.cardElevated,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  secChipSelected: {
    borderColor: Colors.light.secondary,
    backgroundColor: Colors.light.recoveryLight,
  },
  secChipText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
  secChipTextSelected: {
    color: Colors.light.secondary,
    fontWeight: '700',
  },
  daysHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  daysCountBadge: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.light.primary,
    backgroundColor: Colors.light.primaryLight,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  dayGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  dayChip: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: Colors.light.cardElevated,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: Colors.light.border,
  },
  dayChipSelected: {
    borderColor: Colors.light.primary,
    backgroundColor: Colors.light.primary,
  },
  dayChipText: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.light.text,
  },
  dayChipTextSelected: {
    color: '#FFFFFF',
  },
  equipmentRow: {
    flexDirection: 'column',
    gap: 8,
  },
  equipmentChip: {
    backgroundColor: Colors.light.cardElevated,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderWidth: 1.5,
    borderColor: Colors.light.border,
  },
  equipmentChipSelected: {
    borderColor: Colors.light.primary,
    backgroundColor: Colors.light.primaryLight,
  },
  equipmentChipText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
  equipmentChipTextSelected: {
    color: Colors.light.primaryHover,
    fontWeight: '700',
  },
});
