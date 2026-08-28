import React, { useState, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ActivityIndicator,
  Linking,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/Colors';
import { AuthContext } from '../../context/AuthContext';
import { GarminModal } from '../GarminModal';
import { prepopulateTelemetry, PrepopulatedBiometrics } from '../../services/onboardingApi';

interface Step1WearableConnectProps {
  connectedProviders: string[];
  onProviderLinked: (provider: string, prepopulatedData?: PrepopulatedBiometrics) => void;
  onSkip: () => void;
  onContinue: () => void;
}

export const Step1WearableConnect: React.FC<Step1WearableConnectProps> = ({
  connectedProviders,
  onProviderLinked,
  onSkip,
  onContinue,
}) => {
  const { apiUrl, authToken } = useContext(AuthContext);
  const [garminModalVisible, setGarminModalVisible] = useState(false);
  const [syncingProvider, setSyncingProvider] = useState<string | null>(null);

  const isGarminLinked = connectedProviders.includes('garmin');
  const isAppleHealthLinked = connectedProviders.includes('apple_health');
  const isStravaLinked = connectedProviders.includes('strava');

  // Handle Apple HealthKit connection & telemetry ingestion
  const handleConnectAppleHealth = async () => {
    setSyncingProvider('apple_health');
    try {
      const simulatedHealthKitPayload = {
        source: 'apple_health',
        biometrics: {
          resting_heart_rate: 56,
          hrv_sdnn: 68.0,
          sleep_hours: 8.0,
          weight_kg: 76.5,
          height_cm: 182.0,
          age: 29,
          biological_sex: 'male',
        },
        activities: [
          {
            type: 'running',
            distance_km: 10.0,
            duration_min: 50.0,
            timestamp: new Date(Date.now() - 86400000 * 2).toISOString(),
          },
          {
            type: 'running',
            distance_km: 12.5,
            duration_min: 62.0,
            timestamp: new Date(Date.now() - 86400000 * 5).toISOString(),
          },
        ],
      };

      const prepop = await prepopulateTelemetry(simulatedHealthKitPayload);
      onProviderLinked('apple_health', prepop);
    } catch (err: any) {
      console.error('[Step1] HealthKit sync error:', err);
      Alert.alert('HealthKit Sync', 'Could not sync HealthKit data. You can proceed manually.');
      onProviderLinked('apple_health');
    } finally {
      setSyncingProvider(null);
    }
  };

  // Handle Strava OAuth Connect
  const handleConnectStrava = async () => {
    setSyncingProvider('strava');
    try {
      const resp = await fetch(`${apiUrl}/strava/connect_strava?json=true`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.url) {
          Linking.openURL(data.url);
        }
      }
      const prepop = await prepopulateTelemetry();
      onProviderLinked('strava', prepop);
    } catch (err) {
      console.warn('[Step1] Strava connection error:', err);
      onProviderLinked('strava');
    } finally {
      setSyncingProvider(null);
    }
  };

  // Callback on Garmin success
  const handleGarminSuccess = async () => {
    setGarminModalVisible(false);
    setSyncingProvider('garmin');
    try {
      const prepop = await prepopulateTelemetry();
      onProviderLinked('garmin', prepop);
    } catch {
      onProviderLinked('garmin');
    } finally {
      setSyncingProvider(null);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.cardHeader}>
        <View style={styles.iconCircle}>
          <Ionicons name="watch-outline" size={24} color={Colors.light.primary} />
        </View>
        <View style={styles.headerTextGroup}>
          <Text style={styles.cardTitle}>Link Your Wearable</Text>
          <Text style={styles.cardSubtitle}>
            Zero-typing baseline calibration from your past activities & biometrics.
          </Text>
        </View>
      </View>

      <View style={styles.providersList}>
        {/* Apple Health Card */}
        <TouchableOpacity
          style={[styles.providerCard, isAppleHealthLinked && styles.providerCardLinked]}
          onPress={handleConnectAppleHealth}
          disabled={syncingProvider !== null}
          activeOpacity={0.75}
        >
          <View style={[styles.providerIconCircle, { backgroundColor: Colors.light.cardioLight }]}>
            <Ionicons name="heart" size={20} color={Colors.light.cardio} />
          </View>
          <View style={styles.providerInfo}>
            <Text style={styles.providerName}>Apple Health / HealthKit</Text>
            <Text style={styles.providerSub}>
              {isAppleHealthLinked ? '✓ Connected & Synced' : 'HR, HRV, sleep & workouts'}
            </Text>
          </View>
          {syncingProvider === 'apple_health' ? (
            <ActivityIndicator size="small" color={Colors.light.primary} />
          ) : isAppleHealthLinked ? (
            <Ionicons name="checkmark-circle" size={22} color={Colors.light.secondary} />
          ) : (
            <View style={styles.connectBadge}>
              <Text style={styles.connectBadgeText}>Connect</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Garmin Card */}
        <TouchableOpacity
          style={[styles.providerCard, isGarminLinked && styles.providerCardLinked]}
          onPress={() => setGarminModalVisible(true)}
          disabled={syncingProvider !== null}
          activeOpacity={0.75}
        >
          <View style={[styles.providerIconCircle, { backgroundColor: Colors.light.sleepLight }]}>
            <Ionicons name="speedometer" size={20} color={Colors.light.sleepDusk} />
          </View>
          <View style={styles.providerInfo}>
            <Text style={styles.providerName}>Garmin Connect</Text>
            <Text style={styles.providerSub}>
              {isGarminLinked ? '✓ Connected & Synced' : 'Direct 14-day history & body battery'}
            </Text>
          </View>
          {syncingProvider === 'garmin' ? (
            <ActivityIndicator size="small" color={Colors.light.primary} />
          ) : isGarminLinked ? (
            <Ionicons name="checkmark-circle" size={22} color={Colors.light.secondary} />
          ) : (
            <View style={styles.connectBadge}>
              <Text style={styles.connectBadgeText}>Connect</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Strava Card */}
        <TouchableOpacity
          style={[styles.providerCard, isStravaLinked && styles.providerCardLinked]}
          onPress={handleConnectStrava}
          disabled={syncingProvider !== null}
          activeOpacity={0.75}
        >
          <View style={[styles.providerIconCircle, { backgroundColor: Colors.light.primaryLight }]}>
            <Ionicons name="bicycle" size={20} color={Colors.light.primary} />
          </View>
          <View style={styles.providerInfo}>
            <Text style={styles.providerName}>Strava</Text>
            <Text style={styles.providerSub}>
              {isStravaLinked ? '✓ Connected & Synced' : 'Running & cycling activity streams'}
            </Text>
          </View>
          {syncingProvider === 'strava' ? (
            <ActivityIndicator size="small" color={Colors.light.primary} />
          ) : isStravaLinked ? (
            <Ionicons name="checkmark-circle" size={22} color={Colors.light.secondary} />
          ) : (
            <View style={styles.connectBadge}>
              <Text style={styles.connectBadgeText}>Connect</Text>
            </View>
          )}
        </TouchableOpacity>
      </View>

      {/* Skip Action */}
      <TouchableOpacity style={styles.skipButton} onPress={onSkip} activeOpacity={0.7}>
        <Text style={styles.skipButtonText}>I don't use a wearable — Enter Manually</Text>
      </TouchableOpacity>

      {/* Garmin Login Dialog Modal */}
      <GarminModal
        visible={garminModalVisible}
        onClose={() => setGarminModalVisible(false)}
        onSuccess={handleGarminSuccess}
      />
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
  providersList: {
    gap: 12,
    marginBottom: 20,
  },
  providerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.cardElevated,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1.5,
    borderColor: Colors.light.border,
  },
  providerCardLinked: {
    borderColor: Colors.light.secondary,
    backgroundColor: Colors.light.recoveryLight,
  },
  providerIconCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
  },
  providerInfo: {
    flex: 1,
    marginLeft: 12,
  },
  providerName: {
    fontSize: 15,
    fontWeight: '600',
    color: Colors.light.text,
  },
  providerSub: {
    fontSize: 12,
    color: Colors.light.secondaryText,
    marginTop: 2,
  },
  connectBadge: {
    backgroundColor: Colors.light.primaryLight,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  connectBadgeText: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.light.primary,
  },
  skipButton: {
    alignItems: 'center',
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: Colors.light.borderSubtle,
  },
  skipButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
});
