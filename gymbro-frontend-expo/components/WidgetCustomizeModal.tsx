import React, { useState, useEffect } from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Switch,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Colors from '../constants/Colors';

const memoryStore: Record<string, string> = {};

export const AsyncStorage = {
  getItem: async (key: string): Promise<string | null> => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        return window.localStorage.getItem(key);
      }
    } catch (e) {
      // Fallback to memoryStore
    }
    return memoryStore[key] || null;
  },
  setItem: async (key: string, value: string): Promise<void> => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, value);
        return;
      }
    } catch (e) {
      // Fallback to memoryStore
    }
    memoryStore[key] = value;
  },
  removeItem: async (key: string): Promise<void> => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.removeItem(key);
        return;
      }
    } catch (e) {
      // Fallback to memoryStore
    }
    delete memoryStore[key];
  },
};

export interface WidgetPreferences {
  hrv: boolean;
  sleep_stages: boolean;
  body_battery: boolean;
  training_status: boolean;
  spo2: boolean;
  vo2_max: boolean;
}

export const DEFAULT_WIDGET_PREFS: WidgetPreferences = {
  hrv: true,
  sleep_stages: true,
  body_battery: true,
  training_status: true,
  spo2: true,
  vo2_max: true,
};

export const WIDGET_PREFS_KEY = '@gymbro_widget_prefs';

export async function getWidgetPreferences(): Promise<WidgetPreferences> {
  try {
    const json = await AsyncStorage.getItem(WIDGET_PREFS_KEY);
    if (json) {
      const parsed = JSON.parse(json);
      return { ...DEFAULT_WIDGET_PREFS, ...parsed };
    }
  } catch (err) {
    console.error('Failed to load widget preferences:', err);
  }
  return DEFAULT_WIDGET_PREFS;
}

export async function saveWidgetPreferences(prefs: WidgetPreferences): Promise<void> {
  try {
    await AsyncStorage.setItem(WIDGET_PREFS_KEY, JSON.stringify(prefs));
  } catch (err) {
    console.error('Failed to save widget preferences:', err);
  }
}

export interface WidgetCustomizeModalProps {
  visible: boolean;
  onClose: () => void;
  onPreferencesChange?: (prefs: WidgetPreferences) => void;
}

interface WidgetItemConfig {
  key: keyof WidgetPreferences;
  title: string;
  description: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconColor: string;
}

const WIDGET_ITEMS: WidgetItemConfig[] = [
  {
    key: 'hrv',
    title: 'Heart Rate Variability (HRV)',
    description: 'rMSSD baseline and autonomic nervous system recovery status',
    icon: 'pulse-outline',
    iconColor: '#059669',
  },
  {
    key: 'sleep_stages',
    title: 'Sleep Stages Architecture',
    description: 'Deep, REM, Light, and Awake sleep breakdown stats',
    icon: 'moon-outline',
    iconColor: Colors.light.sleepDusk,
  },
  {
    key: 'body_battery',
    title: 'Body Battery Energy Meter',
    description: 'Real-time energy drain and recharge monitoring (0-100)',
    icon: 'battery-charging-outline',
    iconColor: '#D97706',
  },
  {
    key: 'training_status',
    title: 'Garmin Training Status & Load',
    description: 'Acute load, training status (Productive, Recovery, etc.)',
    icon: 'fitness-outline',
    iconColor: '#DC2626',
  },
  {
    key: 'spo2',
    title: 'SpO2 Pulse Oximetry',
    description: 'Blood oxygen saturation percentage and nocturnal trends',
    icon: 'water-outline',
    iconColor: '#0891B2',
  },
  {
    key: 'vo2_max',
    title: 'VO2 Max & Fitness Age',
    description: 'Cardiovascular capacity score and estimated fitness age',
    icon: 'speedometer-outline',
    iconColor: '#7C3AED',
  },
];

export const WidgetCustomizeModal: React.FC<WidgetCustomizeModalProps> = ({
  visible,
  onClose,
  onPreferencesChange,
}) => {
  const [prefs, setPrefs] = useState<WidgetPreferences>(DEFAULT_WIDGET_PREFS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (visible) {
      loadPrefs();
    }
  }, [visible]);

  const loadPrefs = async () => {
    const loaded = await getWidgetPreferences();
    setPrefs(loaded);
  };

  const handleToggle = (key: keyof WidgetPreferences) => {
    setPrefs((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleReset = () => {
    setPrefs(DEFAULT_WIDGET_PREFS);
  };

  const handleSave = async () => {
    setSaving(true);
    await saveWidgetPreferences(prefs);
    if (onPreferencesChange) {
      onPreferencesChange(prefs);
    }
    setSaving(false);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.modalCard}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerTitleRow}>
              <Ionicons name="options-outline" size={22} color={Colors.light.primary} style={{ marginRight: 8 }} />
              <Text style={styles.title}>Customize Widgets</Text>
            </View>
            <TouchableOpacity style={styles.closeBtn} onPress={onClose} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Ionicons name="close" size={20} color={Colors.light.mutedText} />
            </TouchableOpacity>
          </View>
          <Text style={styles.subtitle}>
            Select which Garmin telemetry widgets display on your Recovery and Stats dashboards.
          </Text>

          {/* Widgets List */}
          <ScrollView style={styles.listContainer} showsVerticalScrollIndicator={false}>
            {WIDGET_ITEMS.map((item) => {
              const isEnabled = prefs[item.key];
              return (
                <View key={item.key} style={styles.itemRow}>
                  <View style={[styles.iconContainer, { backgroundColor: `${item.iconColor}15` }]}>
                    <Ionicons name={item.icon} size={20} color={item.iconColor} />
                  </View>
                  <View style={styles.itemTextContainer}>
                    <Text style={styles.itemTitle}>{item.title}</Text>
                    <Text style={styles.itemDescription}>{item.description}</Text>
                  </View>
                  <Switch
                    value={isEnabled}
                    onValueChange={() => handleToggle(item.key)}
                    trackColor={{ false: '#E2E8F0', true: Colors.light.primary }}
                    thumbColor="#FFFFFF"
                  />
                </View>
              );
            })}
          </ScrollView>

          {/* Footer Actions */}
          <View style={styles.footer}>
            <TouchableOpacity style={styles.resetBtn} onPress={handleReset}>
              <Text style={styles.resetBtnText}>Reset All</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.saveBtn} onPress={handleSave} disabled={saving}>
              {saving ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.saveBtnText}>Save Preferences</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

export default WidgetCustomizeModal;

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.5)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    maxHeight: '85%',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 8,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.light.text,
  },
  closeBtn: {
    padding: 4,
    borderRadius: 16,
    backgroundColor: '#F1F5F9',
  },
  subtitle: {
    fontSize: 13,
    color: Colors.light.mutedText,
    marginTop: 4,
    marginBottom: 16,
  },
  listContainer: {
    marginVertical: 4,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 12,
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  iconContainer: {
    width: 38,
    height: 38,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  itemTextContainer: {
    flex: 1,
    marginRight: 8,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.light.text,
    marginBottom: 2,
  },
  itemDescription: {
    fontSize: 11,
    color: Colors.light.mutedText,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
  },
  resetBtn: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
    backgroundColor: '#F1F5F9',
  },
  resetBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.light.mutedText,
  },
  saveBtn: {
    flex: 1,
    marginLeft: 12,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: Colors.light.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});
