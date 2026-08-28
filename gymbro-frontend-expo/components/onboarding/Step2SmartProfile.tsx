import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/Colors';
import { AthleteProfile, PrepopulatedBiometrics } from '../../services/onboardingApi';

interface Step2SmartProfileProps {
  profile: AthleteProfile;
  biometrics: PrepopulatedBiometrics;
  onChangeProfile: (updated: Partial<AthleteProfile>) => void;
  onChangeBiometrics: (updated: Partial<PrepopulatedBiometrics>) => void;
}

interface MetricItemProps {
  title: string;
  value: string | number;
  unit: string;
  onDecrement: () => void;
  onIncrement: () => void;
}

const MetricCard: React.FC<MetricItemProps> = ({
  title,
  value,
  unit,
  onDecrement,
  onIncrement,
}) => (
  <View style={styles.metricCard}>
    <Text style={styles.metricTitle}>{title}</Text>
    <Text style={styles.metricDisplay}>
      {value} <Text style={styles.unit}>{unit}</Text>
    </Text>
    <View style={styles.stepperRow}>
      <TouchableOpacity
        style={styles.stepperBtn}
        onPress={onDecrement}
        activeOpacity={0.7}
      >
        <Ionicons name="remove" size={16} color={Colors.light.text} />
      </TouchableOpacity>
      <TouchableOpacity
        style={styles.stepperBtn}
        onPress={onIncrement}
        activeOpacity={0.7}
      >
        <Ionicons name="add" size={16} color={Colors.light.text} />
      </TouchableOpacity>
    </View>
  </View>
);

