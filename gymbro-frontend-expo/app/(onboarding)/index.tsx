import React, { useState, useEffect, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Platform,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { AuthContext } from '../../context/AuthContext';
import { Colors } from '../../constants/Colors';
import {
  fetchOnboardingState,
  saveOnboardingStep,
  generateOnboardingProposal,
  commitOnboarding,
  AthleteProfile,
  GoalSetDraft,
  PrepopulatedBiometrics,
  DataRealityCheck,
} from '../../services/onboardingApi';
import { Step1WearableConnect } from '../../components/onboarding/Step1WearableConnect';
import { Step2SmartProfile } from '../../components/onboarding/Step2SmartProfile';
import { Step3GoalSet } from '../../components/onboarding/Step3GoalSet';

const STEP_TITLES = [
  'Connect Hardware',
  'Smart Biometrics',
  'Ranked Goal Set',
  'Reality Check',
  'Plan Launch',
];

const STEP_DESCRIPTIONS = [
  'Sync with Garmin, Apple Health, or Strava for automated baseline extraction.',
  'Verify your pre-populated physiological metrics or adjust manual baselines.',
  'Define your primary athletic focus, secondary targets, and weekly training days.',
  'Audit your stated targets against historical workload and select a training horizon.',
  'Review your personalized Meso Horizon schedule and commit it to your calendar.',
];

export default function OnboardingStepperScreen() {
  const router = useRouter();
  const { user, setUser, logout } = useContext(AuthContext);

  const [loading, setLoading] = useState(true);
  const [savingStep, setSavingStep] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);

  // Form State
  const [profile, setProfile] = useState<AthleteProfile>({
    age: 30,
    weight: 75.0,
    height: 180.0,
    biological_sex: 'male',
    sport_history: 'Running & Strength',
    running_experience: 'Intermediate',
  });
  const [biometrics, setBiometrics] = useState<PrepopulatedBiometrics>({
    data_available: false,
    resting_hr: 65,
    sleep_hours: 7.5,
    weekly_volume: 0.0,
    connected_providers: [],
    personal_records: {},
  });
  const [goals, setGoals] = useState<GoalSetDraft>({
    primary_goal: 'marathon_endurance',
    secondary_goals: ['muscle_strength'],
    days_available: ['Monday', 'Wednesday', 'Friday', 'Saturday'],
    horizon: '4_week_foundation',
  });
  const [realityCheck, setRealityCheck] = useState<DataRealityCheck | null>(null);
  const [proposal, setProposal] = useState<any>(null);

  // 1. Initial State Resumption
  useEffect(() => {
    loadOnboardingState();
  }, []);

  const loadOnboardingState = async () => {
    setLoading(true);
    try {
      const state = await fetchOnboardingState();
      if (state.is_completed || state.coach_status === 'active') {
        if (user) {
          setUser({ ...user, coach_status: 'active' });
        }
        router.replace('/(tabs)/training');
        return;
      }

      // Deterministic Resumption
      if (state.step && state.step >= 1 && state.step <= 5) {
        setCurrentStep(state.step);
      }

      if (state.athlete_profile) {
        setProfile((prev) => ({ ...prev, ...state.athlete_profile }));
      }
      if (state.prepopulated_biometrics) {
        setBiometrics(state.prepopulated_biometrics);
      }
      if (state.goal_set) {
        setGoals((prev) => ({ ...prev, ...state.goal_set }));
      }
      if (state.reality_check) {
        setRealityCheck(state.reality_check);
      }
      if (state.proposal) {
        setProposal(state.proposal);
      }
    } catch (err: any) {
      console.warn('[OnboardingStepper] Could not load state from backend:', err?.message);
    } finally {
      setLoading(false);
    }
  };

  // 2. Step Navigation
  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleNext = async () => {
    setSavingStep(true);
    try {
      let stepPayload: Record<string, any> = {};

      if (currentStep === 1) {
        stepPayload = {
          connected_providers: biometrics.connected_providers || [],
          skipped_hardware: (biometrics.connected_providers || []).length === 0,
        };
      } else if (currentStep === 2) {
        if (!profile.age || profile.age < 16 || !profile.weight || profile.weight < 30) {
          Alert.alert('Incomplete Profile', 'Please verify your age and weight before continuing.');
          setSavingStep(false);
          return;
        }
        stepPayload = {
          age: profile.age,
          weight: profile.weight,
          height: profile.height,
          biological_sex: profile.biological_sex,
          sport_history: profile.sport_history,
          running_experience: profile.running_experience,
          resting_hr: biometrics.resting_hr,
          hrv: biometrics.hrv,
          sleep_hours: biometrics.sleep_hours,
        };
      } else if (currentStep === 3) {
        if (!goals.primary_goal) {
          Alert.alert('Missing Goal', 'Please select a primary athletic priority.');
          setSavingStep(false);
          return;
        }
        if (!goals.days_available || goals.days_available.length < 2) {
          Alert.alert('Schedule Availability', 'Please select at least 2 available workout days.');
          setSavingStep(false);
          return;
        }
        stepPayload = {
          primary_goal: goals.primary_goal,
          secondary_goals: goals.secondary_goals,
          days_available: goals.days_available,
          equipment: goals.equipment,
        };
      } else if (currentStep === 4) {
        stepPayload = {
          horizon: goals.horizon,
          calibration_confirmed: true,
        };
        // Auto-generate proposal before entering step 5
        const propBundle = await generateOnboardingProposal(goals.horizon || '4_week_foundation');
        setProposal(propBundle.proposal);
        if (propBundle.reality_check) {
          setRealityCheck(propBundle.reality_check);
        }
      } else if (currentStep === 5) {
        // Commit Onboarding to Calendar
        await commitOnboarding(proposal);
        if (user) {
          setUser({ ...user, coach_status: 'active' });
        }
        router.replace('/(tabs)/training');
        return;
      }

      const saveRes = await saveOnboardingStep(currentStep, stepPayload);
      if (currentStep < 5) {
        setCurrentStep(saveRes.current_step || currentStep + 1);
      }
    } catch (err: any) {
      console.error('[OnboardingStepper] Error saving step:', err);
      Alert.alert('Save Failed', err?.message || 'Could not advance to next step.');
    } finally {
      setSavingStep(false);
    }
  };

  const handleProviderLinked = (provider: string, prepopulatedData?: PrepopulatedBiometrics) => {
    const updatedProviders = Array.from(new Set([...(biometrics.connected_providers || []), provider]));
    if (prepopulatedData) {
      setBiometrics({
        ...prepopulatedData,
        connected_providers: updatedProviders,
      });
      if (prepopulatedData.age) setProfile((p) => ({ ...p, age: prepopulatedData.age }));
      if (prepopulatedData.weight) setProfile((p) => ({ ...p, weight: prepopulatedData.weight }));
      if (prepopulatedData.height) setProfile((p) => ({ ...p, height: prepopulatedData.height }));
      if (prepopulatedData.biological_sex) {
        setProfile((p) => ({ ...p, biological_sex: prepopulatedData.biological_sex }));
      }
    } else {
      setBiometrics((prev) => ({ ...prev, connected_providers: updatedProviders }));
    }
  };

  const handleSkipWearable = async () => {
    setSavingStep(true);
    try {
      setBiometrics((prev) => ({ ...prev, connected_providers: [], data_available: false }));
      const saveRes = await saveOnboardingStep(1, { connected_providers: [], skipped_hardware: true });
      setCurrentStep(saveRes.current_step || 2);
    } catch (err: any) {
      console.error('[OnboardingStepper] Skip error:', err);
      setCurrentStep(2);
    } finally {
      setSavingStep(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
        <Text style={styles.loadingText}>Calibrating your athlete environment...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* 1. Header with Step Progress */}
      <View style={styles.header}>
        <View style={styles.headerTopRow}>
          {currentStep > 1 ? (
            <TouchableOpacity onPress={handleBack} style={styles.navBtn} activeOpacity={0.7}>
              <Ionicons name="arrow-back" size={20} color={Colors.light.text} />
              <Text style={styles.navBtnText}>Back</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.navBtnPlaceholder} />
          )}

          <Text style={styles.stepBadge}>
            Step {currentStep} of 5
          </Text>

          <TouchableOpacity
            onPress={() => {
              Alert.alert('Exit Setup?', 'You can resume your onboarding anytime.', [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Log Out', style: 'destructive', onPress: logout },
              ]);
            }}
            style={styles.exitBtn}
            activeOpacity={0.7}
          >
            <Ionicons name="log-out-outline" size={18} color={Colors.light.subtext} />
          </TouchableOpacity>
        </View>

        {/* Progress Track (5 Segments) */}
        <View style={styles.progressTrack}>
          {[1, 2, 3, 4, 5].map((s) => (
            <View
              key={s}
              style={[
                styles.progressSegment,
                s === currentStep && styles.progressSegmentActive,
                s < currentStep && styles.progressSegmentCompleted,
              ]}
            />
          ))}
        </View>

        <Text style={styles.stepTitle}>{STEP_TITLES[currentStep - 1]}</Text>
        <Text style={styles.stepSubtitle}>{STEP_DESCRIPTIONS[currentStep - 1]}</Text>
      </View>

      {/* 2. Step Viewport Container */}
      <ScrollView contentContainerStyle={styles.contentScroll} showsVerticalScrollIndicator={false}>
        {currentStep === 1 && (
          <Step1WearableConnect
            connectedProviders={biometrics.connected_providers || []}
            onProviderLinked={handleProviderLinked}
            onSkip={handleSkipWearable}
            onContinue={handleNext}
          />
        )}

        {currentStep === 2 && (
          <Step2SmartProfile
            profile={profile}
            biometrics={biometrics}
            onChangeProfile={(upd) => setProfile((p) => ({ ...p, ...upd }))}
            onChangeBiometrics={(upd) => setBiometrics((b) => ({ ...b, ...upd }))}
          />
        )}

        {currentStep === 3 && (
          <Step3GoalSet
            goals={goals}
            onChangeGoals={(upd) => setGoals((g) => ({ ...g, ...upd }))}
          />
        )}

        {currentStep === 4 && (
          <View style={styles.stepCard}>
            <View style={styles.cardHeader}>
              <Ionicons name="analytics-outline" size={28} color={Colors.light.primary} />
              <Text style={styles.cardTitle}>Data Reality Check</Text>
            </View>
            <Text style={styles.cardBody}>
              {realityCheck?.feedback ||
                'Your baseline has been verified against your stated targets for safe progression.'}
            </Text>

            <View style={styles.horizonChoiceRow}>
              <TouchableOpacity
                style={[
                  styles.horizonCard,
                  goals.horizon === '4_week_foundation' && styles.horizonCardActive,
                ]}
                onPress={() => setGoals((prev) => ({ ...prev, horizon: '4_week_foundation' }))}
                activeOpacity={0.8}
              >
                <Text style={styles.horizonTitle}>🏆 4-Week Foundation</Text>
                <Text style={styles.horizonSubtitle}>
                  Consistency building, progressive volume ramp, and Week 4 deload.
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[
                  styles.horizonCard,
                  goals.horizon === '8_12_week_milestone' && styles.horizonCardActive,
                ]}
                onPress={() => setGoals((prev) => ({ ...prev, horizon: '8_12_week_milestone' }))}
                activeOpacity={0.8}
              >
                <Text style={styles.horizonTitle}>🎯 8–12 Week Milestone</Text>
                <Text style={styles.horizonSubtitle}>
                  Extended multi-phase cycle targeted toward specific race or PR dates.
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {currentStep === 5 && (
          <View style={styles.stepCard}>
            <View style={styles.cardHeader}>
              <Ionicons name="calendar-outline" size={28} color={Colors.light.primary} />
              <Text style={styles.cardTitle}>Meso Horizon Preview</Text>
            </View>
            <Text style={styles.cardBody}>
              Ready to launch! Tapping below will write your tailored schedule to your training
              calendar and unlock the full GYMBro agent suite.
            </Text>

            <View style={styles.planSummaryBox}>
              <Text style={styles.planSummaryTitle}>
                {proposal?.plan_name || '4-Week Foundation Block'}
              </Text>
              <Text style={styles.planSummaryDetail}>
                {goals.days_available?.length || 4} workouts/week • Progressive weekly overload
              </Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* 3. Bottom Action Bar */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={styles.primaryCta}
          onPress={handleNext}
          disabled={savingStep}
          activeOpacity={0.85}
        >
          {savingStep ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.primaryCtaText}>
              {currentStep === 5
                ? '🔥 Commit to Calendar & Launch'
                : currentStep === 4
                ? 'Preview Training Plan'
                : currentStep === 2
                ? 'Confirm Profile & Baselines'
                : 'Continue'}
            </Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: Colors.light.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 15,
    color: Colors.light.secondaryText,
    fontWeight: '500',
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
    backgroundColor: Colors.light.background,
  },
  headerTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  navBtn: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  navBtnText: {
    fontSize: 14,
    color: Colors.light.text,
    marginLeft: 4,
    fontWeight: '600',
  },
  navBtnPlaceholder: {
    width: 60,
  },
  stepBadge: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.light.primary,
    backgroundColor: Colors.light.primaryLight,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  exitBtn: {
    padding: 4,
  },
  progressTrack: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 12,
  },
  progressSegment: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.light.border,
  },
  progressSegmentActive: {
    backgroundColor: Colors.light.primary,
  },
  progressSegmentCompleted: {
    backgroundColor: Colors.light.secondary,
  },
  stepTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.light.text,
    letterSpacing: -0.3,
  },
  stepSubtitle: {
    fontSize: 13,
    color: Colors.light.secondaryText,
    marginTop: 4,
    lineHeight: 18,
  },
  contentScroll: {
    padding: 20,
    paddingBottom: 40,
  },
  stepCard: {
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
    gap: 10,
    marginBottom: 10,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.light.text,
  },
  cardBody: {
    fontSize: 14,
    color: Colors.light.secondaryText,
    lineHeight: 20,
    marginBottom: 18,
  },
  horizonChoiceRow: {
    flexDirection: 'column',
    gap: 12,
  },
  horizonCard: {
    backgroundColor: Colors.light.cardElevated,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1.5,
    borderColor: Colors.light.border,
  },
  horizonCardActive: {
    borderColor: Colors.light.primary,
    backgroundColor: Colors.light.primaryLight,
  },
  horizonTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.light.text,
    marginBottom: 4,
  },
  horizonSubtitle: {
    fontSize: 13,
    color: Colors.light.secondaryText,
    lineHeight: 18,
  },
  planSummaryBox: {
    backgroundColor: Colors.light.cardElevated,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  planSummaryTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.light.text,
    marginBottom: 4,
  },
  planSummaryDetail: {
    fontSize: 13,
    color: Colors.light.secondaryText,
  },
  bottomBar: {
    padding: 16,
    paddingBottom: Platform.OS === 'ios' ? 12 : 16,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
    backgroundColor: Colors.light.background,
  },
  primaryCta: {
    backgroundColor: Colors.light.primary,
    borderRadius: 14,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: Colors.light.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  primaryCtaText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
});
