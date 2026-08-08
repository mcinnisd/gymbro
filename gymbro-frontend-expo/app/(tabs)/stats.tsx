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
} from 'react-native';
import { AuthContext } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

interface ProfileData {
  age: number | null;
  weight: number | null;
  height: number | null;
  goals: Record<string, any>;
}

export default function StatsScreen() {
  const { authToken, logout, apiUrl } = useContext(AuthContext);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Edit Profile Modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [ageInput, setAgeInput] = useState('');
  const [weightInput, setWeightInput] = useState('');
  const [heightInput, setHeightInput] = useState('');
  const [targetWeightInput, setTargetWeightInput] = useState('');
  const [weeklyVolumeInput, setWeeklyVolumeInput] = useState('');
  const [aiModel, setAiModel] = useState('gemini-3.1-flash-lite');

  // Edit PR Modal
  const [showPRModal, setShowPRModal] = useState(false);
  const [pr5k, setPr5k] = useState('');
  const [pr10k, setPr10k] = useState('');
  const [prHalf, setPrHalf] = useState('');
  const [prBikeLongest, setPrBikeLongest] = useState('');
  const [prSwim100m, setPrSwim100m] = useState('');
  const [prHikePeak, setPrHikePeak] = useState('');
  
  // Custom PR state (Strength, Lifting, Custom Sports)
  const [customPRName, setCustomPRName] = useState('');
  const [customPRValue, setCustomPRValue] = useState('');
  const [customPRList, setCustomPRList] = useState<Array<{ name: string; value: string }>>([]);

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
        setProfile(data.user);
        
        // Populate inputs
        setAgeInput(data.user.age ? String(data.user.age) : '');
        setWeightInput(data.user.weight ? String(data.user.weight) : '');
        setHeightInput(data.user.height ? String(data.user.height) : '');
        
        const gls = data.user.goals || {};
        setTargetWeightInput(gls.target_weight ? String(gls.target_weight) : '');
        setWeeklyVolumeInput(gls.weekly_volume ? String(gls.weekly_volume) : '');
        setAiModel(gls.llm_model || 'gemini-3.1-flash-lite');

        // Populate PRs if stored inside goals
        const prs = gls.personal_records || {};
        setPr5k(prs.run_5k || '');
        setPr10k(prs.run_10k || '');
        setPrHalf(prs.run_half || '');
        setPrBikeLongest(prs.bike_longest || '');
        setPrSwim100m(prs.swim_100m || '');
        setPrHikePeak(prs.hike_peak || '');
        setCustomPRList(prs.custom_prs || []);
      }
    } catch (err) {
      console.error('Error fetching user profile:', err);
    }
    setLoading(false);
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const bodyPayload = {
        age: ageInput ? Number(ageInput) : null,
        weight: weightInput ? Number(weightInput) : null,
        height: heightInput ? Number(heightInput) : null,
        llm_model: aiModel,
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
        Alert.alert('Profile Saved', 'Stats and goals updated successfully!');
        setShowEditModal(false);
        fetchProfile();
      } else {
        const err = await response.json();
        Alert.alert('Failed', err.error || 'Failed to update profile.');
      }
    } catch (err) {
      console.error('Error updating profile:', err);
      Alert.alert('Error', 'Network error saving profile changes.');
    }
    setSaving(false);
  };

  const handleAddCustomPR = () => {
    if (!customPRName.trim() || !customPRValue.trim()) return;
    const updated = [...customPRList, { name: customPRName.trim(), value: customPRValue.trim() }];
    setCustomPRList(updated);
    setCustomPRName('');
    setCustomPRValue('');
  };

  const handleRemoveCustomPR = (index: number) => {
    const updated = customPRList.filter((_, idx) => idx !== index);
    setCustomPRList(updated);
  };

  const handleSavePRs = async () => {
    setSaving(true);
    try {
      const bodyPayload = {
        goals: {
          personal_records: {
            run_5k: pr5k,
            run_10k: pr10k,
            run_half: prHalf,
            bike_longest: prBikeLongest,
            swim_100m: prSwim100m,
            hike_peak: prHikePeak,
            custom_prs: customPRList,
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
        Alert.alert('PRs Saved', 'Personal Records updated successfully!');
        setShowPRModal(false);
        fetchProfile();
      } else {
        const err = await response.json();
        Alert.alert('Failed', err.error || 'Failed to update PRs.');
      }
    } catch (err) {
      console.error('Error updating PRs:', err);
      Alert.alert('Error', 'Network error saving PR changes.');
    }
    setSaving(false);
  };

  const hasAnyPR = pr5k || pr10k || prHalf || prBikeLongest || prSwim100m || prHikePeak || customPRList.length > 0;

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        
        {/* Profile Card Header */}
        <View style={styles.profileSummaryCard}>
          <LinearGradient
            colors={['rgba(108, 99, 255, 0.15)', 'rgba(0,0,0,0)']}
            style={styles.profileSummaryGradient}
          >
            <View style={styles.profileHeaderRow}>
              <View style={styles.avatarCircle}>
                <Ionicons name="person" size={28} color="#00E5FF" />
              </View>
              <View style={styles.profileMeta}>
                <Text style={styles.profileTitle}>Athlete Dashboard</Text>
                <Text style={styles.profileSubtitle}>
                  {profile?.age || '--'} yrs • {profile?.weight || '--'} kg • {profile?.height || '--'} cm
                </Text>
              </View>
              <TouchableOpacity style={styles.editIconBtn} onPress={() => setShowEditModal(true)}>
                <Ionicons name="create-outline" size={20} color="#00E5FF" />
              </TouchableOpacity>
            </View>
          </LinearGradient>
        </View>

        {/* PRs Section */}
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>🏆 Personal Records (PRs)</Text>
          <TouchableOpacity style={styles.editPrBtn} onPress={() => setShowPRModal(true)}>
            <Text style={styles.editPrText}>+ Edit / Add PRs</Text>
          </TouchableOpacity>
        </View>

        {/* PR Cards Grid */}
        {hasAnyPR ? (
          <View style={styles.prGrid}>
            {/* Run card */}
            {(pr5k || pr10k || prHalf) ? (
              <View style={styles.prCard}>
                <View style={[styles.badgeContainer, { backgroundColor: 'rgba(16, 185, 129, 0.1)' }]}>
                  <Ionicons name="walk" size={20} color="#10B981" />
                </View>
                <Text style={styles.prSportTitle}>Running</Text>
                {pr5k ? <Text style={styles.prStatLabel}>5k: <Text style={styles.prStatValue}>{pr5k}</Text></Text> : null}
                {pr10k ? <Text style={styles.prStatLabel}>10k: <Text style={styles.prStatValue}>{pr10k}</Text></Text> : null}
                {prHalf ? <Text style={styles.prStatLabel}>Half: <Text style={styles.prStatValue}>{prHalf}</Text></Text> : null}
              </View>
            ) : null}

            {/* Cycling Card */}
            {prBikeLongest ? (
              <View style={styles.prCard}>
                <View style={[styles.badgeContainer, { backgroundColor: 'rgba(0, 229, 255, 0.1)' }]}>
                  <Ionicons name="bicycle" size={20} color="#00E5FF" />
                </View>
                <Text style={styles.prSportTitle}>Cycling</Text>
                <Text style={styles.prStatLabel}>Longest: <Text style={styles.prStatValue}>{prBikeLongest}</Text></Text>
              </View>
            ) : null}

            {/* Swimming Card */}
            {prSwim100m ? (
              <View style={styles.prCard}>
                <View style={[styles.badgeContainer, { backgroundColor: 'rgba(108, 99, 255, 0.1)' }]}>
                  <Ionicons name="water" size={20} color="#6C63FF" />
                </View>
                <Text style={styles.prSportTitle}>Swimming</Text>
                <Text style={styles.prStatLabel}>100m: <Text style={styles.prStatValue}>{prSwim100m}</Text></Text>
              </View>
            ) : null}

            {/* Hiking Card */}
            {prHikePeak ? (
              <View style={styles.prCard}>
                <View style={[styles.badgeContainer, { backgroundColor: 'rgba(245, 158, 11, 0.1)' }]}>
                  <Ionicons name="trail-sign" size={20} color="#F59E0B" />
                </View>
                <Text style={styles.prSportTitle}>Hiking</Text>
                <Text style={styles.prStatLabel}>Peak Elev: <Text style={styles.prStatValue}>{prHikePeak}</Text></Text>
              </View>
            ) : null}

            {/* Custom PR Cards */}
            {customPRList.map((pr, idx) => (
              <View key={idx} style={styles.prCard}>
                <View style={[styles.badgeContainer, { backgroundColor: 'rgba(249, 115, 22, 0.1)' }]}>
                  <Ionicons name="trophy" size={20} color="#F97316" />
                </View>
                <Text style={styles.prSportTitle}>{pr.name}</Text>
                <Text style={styles.prStatLabel}>PR: <Text style={styles.prStatValue}>{pr.value}</Text></Text>
              </View>
            ))}
          </View>
        ) : (
          <View style={styles.emptyPrCard}>
            <Ionicons name="trophy-outline" size={28} color="#00E5FF" style={{ marginBottom: 6 }} />
            <Text style={{ color: '#F8FAFC', fontWeight: 'bold', fontSize: 14 }}>No Personal Records Set Yet</Text>
            <Text style={{ color: '#94A3B8', fontSize: 12, textAlign: 'center', marginVertical: 6 }}>
              Add your lifting PRs (Bench, Squat), running times, or custom sport achievements.
            </Text>
            <TouchableOpacity style={styles.emptyPrBtn} onPress={() => setShowPRModal(true)}>
              <Text style={styles.emptyPrBtnText}>➕ Add Custom PRs</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Goals Section */}
        <Text style={styles.sectionTitleGoals}>🎯 Targets & Custom Goals</Text>
        <View style={styles.goalsCard}>
          <View style={styles.goalRow}>
            <Ionicons name="analytics" size={16} color="#00E5FF" />
            <Text style={styles.goalLabel}>Weekly Running Volume:</Text>
            <Text style={styles.goalValue}>{weeklyVolumeInput || '--'} km</Text>
          </View>
          <View style={styles.goalRow}>
            <Ionicons name="barbell" size={16} color="#6C63FF" />
            <Text style={styles.goalLabel}>Target Bodyweight:</Text>
            <Text style={styles.goalValue}>{targetWeightInput || '--'} kg</Text>
          </View>
          <View style={styles.goalRow}>
            <Ionicons name="hardware-chip" size={16} color="#F59E0B" />
            <Text style={styles.goalLabel}>Trainer Model Model:</Text>
            <Text style={styles.goalValue}>{aiModel}</Text>
          </View>
        </View>

        {/* Logout Button */}
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Ionicons name="log-out-outline" size={18} color="#EF4444" />
          <Text style={styles.logoutText}>Log Out Account</Text>
        </TouchableOpacity>

      </ScrollView>

      {/* Edit Profile Modal */}
      <Modal
        visible={showEditModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowEditModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeaderRow}>
              <Text style={styles.modalTitle}>Edit Stats & Goals</Text>
              <TouchableOpacity onPress={() => setShowEditModal(false)}>
                <Ionicons name="close" size={22} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 350 }}>
              <Text style={styles.modalLabel}>Age (years)</Text>
              <TextInput
                style={styles.modalInput}
                keyboardType="numeric"
                value={ageInput}
                onChangeText={setAgeInput}
              />

              <Text style={styles.modalLabel}>Weight (kg)</Text>
              <TextInput
                style={styles.modalInput}
                keyboardType="numeric"
                value={weightInput}
                onChangeText={setWeightInput}
              />

              <Text style={styles.modalLabel}>Height (cm)</Text>
              <TextInput
                style={styles.modalInput}
                keyboardType="numeric"
                value={heightInput}
                onChangeText={setHeightInput}
              />

              <Text style={styles.modalLabel}>Target Weight Goal (kg)</Text>
              <TextInput
                style={styles.modalInput}
                keyboardType="numeric"
                value={targetWeightInput}
                onChangeText={setTargetWeightInput}
              />

              <Text style={styles.modalLabel}>Weekly Volume Goal (km)</Text>
              <TextInput
                style={styles.modalInput}
                keyboardType="numeric"
                value={weeklyVolumeInput}
                onChangeText={setWeeklyVolumeInput}
              />

              <Text style={styles.modalLabel}>AI Model Provider</Text>
              <View style={styles.selectorRow}>
                {['gemini', 'gemini-3.5-flash', 'gemini-3.1-flash-lite'].map((prov) => (
                  <TouchableOpacity
                    key={prov}
                    style={[styles.selectorChip, aiModel === prov && styles.selectorChipActive]}
                    onPress={() => setAiModel(prov)}
                  >
                    <Text style={[styles.selectorChipText, aiModel === prov && styles.selectorChipTextActive]}>
                      {prov}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnCancel]}
                onPress={() => setShowEditModal(false)}
              >
                <Text style={styles.modalBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnSave]}
                onPress={handleSaveProfile}
                disabled={saving}
              >
                <Text style={styles.modalBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Edit PRs Modal */}
      <Modal
        visible={showPRModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowPRModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeaderRow}>
              <Text style={styles.modalTitle}>Update Personal Records</Text>
              <TouchableOpacity onPress={() => setShowPRModal(false)}>
                <Ionicons name="close" size={22} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 350 }}>
              <Text style={styles.modalLabel}>Running: 5k Best Time</Text>
              <TextInput
                style={styles.modalInput}
                value={pr5k}
                onChangeText={setPr5k}
                placeholder="e.g. 21:30"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.modalLabel}>Running: 10k Best Time</Text>
              <TextInput
                style={styles.modalInput}
                value={pr10k}
                onChangeText={setPr10k}
                placeholder="e.g. 45:15"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.modalLabel}>Running: Half Marathon Best Time</Text>
              <TextInput
                style={styles.modalInput}
                value={prHalf}
                onChangeText={setPrHalf}
                placeholder="e.g. 1:40:12"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.modalLabel}>Cycling: Longest Ride Distance</Text>
              <TextInput
                style={styles.modalInput}
                value={prBikeLongest}
                onChangeText={setPrBikeLongest}
                placeholder="e.g. 80 km"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.modalLabel}>Swimming: 100m Best Pace</Text>
              <TextInput
                style={styles.modalInput}
                value={prSwim100m}
                onChangeText={setPrSwim100m}
                placeholder="e.g. 1:35"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.modalLabel}>Hiking: Max Peak Elevation Reach</Text>
              <TextInput
                style={styles.modalInput}
                value={prHikePeak}
                onChangeText={setPrHikePeak}
                placeholder="e.g. 3,100m"
                placeholderTextColor="#64748B"
              />

              <Text style={[styles.modalLabel, { color: '#00E5FF', marginTop: 16 }]}>➕ Custom PRs (Lifting, Sports & Exercises)</Text>
              {customPRList.map((pr, idx) => (
                <View key={idx} style={styles.customPRRow}>
                  <Text style={styles.customPRText}>{pr.name}: {pr.value}</Text>
                  <TouchableOpacity onPress={() => handleRemoveCustomPR(idx)}>
                    <Ionicons name="trash-outline" size={16} color="#EF4444" />
                  </TouchableOpacity>
                </View>
              ))}

              <View style={styles.addCustomPRContainer}>
                <TextInput
                  style={[styles.modalInput, { flex: 1, marginRight: 6 }]}
                  placeholder="e.g. Bench Press"
                  placeholderTextColor="#64748B"
                  value={customPRName}
                  onChangeText={setCustomPRName}
                />
                <TextInput
                  style={[styles.modalInput, { flex: 1, marginRight: 6 }]}
                  placeholder="e.g. 225 lbs"
                  placeholderTextColor="#64748B"
                  value={customPRValue}
                  onChangeText={setCustomPRValue}
                />
                <TouchableOpacity style={styles.addPRBtn} onPress={handleAddCustomPR}>
                  <Text style={styles.addPRBtnText}>Add</Text>
                </TouchableOpacity>
              </View>
            </ScrollView>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnCancel]}
                onPress={() => setShowPRModal(false)}
              >
                <Text style={styles.modalBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnSave]}
                onPress={handleSavePRs}
                disabled={saving}
              >
                <Text style={styles.modalBtnText}>Save PRs</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  profileSummaryCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#334155',
    overflow: 'hidden',
    marginBottom: 20,
  },
  profileSummaryGradient: {
    padding: 20,
  },
  profileHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatarCircle: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: 'rgba(0, 229, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.3)',
  },
  profileMeta: {
    flex: 1,
    marginLeft: 16,
  },
  profileTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  profileSubtitle: {
    fontSize: 13,
    color: '#94A3B8',
    marginTop: 4,
  },
  editIconBtn: {
    padding: 8,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  editPrBtn: {
    backgroundColor: 'rgba(0, 229, 255, 0.1)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.3)',
  },
  editPrText: {
    color: '#00E5FF',
    fontSize: 11,
    fontWeight: 'bold',
  },
  prGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: 24,
  },
  prCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    width: '48%',
    padding: 14,
    marginBottom: 14,
  },
  badgeContainer: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  prSportTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 6,
  },
  prStatLabel: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 3,
  },
  prStatValue: {
    fontWeight: 'bold',
    color: '#00E5FF',
  },
  sectionTitleGoals: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 12,
  },
  goalsCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 16,
    marginBottom: 24,
  },
  goalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  goalLabel: {
    flex: 1,
    color: '#94A3B8',
    fontSize: 13,
    marginLeft: 10,
  },
  goalValue: {
    color: '#F8FAFC',
    fontWeight: 'bold',
    fontSize: 13,
  },
  logoutBtn: {
    flexDirection: 'row',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.3)',
    borderRadius: 12,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  logoutText: {
    color: '#EF4444',
    fontWeight: 'bold',
    fontSize: 14,
    marginLeft: 8,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  modalLabel: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#94A3B8',
    marginTop: 10,
    marginBottom: 4,
  },
  modalInput: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    height: 40,
    paddingHorizontal: 12,
    color: '#F8FAFC',
    fontSize: 14,
    marginBottom: 6,
  },
  selectorRow: {
    flexDirection: 'row',
    marginTop: 6,
    marginBottom: 12,
  },
  selectorChip: {
    backgroundColor: '#0F172A',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  selectorChipActive: {
    backgroundColor: '#00E5FF',
    borderColor: '#00E5FF',
  },
  selectorChipText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  selectorChipTextActive: {
    color: '#020617',
    fontWeight: 'bold',
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: 20,
  },
  modalBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    marginLeft: 10,
  },
  btnCancel: {
    backgroundColor: '#475569',
  },
  btnSave: {
    backgroundColor: '#6C63FF',
  },
  modalBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  emptyPrCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 20,
    alignItems: 'center',
    marginBottom: 24,
  },
  emptyPrBtn: {
    backgroundColor: '#00E5FF',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    marginTop: 8,
  },
  emptyPrBtnText: {
    color: '#020617',
    fontSize: 13,
    fontWeight: 'bold',
  },
  customPRRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#0F172A',
    padding: 10,
    borderRadius: 8,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  customPRText: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '600',
  },
  addCustomPRContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  addPRBtn: {
    backgroundColor: '#6C63FF',
    paddingHorizontal: 14,
    height: 40,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 6,
  },
  addPRBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 13,
  },
});
