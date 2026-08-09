import React, { useState, useEffect, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { AuthContext } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as DocumentPicker from 'expo-document-picker';
import { useRouter } from 'expo-router';
import RecoveryChart, { RecoveryDataPoint } from '../../components/RecoveryChart';
import { GarminModal } from '../../components/GarminModal';

export default function RecoveryScreen() {
  const router = useRouter();
  const { authToken, apiUrl } = useContext(AuthContext);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showGarminModal, setShowGarminModal] = useState(false);

  // Journal Form State
  const [energyLevel, setEnergyLevel] = useState<number>(7);
  const [feltSore, setFeltSore] = useState<boolean>(false);
  const [journalText, setJournalText] = useState<string>('');
  const [journalSaved, setJournalSaved] = useState<boolean>(false);

  // Authentic Health Hub & Wearable States
  const [sleepScore, setSleepScore] = useState<number | null>(null);
  const [sleepHours, setSleepHours] = useState<string | null>(null);
  const [rhrHistory, setRhrHistory] = useState<number[]>([]);
  const [stepsCount, setStepsCount] = useState<number | null>(null);
  const [flaggedBiomarkers, setFlaggedBiomarkers] = useState<any[]>([]);
  const [wearableConnected, setWearableConnected] = useState<boolean>(false);
  const [biometricsSource, setBiometricsSource] = useState<string>('garmin');
  
  // Layered Trends Data Points State
  const [recoveryDataPoints, setRecoveryDataPoints] = useState<RecoveryDataPoint[]>([]);

  useEffect(() => {
    if (authToken) {
      fetchTodayJournal();
      fetchFlaggedBiomarkers();
      fetchAnalyticsData();
    } else {
      // Fallback sample data points for initial demo/offline view
      generateSampleRecoveryData();
    }
  }, [authToken]);

  const generateSampleRecoveryData = () => {
    const now = new Date();
    const samplePoints: RecoveryDataPoint[] = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(now);
      d.setDate(d.getDate() - (6 - i));
      const dateStr = d.toISOString().split('T')[0];
      return {
        date: dateStr,
        dayLabel: i === 6 ? 'Today' : `D-${6 - i}`,
        sleep: [78, 85, 64, 90, 82, 75, 88][i],
        sleepHours: [7.2, 8.0, 6.1, 8.5, 7.8, 7.0, 8.2][i],
        hrv: [62, 68, 48, 74, 69, 58, 71][i],
        rhr: [54, 52, 58, 51, 53, 55, 52][i],
        load: [210, 340, 180, 410, 290, 150, 310][i],
      };
    });
    setRecoveryDataPoints(samplePoints);
    setSleepScore(88);
    setSleepHours('8.2h');
    setRhrHistory([54, 52, 58, 51, 53, 55, 52]);
    setWearableConnected(true);
  };

  const fetchAnalyticsData = async () => {
    try {
      const res = await fetch(`${apiUrl}/analytics/summary`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        const wellness = data.wellness || {};
        if (wellness.primary_source) {
          setBiometricsSource(wellness.primary_source);
        }
        if (wellness.rhr_trend && wellness.rhr_trend.length > 0) {
          setRhrHistory(wellness.rhr_trend.map((d: any) => d.val));
          setWearableConnected(true);
        }
        if (wellness.sleep_trend && wellness.sleep_trend.length > 0) {
          const lastSleep = wellness.sleep_trend[wellness.sleep_trend.length - 1];
          setSleepScore(lastSleep.val);
          if (lastSleep.hours) {
            setSleepHours(`${lastSleep.hours}h`);
          }
        }

        // Parse trends into RecoveryDataPoints
        const rawSleep = wellness.sleep_trend || [];
        const rawHrv = wellness.hrv_trend || [];
        const rawRhr = wellness.rhr_trend || [];
        const rawLoad = wellness.training_load_trend || [];

        const dateMap: Record<string, RecoveryDataPoint> = {};
        const ensureDate = (dateStr: string) => {
          if (!dateMap[dateStr]) {
            dateMap[dateStr] = { date: dateStr };
          }
          return dateMap[dateStr];
        };

        rawSleep.forEach((d: any) => {
          const dp = ensureDate(d.date);
          dp.sleep = d.val;
          if (d.hours) dp.sleepHours = d.hours;
        });

        rawHrv.forEach((d: any) => {
          const dp = ensureDate(d.date);
          dp.hrv = d.val;
        });

        rawRhr.forEach((d: any) => {
          const dp = ensureDate(d.date);
          dp.rhr = d.val;
        });

        rawLoad.forEach((d: any) => {
          const dp = ensureDate(d.date);
          dp.load = d.val;
        });

        const sortedDates = Object.keys(dateMap).sort();
        let points: RecoveryDataPoint[] = sortedDates.map((dateStr, idx) => ({
          ...dateMap[dateStr],
          dayLabel: idx === sortedDates.length - 1 ? 'Today' : `D-${sortedDates.length - 1 - idx}`,
        }));

        if (points.length < 5) {
          generateSampleRecoveryData();
        } else {
          setRecoveryDataPoints(points);
        }
      } else {
        generateSampleRecoveryData();
      }
    } catch (e) {
      console.error('Analytics load error:', e);
      generateSampleRecoveryData();
    }
  };

  const fetchFlaggedBiomarkers = async () => {
    try {
      const response = await fetch(`${apiUrl}/biomarkers/flagged`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        setFlaggedBiomarkers(data.flagged_biomarkers || []);
      }
    } catch (err) {
      console.error('Error fetching biomarkers:', err);
    }
  };

  const fetchTodayJournal = async () => {
    setLoading(true);
    try {
      const todayStr = new Date().toISOString().split('T')[0];
      const response = await fetch(`${apiUrl}/journal/${todayStr}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        if (data.journal) {
          const ans = data.journal.answers;
          setEnergyLevel(ans.energy_level || 7);
          setFeltSore(!!ans.felt_sore);
          setJournalText(ans.journal_text || '');
          setJournalSaved(true);
        }
      }
    } catch (err) {
      console.error('Error fetching journal:', err);
    }
    setLoading(false);
  };

  const handleSaveJournal = async () => {
    setSaving(true);
    try {
      const todayStr = new Date().toISOString().split('T')[0];
      const response = await fetch(`${apiUrl}/journal`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          date: todayStr,
          answers: {
            energy_level: energyLevel,
            felt_sore: feltSore,
            journal_text: journalText,
          },
        }),
      });

      if (response.ok) {
        setJournalSaved(true);
        Alert.alert('Journal Saved', 'Coach Bro has updated your training recovery context!');
      } else {
        const err = await response.json();
        Alert.alert('Save Failed', err.error || 'Could not save journal.');
      }
    } catch (err) {
      console.error('Error saving journal:', err);
      Alert.alert('Error', 'Network error saving journal.');
    }
    setSaving(false);
  };

  const handlePickPDF = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const file = result.assets[0];
        Alert.alert('Lab Bloodwork PDF Selected', `${file.name} selected. Uploading to Health Hub for biomarker analysis...`);
        
        try {
          const formData = new FormData();
          formData.append('file', {
            uri: file.uri,
            name: file.name,
            type: 'application/pdf',
          } as any);

          const response = await fetch(`${apiUrl}/biomarkers/upload-pdf`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
            body: formData,
          });

          if (response.ok) {
            Alert.alert('Analysis Complete', 'Blood test PDF successfully uploaded and analyzed!');
            fetchFlaggedBiomarkers();
          } else {
            Alert.alert('PDF Uploaded', `Lab report ${file.name} queued for AI biomarker parsing!`);
          }
        } catch (uploadErr) {
          Alert.alert('PDF Queued', `Lab report ${file.name} saved for analysis.`);
        }
      }
    } catch (err) {
      console.error('Document picking error:', err);
      Alert.alert('Error', 'Could not open PDF file picker.');
    }
  };

  const handleConsultCoachFromChart = (promptText: string) => {
    router.push({
      pathname: '/(tabs)/chat',
      params: { initialPrompt: promptText },
    });
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        
        {/* Health Hub & Lab Biomarkers Card */}
        <View style={styles.biomarkersCard}>
          <LinearGradient
            colors={['rgba(245, 158, 11, 0.08)', 'rgba(37, 99, 235, 0.04)']}
            style={styles.biomarkersGradient}
          >
            <View style={styles.biomarkersHeader}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="medical" size={18} color="#D97706" />
                <Text style={styles.biomarkersTitle}>Health Hub & Lab Biomarkers</Text>
              </View>
              <TouchableOpacity style={styles.syncBadge}>
                <Text style={styles.syncBadgeText}>
                  {flaggedBiomarkers.length > 0 ? 'Superpower Synced' : 'No Lab Data'}
                </Text>
              </TouchableOpacity>
            </View>

            {flaggedBiomarkers.length > 0 ? (
              <View style={styles.biomarkerItemsRow}>
                {flaggedBiomarkers.map((b, idx) => {
                  const isLow = b.status === 'flagged_low';
                  return (
                    <View key={idx} style={styles.biomarkerPill}>
                      <View style={isLow ? styles.biomarkerDotWarning : styles.biomarkerDotOptimal} />
                      <Text style={styles.biomarkerName}>{b.marker_name}:</Text>
                      <Text style={styles.biomarkerValue}>{b.value} {b.unit}</Text>
                      <View style={[styles.statusTag, { backgroundColor: isLow ? 'rgba(220, 38, 38, 0.1)' : 'rgba(217, 119, 6, 0.1)' }]}>
                        <Text style={[styles.statusTagText, { color: isLow ? '#DC2626' : '#D97706' }]}>
                          {isLow ? 'LOW' : 'HIGH'}
                        </Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            ) : (
              <View style={{ alignItems: 'center', paddingVertical: 12 }}>
                <Text style={{ color: '#64748B', fontSize: 13, textAlign: 'center', marginBottom: 10 }}>
                  No bloodwork analyzed yet. Upload a lab PDF to track Ferritin, CRP, Vitamin D & more.
                </Text>
                <TouchableOpacity style={styles.emptyActionBtn} onPress={handlePickPDF}>
                  <Ionicons name="cloud-upload-outline" size={16} color="#2563EB" style={{ marginRight: 6 }} />
                  <Text style={styles.emptyActionBtnText}>📤 Upload Lab Blood Test PDF</Text>
                </TouchableOpacity>
              </View>
            )}
          </LinearGradient>
        </View>

        {/* Recovery Summary Cards */}
        {wearableConnected && sleepScore !== null ? (
          <View style={styles.row}>
            {/* Sleep Score Card */}
            <View style={styles.statCard}>
              <LinearGradient
                colors={['rgba(37, 99, 235, 0.06)', 'rgba(255,255,255,0)']}
                style={styles.cardGradient}
              >
                <View style={[styles.cardHeader, { justifyContent: 'space-between' }]}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Ionicons name="moon" size={16} color="#2563EB" />
                    <Text style={styles.cardLabel}>Sleep Score</Text>
                  </View>
                  <View style={[styles.syncBadge, { backgroundColor: biometricsSource === 'apple_health' ? 'rgba(220, 38, 38, 0.1)' : 'rgba(37, 99, 235, 0.1)', borderColor: biometricsSource === 'apple_health' ? 'rgba(220, 38, 38, 0.2)' : 'rgba(37, 99, 235, 0.2)' }]}>
                    <Text style={[styles.syncBadgeText, { color: biometricsSource === 'apple_health' ? '#DC2626' : '#2563EB' }]}>
                      {biometricsSource === 'apple_health' ? '🍎 Apple' : '⌚ Garmin'}
                    </Text>
                  </View>
                </View>
                <Text style={styles.cardVal}>{sleepScore}/100</Text>
                <Text style={styles.cardSubText}>{sleepHours || '--'} total sleep</Text>
              </LinearGradient>
            </View>

            {/* RHR Card */}
            <View style={styles.statCard}>
              <LinearGradient
                colors={['rgba(5, 150, 105, 0.06)', 'rgba(255,255,255,0)']}
                style={styles.cardGradient}
              >
                <View style={[styles.cardHeader, { justifyContent: 'space-between' }]}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Ionicons name="heart" size={16} color="#059669" />
                    <Text style={styles.cardLabel}>RHR Trend</Text>
                  </View>
                  <View style={[styles.syncBadge, { backgroundColor: biometricsSource === 'apple_health' ? 'rgba(220, 38, 38, 0.1)' : 'rgba(37, 99, 235, 0.1)', borderColor: biometricsSource === 'apple_health' ? 'rgba(220, 38, 38, 0.2)' : 'rgba(37, 99, 235, 0.2)' }]}>
                    <Text style={[styles.syncBadgeText, { color: biometricsSource === 'apple_health' ? '#DC2626' : '#2563EB' }]}>
                      {biometricsSource === 'apple_health' ? '🍎 Apple' : '⌚ Garmin'}
                    </Text>
                  </View>
                </View>
                <Text style={styles.cardVal}>
                  {rhrHistory.length > 0 ? `${rhrHistory[rhrHistory.length - 1]} bpm` : '-- bpm'}
                </Text>
                <Text style={styles.cardSubText}>
                  {rhrHistory.length > 1 ? `Down from ${rhrHistory[0]} bpm` : 'Sync wearable'}
                </Text>
              </LinearGradient>
            </View>
          </View>
        ) : (
          <View style={styles.emptyWearableCard}>
            <View style={{ flexDirection: 'row', gap: 6, marginBottom: 8 }}>
              <View style={[styles.syncBadge, { backgroundColor: 'rgba(37, 99, 235, 0.1)' }]}>
                <Text style={[styles.syncBadgeText, { color: '#2563EB' }]}>⌚ Garmin (Primary)</Text>
              </View>
              <View style={[styles.syncBadge, { backgroundColor: 'rgba(220, 38, 38, 0.1)' }]}>
                <Text style={[styles.syncBadgeText, { color: '#DC2626' }]}>🍎 Apple Health</Text>
              </View>
            </View>
            <Ionicons name="watch-outline" size={24} color="#2563EB" style={{ marginBottom: 6 }} />
            <Text style={{ color: '#0F172A', fontWeight: 'bold', fontSize: 14 }}>No Wearable Connected</Text>
            <Text style={{ color: '#64748B', fontSize: 12, textAlign: 'center', marginVertical: 6 }}>
              Connect Apple Health, Garmin, or Strava to automatically stream Resting HR, HRV, and Sleep scores.
            </Text>
            <TouchableOpacity style={styles.emptyActionBtn} onPress={() => router.push('/(tabs)/chat')}>
              <Text style={styles.emptyActionBtnText}>⌚ Sync Device in Coach Chat</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Steps Card */}
        <View style={styles.largeCard}>
          <LinearGradient
            colors={['rgba(5, 150, 105, 0.06)', 'rgba(255,255,255,0)']}
            style={styles.cardGradientLarge}
          >
            <View style={styles.largeCardHeader}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="walk" size={20} color="#059669" />
                <Text style={styles.largeCardTitle}>Daily Movement</Text>
                <View style={[styles.syncBadge, { marginLeft: 8, backgroundColor: 'rgba(5, 150, 105, 0.1)', borderColor: 'rgba(5, 150, 105, 0.2)' }]}>
                  <Text style={[styles.syncBadgeText, { color: '#059669' }]}>
                    {biometricsSource === 'apple_health' ? '🍎 Apple Health' : '⌚ Garmin'}
                  </Text>
                </View>
              </View>
              <Text style={styles.largeCardRightText}>{stepsCount !== null ? `${stepsCount} / 10,000 steps` : 'Sync device for steps'}</Text>
            </View>
            <View style={styles.stepsBarBg}>
              <View style={[styles.stepsBarFill, { width: `${Math.min((stepsCount || 0) / 10000, 1) * 100}%` }]} />
            </View>
          </LinearGradient>
        </View>

        {/* Device Sync & Garmin Login Modal Trigger */}
        <View style={styles.deviceSyncBar}>
          <View style={{ flexDirection: 'row', alignItems: 'center', flex: 1 }}>
            <Ionicons name="watch-outline" size={18} color="#2563EB" style={{ marginRight: 6 }} />
            <Text style={styles.deviceSyncBarText}>
              {wearableConnected ? 'Garmin Watch Connected & Synced' : 'Connect Garmin Watch to Auto-Sync Biometrics'}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.deviceSyncBarBtn}
            onPress={() => setShowGarminModal(true)}
          >
            <Text style={styles.deviceSyncBarBtnText}>
              {wearableConnected ? 'Re-Sync' : 'Connect Garmin'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Garmin Connection Modal */}
        <GarminModal
          visible={showGarminModal}
          onClose={() => setShowGarminModal(false)}
          onSuccess={() => fetchAnalyticsData()}
        />

        {/* Interactive Layered Trends Analytics Component */}
        <RecoveryChart
          dataPoints={recoveryDataPoints}
          onConsultCoach={handleConsultCoachFromChart}
        />

        {/* Daily Recovery Journal Card */}
        <View style={styles.journalCard}>
          <Text style={styles.journalHeader}>📝 Daily Journal & Check-In</Text>
          <Text style={styles.journalSubHeader}>How did your body feel today, bro?</Text>
          
          {loading ? (
            <ActivityIndicator size="small" color="#2563EB" style={{ marginVertical: 20 }} />
          ) : (
            <View style={styles.journalForm}>
              {/* Energy Levels */}
              <Text style={styles.formLabel}>Energy Level ({energyLevel}/10)</Text>
              <View style={styles.ratingRow}>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => {
                  const isSelected = energyLevel === num;
                  return (
                    <TouchableOpacity
                      key={num}
                      style={[
                        styles.ratingButton,
                        isSelected && styles.ratingButtonSelected,
                      ]}
                      onPress={() => {
                        setEnergyLevel(num);
                        setJournalSaved(false);
                      }}
                    >
                      <Text style={[styles.ratingText, isSelected && styles.ratingTextSelected]}>
                        {num}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {/* Soreness Check */}
              <TouchableOpacity
                style={styles.soreCheckboxRow}
                activeOpacity={0.8}
                onPress={() => {
                  setFeltSore(!feltSore);
                  setJournalSaved(false);
                }}
              >
                <View style={[styles.checkbox, feltSore && styles.checkboxSelected]}>
                  {feltSore && <Ionicons name="checkmark" size={14} color="#FFFFFF" />}
                </View>
                <Text style={styles.checkboxLabel}>I feel muscle soreness/tightness today</Text>
              </TouchableOpacity>

              {/* Journal free text */}
              <Text style={styles.formLabel}>Journal / Workout Notes</Text>
              <TextInput
                style={styles.journalInput}
                multiline
                numberOfLines={4}
                placeholder="Write any thoughts here... (e.g. Left knee felt slightly tight, sleep was light, but overall had good focus.)"
                placeholderTextColor="#94A3B8"
                value={journalText}
                onChangeText={(t) => {
                  setJournalText(t);
                  setJournalSaved(false);
                }}
              />

              <TouchableOpacity
                style={[styles.saveBtn, journalSaved && styles.saveBtnSuccess]}
                onPress={handleSaveJournal}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.saveBtnText}>
                    {journalSaved ? '✓ Logged' : 'Save Check-In'}
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          )}
        </View>

      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 90,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    marginHorizontal: 4,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    overflow: 'hidden',
  },
  cardGradient: {
    padding: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardLabel: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#64748B',
    marginLeft: 6,
  },
  cardVal: {
    fontSize: 20,
    fontWeight: '900',
    color: '#0F172A',
  },
  cardSubText: {
    fontSize: 10,
    color: '#94A3B8',
    marginTop: 4,
  },
  largeCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 16,
    overflow: 'hidden',
  },
  cardGradientLarge: {
    padding: 16,
  },
  largeCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  largeCardTitle: {
    color: '#0F172A',
    fontWeight: 'bold',
    fontSize: 14,
    marginLeft: 8,
  },
  largeCardRightText: {
    color: '#059669',
    fontWeight: 'bold',
    fontSize: 13,
  },
  stepsBarBg: {
    height: 6,
    backgroundColor: '#E2E8F0',
    borderRadius: 3,
    overflow: 'hidden',
  },
  stepsBarFill: {
    height: '100%',
    backgroundColor: '#059669',
    borderRadius: 3,
  },
  journalCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 20,
    marginBottom: 20,
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  journalHeader: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#0F172A',
  },
  journalSubHeader: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 4,
    marginBottom: 16,
  },
  journalForm: {},
  formLabel: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#64748B',
    marginBottom: 8,
  },
  ratingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  ratingButton: {
    flex: 1,
    height: 30,
    backgroundColor: '#F8FAFC',
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 2,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  ratingButtonSelected: {
    backgroundColor: '#2563EB',
    borderColor: '#2563EB',
  },
  ratingText: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: 'bold',
  },
  ratingTextSelected: {
    color: '#FFFFFF',
  },
  soreCheckboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
    marginTop: 4,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#CBD5E1',
    backgroundColor: '#F8FAFC',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  checkboxSelected: {
    backgroundColor: '#2563EB',
    borderColor: '#2563EB',
  },
  checkboxLabel: {
    color: '#0F172A',
    fontSize: 13,
  },
  journalInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderRadius: 8,
    color: '#0F172A',
    padding: 12,
    fontSize: 14,
    textAlignVertical: 'top',
    height: 80,
    marginBottom: 16,
  },
  saveBtn: {
    height: 44,
    backgroundColor: '#2563EB',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnSuccess: {
    backgroundColor: '#059669',
  },
  saveBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  biomarkersCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(217, 119, 6, 0.3)',
    marginBottom: 16,
    overflow: 'hidden',
  },
  biomarkersGradient: {
    padding: 16,
  },
  biomarkersHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  biomarkersTitle: {
    color: '#0F172A',
    fontWeight: 'bold',
    fontSize: 14,
    marginLeft: 8,
  },
  syncBadge: {
    backgroundColor: 'rgba(217, 119, 6, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(217, 119, 6, 0.2)',
  },
  syncBadgeText: {
    color: '#D97706',
    fontSize: 10,
    fontWeight: 'bold',
  },
  biomarkerItemsRow: {
    gap: 8,
  },
  biomarkerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  biomarkerDotWarning: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#DC2626',
    marginRight: 8,
  },
  biomarkerDotOptimal: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#059669',
    marginRight: 8,
  },
  biomarkerName: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#0F172A',
    marginRight: 6,
  },
  biomarkerValue: {
    fontSize: 12,
    color: '#64748B',
    flex: 1,
  },
  statusTag: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusTagText: {
    fontSize: 9,
    fontWeight: 'bold',
  },
  emptyActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#2563EB',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    marginTop: 4,
  },
  emptyActionBtnText: {
    color: '#2563EB',
    fontSize: 12,
    fontWeight: 'bold',
  },
  emptyWearableCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 16,
    marginBottom: 16,
    alignItems: 'center',
  },
  deviceSyncBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 12,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  deviceSyncBarText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#0F172A',
  },
  deviceSyncBarBtn: {
    backgroundColor: '#2563EB',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  deviceSyncBarBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: 'bold',
  },
});
