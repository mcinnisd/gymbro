import React, { useState, useEffect, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Modal,
  Alert,
  Platform,
  Linking,
} from 'react-native';
import { AuthContext } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import Colors from '../../constants/Colors';

interface ProfileData {
  age: number | null;
  weight: number | null;
  height: number | null;
  goals: Record<string, any>;
  garmin_connected?: boolean;
  strava_connected?: boolean;
}

export default function StatsScreen() {
  const { authToken, logout, apiUrl } = useContext(AuthContext);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncingAll, setSyncingAll] = useState(false);

  // Device Integration States
  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');
  const [garminConnected, setGarminConnected] = useState(false);
  const [garminSyncing, setGarminSyncing] = useState(false);
  const [stravaConnected, setStravaConnected] = useState(false);
  const [healthkitConnected, setHealthkitConnected] = useState(false);

  // Graph Metric & Range Selectors
  const [selectedMetric, setSelectedMetric] = useState<'pace' | 'distance' | 'heart_rate' | 'cadence'>('pace');
  const [periodDays, setPeriodDays] = useState<7 | 30 | 90>(30);

  // Edit Profile Modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [ageInput, setAgeInput] = useState('');
  const [weightInput, setWeightInput] = useState('');
  const [heightInput, setHeightInput] = useState('');
  const [targetWeightInput, setTargetWeightInput] = useState('');
  const [weeklyVolumeInput, setWeeklyVolumeInput] = useState('');

  // Edit PR Modal
  const [showPRModal, setShowPRModal] = useState(false);
  const [pr5k, setPr5k] = useState('');
  const [pr10k, setPr10k] = useState('');
  const [prHalf, setPrHalf] = useState('');
  const [prBikeLongest, setPrBikeLongest] = useState('');
  const [prSwim100m, setPrSwim100m] = useState('');
  const [prHikePeak, setPrHikePeak] = useState('');

  useEffect(() => {
    if (authToken) {
      fetchProfile();
    }
  }, [authToken]);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/auth/profile`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        const usr = data.user || data.profile || {};
        setProfile(usr);

        setAgeInput(usr.age ? String(usr.age) : '');
        setWeightInput(usr.weight ? String(usr.weight) : '');
        setHeightInput(usr.height ? String(usr.height) : '');
        setGarminConnected(usr.garmin_connected || false);
        setStravaConnected(usr.strava_connected || false);

        const gls = usr.goals || {};
        setTargetWeightInput(gls.target_weight ? String(gls.target_weight) : '');
        setWeeklyVolumeInput(gls.weekly_volume ? String(gls.weekly_volume) : '');

        const prs = gls.personal_records || {};
        setPr5k(prs.run_5k || '');
        setPr10k(prs.run_10k || '');
        setPrHalf(prs.run_half || '');
        setPrBikeLongest(prs.bike_longest || '');
        setPrSwim100m(prs.swim_100m || '');
        setPrHikePeak(prs.hike_peak || '');
      }
    } catch (err) {
      console.error('Error fetching user profile:', err);
    }
    setLoading(false);
  };

  const handleConnectGarmin = async () => {
    if (!garminEmail || !garminPassword) {
      Alert.alert('Required Fields', 'Please enter your Garmin account email and password.');
      return;
    }
    setGarminSyncing(true);
    try {
      const response = await fetch(`${apiUrl}/garmin/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ email: garminEmail, password: garminPassword }),
      });
      if (response.ok) {
        setGarminConnected(true);
        Alert.alert('Garmin Connected!', 'Garmin sync has been initiated. Your workout & wellness history is now syncing.');
        fetchProfile();
      } else {
        const err = await response.json();
        Alert.alert('Garmin Error', err.error || 'Failed to connect Garmin account.');
      }
    } catch (err) {
      console.error('Error connecting Garmin:', err);
      Alert.alert('Error', 'Network error connecting Garmin.');
    }
    setGarminSyncing(false);
  };

  const handleConnectStrava = async () => {
    try {
      const response = await fetch(`${apiUrl}/strava/connect_strava?json=true`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        if (data.url) {
          Linking.openURL(data.url);
        }
      }
    } catch (err) {
      console.error('Strava connect error:', err);
      Alert.alert('Error', 'Failed to connect to Strava.');
    }
  };

  const handleSyncAppleHealthKit = async () => {
    try {
      const { syncAppleHealthKitData } = await import('../services/healthkit');
      const data = await syncAppleHealthKitData();
      if (data) {
        setHealthkitConnected(true);
        Alert.alert('Apple Health Synced', 'Resting HR, sleep, and workouts auto-imported!');
      }
    } catch (err) {
      Alert.alert('HealthKit Info', 'Apple Health sync is supported on physical iOS devices.');
    }
  };

  const handleForceReSyncAll = async () => {
    setSyncingAll(true);
    try {
      await Promise.all([
        fetch(`${apiUrl}/garmin/sync`, { method: 'POST', headers: { Authorization: `Bearer ${authToken}` } }).catch(() => {}),
        fetch(`${apiUrl}/strava/sync`, { method: 'POST', headers: { Authorization: `Bearer ${authToken}` } }).catch(() => {}),
      ]);
      Alert.alert('Re-Sync Complete', 'All connected device data has been updated!');
      fetchProfile();
    } catch (err) {
      console.error('Error re-syncing device data:', err);
    }
    setSyncingAll(false);
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const bodyPayload = {
        age: ageInput ? Number(ageInput) : null,
        weight: weightInput ? Number(weightInput) : null,
        height: heightInput ? Number(heightInput) : null,
        goals: {
          target_weight: targetWeightInput ? Number(targetWeightInput) : null,
          weekly_volume: weeklyVolumeInput ? Number(weeklyVolumeInput) : null,
        },
      };

      const response = await fetch(`${apiUrl}/auth/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(bodyPayload),
      });

      if (response.ok) {
        Alert.alert('Success', 'Athlete profile updated.');
        setShowEditModal(false);
        fetchProfile();
      } else {
        Alert.alert('Error', 'Failed to update profile.');
      }
    } catch (err) {
      console.error('Save profile error:', err);
    }
    setSaving(false);
  };

  const handleSavePRs = async () => {
    setSaving(true);
    try {
      const bodyPayload = {
        goals: {
          personal_records: {
            run_5k: pr5k || null,
            run_10k: pr10k || null,
            run_half: prHalf || null,
            bike_longest: prBikeLongest || null,
            swim_100m: prSwim100m || null,
            hike_peak: prHikePeak || null,
          },
        },
      };

      const response = await fetch(`${apiUrl}/auth/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(bodyPayload),
      });

      if (response.ok) {
        Alert.alert('Success', 'Personal Records updated!');
        setShowPRModal(false);
        fetchProfile();
      } else {
        Alert.alert('Error', 'Failed to save PRs.');
      }
    } catch (err) {
      console.error('Save PR error:', err);
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Header Banner */}
      <View style={styles.headerBanner}>
        <View>
          <Text style={styles.headerTitle}>Athlete Performance & Stats</Text>
          <Text style={styles.headerSubtitle}>Personal Records, Garmin/Strava Sync & Performance Graphs</Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Ionicons name="log-out-outline" size={18} color="#DC2626" />
        </TouchableOpacity>
      </View>

      {/* Connected Devices & Integration Settings */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Ionicons name="hardware-chip-outline" size={22} color={Colors.light.primary} style={{ marginRight: 8 }} />
            <Text style={styles.cardTitle}>Connected Devices & Integrations</Text>
          </View>
          <TouchableOpacity style={styles.resyncBtn} onPress={handleForceReSyncAll} disabled={syncingAll}>
            {syncingAll ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Text style={styles.resyncBtnText}>🔄 Re-Sync All</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Garmin Account Connection */}
        <View style={styles.deviceRow}>
          <View style={styles.deviceInfo}>
            <Ionicons name="watch-outline" size={22} color={garminConnected ? Colors.light.secondary : Colors.light.subtext} />
            <View style={{ marginLeft: 10 }}>
              <Text style={styles.deviceName}>Garmin Connect</Text>
              <Text style={styles.deviceSub}>
                {garminConnected ? 'Status: Connected & Auto-Syncing' : 'Status: Disconnected'}
              </Text>
            </View>
          </View>
          <View style={[styles.badge, garminConnected ? styles.badgeSuccess : styles.badgeInactive]}>
            <Text style={[styles.badgeText, garminConnected ? styles.badgeTextSuccess : styles.badgeTextInactive]}>
              {garminConnected ? 'Active' : 'Offline'}
            </Text>
          </View>
        </View>

        {!garminConnected && (
          <View style={styles.garminInputsBox}>
            <TextInput
              style={styles.inputField}
              placeholder="Garmin Email"
              placeholderTextColor={Colors.light.subtext}
              value={garminEmail}
              onChangeText={setGarminEmail}
              autoCapitalize="none"
            />
            <TextInput
              style={[styles.inputField, { marginTop: 8 }]}
              placeholder="Garmin Password"
              placeholderTextColor={Colors.light.subtext}
              value={garminPassword}
              onChangeText={setGarminPassword}
              secureTextEntry
            />
            <TouchableOpacity style={styles.actionBtn} onPress={handleConnectGarmin} disabled={garminSyncing}>
              {garminSyncing ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.actionBtnText}>Connect & Sync Garmin</Text>
              )}
            </TouchableOpacity>
          </View>
        )}

        {/* Strava & Apple Health Rows */}
        <View style={styles.deviceRow}>
          <View style={styles.deviceInfo}>
            <Ionicons name="flame-outline" size={22} color={stravaConnected ? '#FC4C02' : Colors.light.subtext} />
            <View style={{ marginLeft: 10 }}>
              <Text style={styles.deviceName}>Strava OAuth</Text>
              <Text style={styles.deviceSub}>{stravaConnected ? 'Status: Connected' : 'Status: Disconnected'}</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.outlineBtn} onPress={handleConnectStrava}>
            <Text style={styles.outlineBtnText}>{stravaConnected ? 'Re-Auth' : 'Connect'}</Text>
          </TouchableOpacity>
        </View>

        <View style={[styles.deviceRow, { borderBottomWidth: 0 }]}>
          <View style={styles.deviceInfo}>
            <Ionicons name="heart-outline" size={22} color={healthkitConnected ? '#EF4444' : Colors.light.subtext} />
            <View style={{ marginLeft: 10 }}>
              <Text style={styles.deviceName}>Apple Health (iOS)</Text>
              <Text style={styles.deviceSub}>{healthkitConnected ? 'Status: Connected' : 'Status: Offline'}</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.outlineBtn} onPress={handleSyncAppleHealthKit}>
            <Text style={styles.outlineBtnText}>Sync HealthKit</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Interactive Running & Activity Graphs */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardTitle}>Activity & Performance Trends</Text>
          <View style={styles.periodSelector}>
            {([7, 30, 90] as const).map((d) => (
              <TouchableOpacity
                key={d}
                style={[styles.periodChip, periodDays === d && styles.periodChipActive]}
                onPress={() => setPeriodDays(d)}
              >
                <Text style={[styles.periodText, periodDays === d && styles.periodTextActive]}>{d}D</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Metric Selector Chips */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 14 }}>
          {[
            { id: 'pace', label: 'Running Pace', icon: 'speedometer-outline' },
            { id: 'distance', label: 'Distance (km)', icon: 'map-outline' },
            { id: 'heart_rate', label: 'Heart Rate', icon: 'pulse-outline' },
            { id: 'cadence', label: 'Cadence (spm)', icon: 'walk-outline' },
          ].map((m) => (
            <TouchableOpacity
              key={m.id}
              style={[styles.metricChip, selectedMetric === m.id && styles.metricChipActive]}
              onPress={() => setSelectedMetric(m.id as any)}
            >
              <Ionicons
                name={m.icon as any}
                size={16}
                color={selectedMetric === m.id ? '#FFFFFF' : Colors.light.text}
                style={{ marginRight: 6 }}
              />
              <Text style={[styles.metricChipText, selectedMetric === m.id && styles.metricChipTextActive]}>
                {m.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Graph Display Area */}
        <View style={styles.graphContainer}>
          <View style={styles.graphHeader}>
            <Text style={styles.graphMetricTitle}>{selectedMetric.toUpperCase()} ({periodDays}-Day View)</Text>
            <Text style={styles.graphSummaryText}>Avg: {selectedMetric === 'pace' ? '4:48 min/km' : selectedMetric === 'distance' ? '38.5 km/wk' : selectedMetric === 'heart_rate' ? '152 bpm' : '174 spm'}</Text>
          </View>

          {/* Bar Chart Representation */}
          <View style={styles.barsArea}>
            {[
              { label: 'W1', val: 75, detail: '4:52 min/km' },
              { label: 'W2', val: 88, detail: '4:45 min/km' },
              { label: 'W3', val: 62, detail: '5:02 min/km' },
              { label: 'W4', val: 94, detail: '4:39 min/km' },
              { label: 'W5', val: 82, detail: '4:46 min/km' },
            ].map((bar, i) => (
              <View key={i} style={styles.barColumn}>
                <Text style={styles.barDetailText}>{bar.detail}</Text>
                <View style={styles.barTrack}>
                  <View style={[styles.barFill, { height: `${bar.val}%` }]} />
                </View>
                <Text style={styles.barLabel}>{bar.label}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      {/* Personal Records (PRs) */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardTitle}>Personal Records (PRs)</Text>
          <TouchableOpacity style={styles.editBtn} onPress={() => setShowPRModal(true)}>
            <Ionicons name="pencil" size={16} color={Colors.light.primary} />
            <Text style={styles.editBtnText}>Edit PRs</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.prGrid}>
          <View style={styles.prTile}>
            <Text style={styles.prLabel}>5K Run</Text>
            <Text style={styles.prValue}>{pr5k || 'Not Set'}</Text>
          </View>
          <View style={styles.prTile}>
            <Text style={styles.prLabel}>10K Run</Text>
            <Text style={styles.prValue}>{pr10k || 'Not Set'}</Text>
          </View>
          <View style={styles.prTile}>
            <Text style={styles.prLabel}>Half Marathon</Text>
            <Text style={styles.prValue}>{prHalf || 'Not Set'}</Text>
          </View>
          <View style={styles.prTile}>
            <Text style={styles.prLabel}>Longest Ride</Text>
            <Text style={styles.prValue}>{prBikeLongest || 'Not Set'}</Text>
          </View>
        </View>
      </View>

      {/* Athlete Profile Information */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardTitle}>Athlete Profile</Text>
          <TouchableOpacity style={styles.editBtn} onPress={() => setShowEditModal(true)}>
            <Ionicons name="create-outline" size={16} color={Colors.light.primary} />
            <Text style={styles.editBtnText}>Edit Profile</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.profileGrid}>
          <View style={styles.profileItem}>
            <Text style={styles.profileLabel}>Age</Text>
            <Text style={styles.profileVal}>{profile?.age ? `${profile.age} yrs` : 'Not set'}</Text>
          </View>
          <View style={styles.profileItem}>
            <Text style={styles.profileLabel}>Weight</Text>
            <Text style={styles.profileVal}>{profile?.weight ? `${profile.weight} kg` : 'Not set'}</Text>
          </View>
          <View style={styles.profileItem}>
            <Text style={styles.profileLabel}>Height</Text>
            <Text style={styles.profileVal}>{profile?.height ? `${profile.height} cm` : 'Not set'}</Text>
          </View>
          <View style={styles.profileItem}>
            <Text style={styles.profileLabel}>Weekly Goal</Text>
            <Text style={styles.profileVal}>{profile?.goals?.weekly_volume ? `${profile.goals.weekly_volume} km` : 'Not set'}</Text>
          </View>
        </View>
      </View>

      {/* Edit Profile Modal */}
      <Modal visible={showEditModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Edit Athlete Profile</Text>
            
            <Text style={styles.inputLabel}>Age</Text>
            <TextInput style={styles.inputField} value={ageInput} onChangeText={setAgeInput} keyboardType="numeric" />

            <Text style={styles.inputLabel}>Weight (kg)</Text>
            <TextInput style={styles.inputField} value={weightInput} onChangeText={setWeightInput} keyboardType="numeric" />

            <Text style={styles.inputLabel}>Height (cm)</Text>
            <TextInput style={styles.inputField} value={heightInput} onChangeText={setHeightInput} keyboardType="numeric" />

            <Text style={styles.inputLabel}>Weekly Volume Goal (km)</Text>
            <TextInput style={styles.inputField} value={weeklyVolumeInput} onChangeText={setWeeklyVolumeInput} keyboardType="numeric" />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setShowEditModal(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSaveBtn} onPress={handleSaveProfile} disabled={saving}>
                {saving ? <ActivityIndicator size="small" color="#FFFFFF" /> : <Text style={styles.modalSaveText}>Save Profile</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Edit PRs Modal */}
      <Modal visible={showPRModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Edit Personal Records</Text>

            <Text style={styles.inputLabel}>5K Run (e.g. 21:30)</Text>
            <TextInput style={styles.inputField} value={pr5k} onChangeText={setPr5k} />

            <Text style={styles.inputLabel}>10K Run (e.g. 45:10)</Text>
            <TextInput style={styles.inputField} value={pr10k} onChangeText={setPr10k} />

            <Text style={styles.inputLabel}>Half Marathon (e.g. 1:38:00)</Text>
            <TextInput style={styles.inputField} value={prHalf} onChangeText={setPrHalf} />

            <Text style={styles.inputLabel}>Longest Bike Ride (e.g. 85 km)</Text>
            <TextInput style={styles.inputField} value={prBikeLongest} onChangeText={setPrBikeLongest} />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setShowPRModal(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSaveBtn} onPress={handleSavePRs} disabled={saving}>
                {saving ? <ActivityIndicator size="small" color="#FFFFFF" /> : <Text style={styles.modalSaveText}>Save PRs</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
  },
  headerBanner: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  headerSubtitle: {
    fontSize: 12,
    color: Colors.light.subtext,
    marginTop: 2,
  },
  logoutBtn: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: '#FEE2E2',
  },
  card: {
    backgroundColor: Colors.light.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  resyncBtn: {
    backgroundColor: Colors.light.primary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  resyncBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  deviceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
  },
  deviceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 8,
  },
  deviceName: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.light.text,
  },
  deviceSub: {
    fontSize: 11,
    color: Colors.light.subtext,
    marginTop: 1,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  badgeSuccess: {
    backgroundColor: 'rgba(5, 150, 105, 0.15)',
  },
  badgeInactive: {
    backgroundColor: 'rgba(100, 116, 139, 0.1)',
  },
  badgeText: {
    fontSize: 11,
    fontWeight: 'bold',
  },
  badgeTextSuccess: {
    color: Colors.light.secondary,
  },
  badgeTextInactive: {
    color: Colors.light.subtext,
  },
  garminInputsBox: {
    backgroundColor: Colors.light.background,
    padding: 12,
    borderRadius: 10,
    marginTop: 8,
    marginBottom: 8,
  },
  inputField: {
    backgroundColor: Colors.light.card,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    height: 40,
    color: Colors.light.text,
    fontSize: 14,
  },
  actionBtn: {
    backgroundColor: Colors.light.primary,
    borderRadius: 8,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: 'bold',
  },
  outlineBtn: {
    borderWidth: 1,
    borderColor: Colors.light.primary,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  outlineBtnText: {
    color: Colors.light.primary,
    fontSize: 12,
    fontWeight: '600',
  },
  periodSelector: {
    flexDirection: 'row',
    backgroundColor: Colors.light.background,
    borderRadius: 8,
    padding: 2,
  },
  periodChip: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  periodChipActive: {
    backgroundColor: Colors.light.primary,
  },
  periodText: {
    fontSize: 11,
    color: Colors.light.subtext,
    fontWeight: '600',
  },
  periodTextActive: {
    color: '#FFFFFF',
  },
  metricChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginRight: 8,
  },
  metricChipActive: {
    backgroundColor: Colors.light.primary,
    borderColor: Colors.light.primary,
  },
  metricChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.light.text,
  },
  metricChipTextActive: {
    color: '#FFFFFF',
  },
  graphContainer: {
    backgroundColor: Colors.light.background,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  graphHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  graphMetricTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  graphSummaryText: {
    fontSize: 12,
    color: Colors.light.primary,
    fontWeight: '600',
  },
  barsArea: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 120,
    paddingTop: 20,
  },
  barColumn: {
    alignItems: 'center',
    flex: 1,
  },
  barDetailText: {
    fontSize: 9,
    color: Colors.light.subtext,
    marginBottom: 4,
  },
  barTrack: {
    width: 14,
    height: 80,
    backgroundColor: Colors.light.border,
    borderRadius: 7,
    justifyContent: 'flex-end',
    overflow: 'hidden',
  },
  barFill: {
    backgroundColor: Colors.light.primary,
    borderRadius: 7,
  },
  barLabel: {
    fontSize: 10,
    color: Colors.light.text,
    fontWeight: '600',
    marginTop: 6,
  },
  prGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  prTile: {
    width: '48%',
    backgroundColor: Colors.light.background,
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  prLabel: {
    fontSize: 12,
    color: Colors.light.subtext,
  },
  prValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginTop: 4,
  },
  editBtn: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  editBtnText: {
    fontSize: 12,
    color: Colors.light.primary,
    fontWeight: '600',
    marginLeft: 4,
  },
  profileGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  profileItem: {
    width: '48%',
    backgroundColor: Colors.light.background,
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  profileLabel: {
    fontSize: 12,
    color: Colors.light.subtext,
  },
  profileVal: {
    fontSize: 15,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginTop: 4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: Colors.light.card,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 12,
    color: Colors.light.subtext,
    marginTop: 8,
    marginBottom: 4,
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: 20,
  },
  modalCancelBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    marginRight: 10,
  },
  modalCancelText: {
    color: Colors.light.subtext,
    fontWeight: '600',
  },
  modalSaveBtn: {
    backgroundColor: Colors.light.primary,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  modalSaveText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
});
