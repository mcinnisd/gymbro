import React, { useState, useContext } from 'react';
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AuthContext } from '../context/AuthContext';
import Colors from '../constants/Colors';

interface GarminModalProps {
  visible: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const GarminModal: React.FC<GarminModalProps> = ({ visible, onClose, onSuccess }) => {
  const { authToken, apiUrl } = useContext(AuthContext);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [syncMode, setSyncMode] = useState<'all_time' | 'deep_365' | 'incremental'>('all_time');

  const handleConnect = async () => {
    if (!email.trim() || !password.trim()) {
      setErrorMsg('Please enter both Garmin email and password.');
      return;
    }

    setLoading(true);
    setErrorMsg('');

    try {
      const response = await fetch(`${apiUrl}/garmin/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          email: email.trim(),
          password: password.trim(),
          mode: syncMode,
          deep_backfill: syncMode !== 'incremental',
          days_back: syncMode === 'all_time' ? 3650 : (syncMode === 'deep_365' ? 365 : 30)
        }),
      });

      const data = await response.json();

      if (response.ok) {
        Alert.alert(
          'Garmin Connected!',
          syncMode === 'all_time'
            ? 'Credentials saved! All-Time Lifetime Archive backfill (multi-year sleep architecture, HRV, and workouts) initiated in background.'
            : syncMode === 'deep_365'
            ? 'Credentials saved! 365-day historical deep backfill initiated in background.'
            : 'Credentials saved! Background sync initiated.'
        );
        if (onSuccess) onSuccess();
        onClose();
      } else {
        setErrorMsg(data.error || 'Failed to connect Garmin account.');
      }
    } catch (err: any) {
      setErrorMsg('Network error connecting to Garmin API server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.modalContent}>
          <View style={styles.header}>
            <View style={styles.iconCircle}>
              <Ionicons name="watch-outline" size={24} color={Colors.light.primary} />
            </View>
            <Text style={styles.title}>Connect Garmin Watch</Text>
            <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
              <Ionicons name="close" size={20} color={Colors.light.subtext} />
            </TouchableOpacity>
          </View>

          <Text style={styles.subtitle}>
            Enter your Garmin credentials to auto-sync sleep stages (Deep/REM/Light), HRV, Resting HR, and multi-year activity archive.
          </Text>

          {errorMsg ? (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle-outline" size={16} color={Colors.light.danger} />
              <Text style={styles.errorText}>{errorMsg}</Text>
            </View>
          ) : null}

          <Text style={styles.label}>Garmin Email</Text>
          <TextInput
            style={styles.input}
            placeholder="email@example.com"
            placeholderTextColor={Colors.light.subtext}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
          />

          <Text style={styles.label}>Garmin Password</Text>
          <TextInput
            style={styles.input}
            placeholder="••••••••••••"
            placeholderTextColor={Colors.light.subtext}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />

          <Text style={styles.label}>Historical Sync Depth</Text>

          {/* All-Time Lifetime Archive */}
          <TouchableOpacity
            style={[styles.backfillRow, syncMode === 'all_time' && styles.backfillRowActive]}
            onPress={() => setSyncMode('all_time')}
            activeOpacity={0.8}
          >
            <Ionicons
              name={syncMode === 'all_time' ? 'radio-button-on' : 'radio-button-off'}
              size={20}
              color={syncMode === 'all_time' ? Colors.light.primary : Colors.light.subtext}
            />
            <View style={{ marginLeft: 10, flex: 1 }}>
              <Text style={styles.backfillTitle}>All-Time Lifetime Archive (Recommended)</Text>
              <Text style={styles.backfillDesc}>
                Discovers account inception date and backfills complete multi-year archive with monthly chunks.
              </Text>
            </View>
          </TouchableOpacity>

          {/* 1-Year Deep Backfill */}
          <TouchableOpacity
            style={[styles.backfillRow, syncMode === 'deep_365' && styles.backfillRowActive]}
            onPress={() => setSyncMode('deep_365')}
            activeOpacity={0.8}
          >
            <Ionicons
              name={syncMode === 'deep_365' ? 'radio-button-on' : 'radio-button-off'}
              size={20}
              color={syncMode === 'deep_365' ? Colors.light.primary : Colors.light.subtext}
            />
            <View style={{ marginLeft: 10, flex: 1 }}>
              <Text style={styles.backfillTitle}>1-Year Deep Backfill (365 Days)</Text>
              <Text style={styles.backfillDesc}>
                Backfills past 365 days of sleep architecture, daily HRV, and workouts.
              </Text>
            </View>
          </TouchableOpacity>

          {/* 30-Day Snapshot */}
          <TouchableOpacity
            style={[styles.backfillRow, syncMode === 'incremental' && styles.backfillRowActive]}
            onPress={() => setSyncMode('incremental')}
            activeOpacity={0.8}
          >
            <Ionicons
              name={syncMode === 'incremental' ? 'radio-button-on' : 'radio-button-off'}
              size={20}
              color={syncMode === 'incremental' ? Colors.light.primary : Colors.light.subtext}
            />
            <View style={{ marginLeft: 10, flex: 1 }}>
              <Text style={styles.backfillTitle}>Recent Snapshot (30 Days)</Text>
              <Text style={styles.backfillDesc}>
                Quick initial sync of the last 30 days.
              </Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity style={styles.connectBtn} onPress={handleConnect} disabled={loading}>
            {loading ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Text style={styles.connectBtnText}>
                {syncMode === 'all_time'
                  ? 'Connect & Start Lifetime Archive'
                  : syncMode === 'deep_365'
                  ? 'Connect & Start 1-Year Backfill'
                  : 'Connect & Initiate Sync'}
              </Text>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: Colors.light.card,
    borderRadius: 20,
    padding: 24,
    borderWidth: 1,
    borderColor: Colors.light.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#EFF6FF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    color: Colors.light.text,
    flex: 1,
  },
  closeBtn: {
    padding: 4,
  },
  subtitle: {
    fontSize: 13,
    color: Colors.light.subtext,
    lineHeight: 18,
    marginBottom: 20,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FCA5A5',
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
  },
  errorText: {
    fontSize: 12,
    color: Colors.light.danger,
    marginLeft: 6,
    flex: 1,
  },
  label: {
    fontSize: 12,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginBottom: 6,
  },
  input: {
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 10,
    height: 44,
    paddingHorizontal: 14,
    fontSize: 14,
    color: Colors.light.text,
    marginBottom: 16,
  },
  connectBtn: {
    height: 48,
    backgroundColor: Colors.light.primary,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  connectBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 15,
  },
  backfillRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
  },
  backfillRowActive: {
    borderColor: Colors.light.primary,
    backgroundColor: 'rgba(217, 119, 6, 0.05)',
  },
  backfillTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  backfillDesc: {
    fontSize: 11,
    color: Colors.light.subtext,
    marginTop: 2,
    lineHeight: 14,
  },
});