export const Step2SmartProfile: React.FC<Step2SmartProfileProps> = ({
  profile,
  biometrics,
  onChangeProfile,
  onChangeBiometrics,
}) => {
  const isDataPrepopulated = biometrics.data_available;

  const adjustAge = (delta: number) => {
    const current = profile.age || 30;
    onChangeProfile({ age: Math.max(16, Math.min(100, current + delta)) });
  };

  const adjustWeight = (delta: number) => {
    const current = profile.weight || 75.0;
    onChangeProfile({ weight: Math.max(35, Math.min(250, +(current + delta).toFixed(1))) });
  };

  const adjustHeight = (delta: number) => {
    const current = profile.height || 180.0;
    onChangeProfile({ height: Math.max(120, Math.min(230, +(current + delta).toFixed(0))) });
  };

  const adjustRestingHr = (delta: number) => {
    const current = biometrics.resting_hr || 65;
    onChangeBiometrics({ resting_hr: Math.max(35, Math.min(120, current + delta)) });
  };

  return (
    <View style={styles.container}>
      {/* Header Banner */}
      <View style={styles.cardHeader}>
        <View style={styles.iconCircle}>
          <Ionicons name="person-circle-outline" size={24} color={Colors.light.primary} />
        </View>
        <View style={styles.headerTextGroup}>
          <Text style={styles.cardTitle}>Smart Profile & Baselines</Text>
          <Text style={styles.cardSubtitle}>
            {isDataPrepopulated
              ? '✨ Extracted automatically from your connected device history.'
              : 'Calibrated defaults. Fine-tune with quick steppers if needed.'}
          </Text>
        </View>
      </View>

      {/* Biological Sex Toggle */}
      <View style={styles.section}>
        <Text style={styles.sectionLabel}>Biological Sex</Text>
        <View style={styles.sexToggleRow}>
          {['male', 'female'].map((sex) => {
            const isSelected = (profile.biological_sex || 'male').toLowerCase() === sex;
            return (
              <TouchableOpacity
                key={sex}
                style={[styles.sexChip, isSelected && styles.sexChipSelected]}
                onPress={() => onChangeProfile({ biological_sex: sex })}
                activeOpacity={0.75}
              >
                <Text style={[styles.sexChipText, isSelected && styles.sexChipTextSelected]}>
                  {sex === 'male' ? '♂ Male' : '♀ Female'}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Metric Stepper Grid */}
      <View style={styles.grid}>
        <MetricCard
          title="Age"
          value={profile.age || 30}
          unit="yrs"
          onDecrement={() => adjustAge(-1)}
          onIncrement={() => adjustAge(1)}
        />
        <MetricCard
          title="Weight"
          value={profile.weight || 75.0}
          unit="kg"
          onDecrement={() => adjustWeight(-1.0)}
          onIncrement={() => adjustWeight(1.0)}
        />
        <MetricCard
          title="Height"
          value={profile.height || 180}
          unit="cm"
          onDecrement={() => adjustHeight(-1)}
          onIncrement={() => adjustHeight(1)}
        />
        <MetricCard
          title="Resting HR"
          value={biometrics.resting_hr || 65}
          unit="bpm"
          onDecrement={() => adjustRestingHr(-1)}
          onIncrement={() => adjustRestingHr(1)}
        />
      </View>

      {/* 14-day Acute Workload Snapshot */}
      <View style={styles.acuteSnapshot}>
        <View style={styles.acuteSnapshotHeader}>
          <Ionicons name="trending-up" size={18} color={Colors.light.secondary} />
          <Text style={styles.acuteSnapshotTitle}>14-Day Acute Workload</Text>
        </View>
        <View style={styles.acuteSnapshotRow}>
          <View style={styles.acuteItem}>
            <Text style={styles.acuteItemLabel}>Weekly Vol</Text>
            <Text style={styles.acuteItemVal}>
              {(biometrics.acute_weekly_volume_km ?? biometrics.weekly_volume ?? 0).toFixed(1)} km/wk
            </Text>
          </View>
          <View style={styles.acuteItem}>
            <Text style={styles.acuteItemLabel}>Avg Sleep</Text>
            <Text style={styles.acuteItemVal}>{(biometrics.sleep_hours || 7.5).toFixed(1)} hrs</Text>
          </View>
          <View style={styles.acuteItem}>
            <Text style={styles.acuteItemLabel}>HRV</Text>
            <Text style={styles.acuteItemVal}>
              {biometrics.hrv_ms ? `${biometrics.hrv_ms} ms` : biometrics.hrv ? `${biometrics.hrv}` : '65 ms'}
            </Text>
          </View>
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
    marginBottom: 18,
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
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.light.secondaryText,
    marginBottom: 8,
  },
  sexToggleRow: {
    flexDirection: 'row',
    gap: 10,
  },
  sexChip: {
    flex: 1,
    backgroundColor: Colors.light.cardElevated,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: Colors.light.border,
  },
  sexChipSelected: {
    borderColor: Colors.light.primary,
    backgroundColor: Colors.light.primaryLight,
  },
  sexChipText: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.light.text,
  },
  sexChipTextSelected: {
    color: Colors.light.primaryHover,
    fontWeight: '700',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 18,
  },
  metricCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: Colors.light.cardElevated,
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  metricTitle: {
    fontSize: 12,
    color: Colors.light.secondaryText,
    marginBottom: 4,
  },
  metricDisplay: {
    fontSize: 20,
    fontWeight: '800',
    color: Colors.light.text,
    marginBottom: 8,
  },
  unit: {
    fontSize: 13,
    fontWeight: '500',
    color: Colors.light.secondaryText,
  },
  stepperRow: {
    flexDirection: 'row',
    gap: 8,
  },
  stepperBtn: {
    flex: 1,
    height: 32,
    backgroundColor: Colors.light.card,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  acuteSnapshot: {
    backgroundColor: Colors.light.recoveryLight,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: Colors.light.vitalityLight,
  },
  acuteSnapshotHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  acuteSnapshotTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.light.secondary,
  },
  acuteSnapshotRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  acuteItem: {
    alignItems: 'center',
  },
  acuteItemLabel: {
    fontSize: 11,
    color: Colors.light.secondaryText,
    marginBottom: 2,
  },
  acuteItemVal: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.light.text,
  },
});
