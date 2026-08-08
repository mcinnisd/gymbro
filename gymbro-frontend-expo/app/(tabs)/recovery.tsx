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

interface JournalEntry {
  answers: {
    energy_level: number;
    felt_sore: boolean;
    journal_text: string;
  };
}

export default function RecoveryScreen() {
  const { authToken, apiUrl } = useContext(AuthContext);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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

  useEffect(() => {
    if (authToken) {
      fetchTodayJournal();
      fetchFlaggedBiomarkers();
    }
  }, [authToken]);

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

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        
        {/* Health Hub & Lab Biomarkers Card */}
        <View style={styles.biomarkersCard}>
          <LinearGradient
            colors={['rgba(245, 158, 11, 0.12)', 'rgba(0, 229, 255, 0.05)']}
            style={styles.biomarkersGradient}
          >
            <View style={styles.biomarkersHeader}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="medical" size={18} color="#F59E0B" />
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
                      <View style={[styles.statusTag, { backgroundColor: isLow ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)' }]}>
                        <Text style={[styles.statusTagText, { color: isLow ? '#EF4444' : '#F59E0B' }]}>
                          {isLow ? 'LOW' : 'HIGH'}
                        </Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            ) : (
              <View style={{ alignItems: 'center', paddingVertical: 12 }}>
                <Text style={{ color: '#94A3B8', fontSize: 13, textAlign: 'center', marginBottom: 10 }}>
                  No bloodwork analyzed yet. Upload a lab PDF to track Ferritin, CRP, Vitamin D & more.
                </Text>
                <TouchableOpacity style={styles.emptyActionBtn} onPress={() => Alert.alert("Upload PDF", "PDF parsing feature: Upload your blood test PDF via chat or upload portal.")}>
                  <Ionicons name="cloud-upload-outline" size={16} color="#00E5FF" style={{ marginRight: 6 }} />
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
                colors={['rgba(0, 229, 255, 0.1)', 'rgba(0,0,0,0)']}
                style={styles.cardGradient}
              >
                <View style={styles.cardHeader}>
                  <Ionicons name="moon" size={16} color="#00E5FF" />
                  <Text style={styles.cardLabel}>Sleep Score</Text>
                </View>
                <Text style={styles.cardVal}>{sleepScore}/100</Text>
                <Text style={styles.cardSubText}>{sleepHours || '--'} total sleep</Text>
              </LinearGradient>
            </View>

            {/* RHR Card */}
            <View style={styles.statCard}>
              <LinearGradient
                colors={['rgba(108, 99, 255, 0.1)', 'rgba(0,0,0,0)']}
                style={styles.cardGradient}
              >
                <View style={styles.cardHeader}>
                  <Ionicons name="heart" size={16} color="#6C63FF" />
                  <Text style={styles.cardLabel}>RHR Trend</Text>
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
            <Ionicons name="watch-outline" size={24} color="#00E5FF" style={{ marginBottom: 6 }} />
            <Text style={{ color: '#F8FAFC', fontWeight: 'bold', fontSize: 14 }}>No Wearable Connected</Text>
            <Text style={{ color: '#94A3B8', fontSize: 12, textAlign: 'center', marginVertical: 6 }}>
              Connect your Garmin or Apple Health watch to automatically stream Resting HR, HRV, and Sleep scores.
            </Text>
            <TouchableOpacity style={styles.emptyActionBtn} onPress={() => Alert.alert("Sync Wearable", "Connect your Garmin or Strava account in the AI Coach Chat tab.")}>
              <Text style={styles.emptyActionBtnText}>⌚ Sync Device in Coach Chat</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Steps Card */}
        <View style={styles.largeCard}>
          <LinearGradient
            colors={['rgba(16, 185, 129, 0.08)', 'rgba(0,0,0,0)']}
            style={styles.cardGradientLarge}
          >
            <View style={styles.largeCardHeader}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="walk" size={20} color="#10B981" />
                <Text style={styles.largeCardTitle}>Daily Movement</Text>
              </View>
              <Text style={styles.largeCardRightText}>{stepsCount !== null ? `${stepsCount} / 10,000 steps` : 'Sync device for steps'}</Text>
            </View>
            <View style={styles.stepsBarBg}>
              <View style={[styles.stepsBarFill, { width: `${Math.min((stepsCount || 0) / 10000, 1) * 100}%` }]} />
            </View>
          </LinearGradient>
        </View>

        {/* RHR Trend Graph (Styled Mini SVG-Like Visualization) */}
        <View style={styles.graphCard}>
          <Text style={styles.graphTitle}>Resting Heart Rate History (7 Days)</Text>
          <View style={styles.graphContainer}>
            {rhrHistory.map((val, idx) => {
              // Normalize RHR between 50 and 70 for height (max 80px)
              const minVal = 50;
              const maxVal = 70;
              const barHeight = Math.max(((val - minVal) / (maxVal - minVal)) * 60, 10);
              return (
                <View key={idx} style={styles.graphCol}>
                  <Text style={styles.graphVal}>{val}</Text>
                  <View style={[styles.graphBar, { height: barHeight, width: 14, backgroundColor: '#6C63FF', borderRadius: 4 }]} />
                  <Text style={styles.graphLabel}>D-{6 - idx}</Text>
                </View>
              );
            })}
          </View>
        </View>

        {/* Daily Recovery Journal Card */}
        <View style={styles.journalCard}>
          <Text style={styles.journalHeader}>📝 Daily Journal & Check-In</Text>
          <Text style={styles.journalSubHeader}>How did your body feel today, bro?</Text>
          
          {loading ? (
            <ActivityIndicator size="small" color="#00E5FF" style={{ marginVertical: 20 }} />
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
                  {feltSore && <Ionicons name="checkmark" size={14} color="#020617" />}
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
                placeholderTextColor="#64748B"
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
    backgroundColor: '#0A0E17',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 90, // space for drawer peek
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 12,
    marginHorizontal: 4,
    borderWidth: 1,
    borderColor: '#334155',
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
    color: '#94A3B8',
    marginLeft: 6,
  },
  cardVal: {
    fontSize: 20,
    fontWeight: '900',
    color: '#FFFFFF',
  },
  cardSubText: {
    fontSize: 10,
    color: '#64748B',
    marginTop: 4,
  },
  largeCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
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
    color: '#F8FAFC',
    fontWeight: 'bold',
    fontSize: 14,
    marginLeft: 8,
  },
  largeCardRightText: {
    color: '#10B981',
    fontWeight: 'bold',
    fontSize: 13,
  },
  stepsBarBg: {
    height: 6,
    backgroundColor: '#0F172A',
    borderRadius: 3,
    overflow: 'hidden',
  },
  stepsBarFill: {
    height: '100%',
    backgroundColor: '#10B981',
    borderRadius: 3,
  },
  graphCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 16,
    marginBottom: 16,
  },
  graphTitle: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  graphContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 90,
  },
  graphCol: {
    alignItems: 'center',
    flex: 1,
  },
  graphVal: {
    fontSize: 9,
    color: '#00E5FF',
    fontWeight: '600',
    marginBottom: 4,
  },
  graphBar: {
    width: 12,
    backgroundColor: '#6C63FF',
    borderRadius: 3,
  },
  graphLabel: {
    fontSize: 8,
    color: '#64748B',
    marginTop: 6,
  },
  journalCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 20,
    marginBottom: 20,
  },
  journalHeader: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  journalSubHeader: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 4,
    marginBottom: 16,
  },
  journalForm: {},
  formLabel: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#94A3B8',
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
    backgroundColor: '#0F172A',
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 2,
    borderWidth: 1,
    borderColor: '#334155',
  },
  ratingButtonSelected: {
    backgroundColor: '#00E5FF',
    borderColor: '#00E5FF',
  },
  ratingText: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: 'bold',
  },
  ratingTextSelected: {
    color: '#020617',
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
    borderColor: '#334155',
    backgroundColor: '#0F172A',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  checkboxSelected: {
    backgroundColor: '#00E5FF',
    borderColor: '#00E5FF',
  },
  checkboxLabel: {
    color: '#E0E6ED',
    fontSize: 13,
  },
  journalInput: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    color: '#F8FAFC',
    padding: 12,
    fontSize: 14,
    textAlignVertical: 'top',
    height: 80,
    marginBottom: 16,
  },
  saveBtn: {
    height: 44,
    backgroundColor: '#6C63FF',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnSuccess: {
    backgroundColor: '#10B981',
  },
  saveBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  biomarkersCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
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
    color: '#F8FAFC',
    fontWeight: 'bold',
    fontSize: 14,
    marginLeft: 8,
  },
  syncBadge: {
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  syncBadgeText: {
    color: '#F59E0B',
    fontSize: 10,
    fontWeight: 'bold',
  },
  biomarkerItemsRow: {
    gap: 8,
  },
  biomarkerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0F172A',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  biomarkerDotWarning: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#EF4444',
    marginRight: 8,
  },
  biomarkerDotOptimal: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#10B981',
    marginRight: 8,
  },
  biomarkerName: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginRight: 6,
  },
  biomarkerValue: {
    fontSize: 12,
    color: '#94A3B8',
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
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#00E5FF',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    marginTop: 4,
  },
  emptyActionBtnText: {
    color: '#00E5FF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  emptyWearableCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 16,
    marginBottom: 16,
    alignItems: 'center',
  },
});
