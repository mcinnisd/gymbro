import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

interface DaySelectorWidgetProps {
  onSelectDays: (formattedText: string) => void;
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export const DaySelectorWidget: React.FC<DaySelectorWidgetProps> = ({ onSelectDays }) => {
  const [selectedDays, setSelectedDays] = useState<string[]>(['Mon', 'Wed', 'Fri']);

  const toggleDay = (day: string) => {
    if (selectedDays.includes(day)) {
      setSelectedDays(selectedDays.filter((d) => d !== day));
    } else {
      setSelectedDays([...selectedDays, day]);
    }
  };

  const handleConfirm = () => {
    if (selectedDays.length === 0) return;
    const formatted = `I want to train on ${selectedDays.join(', ')}.`;
    onSelectDays(formatted);
  };

  return (
    <View style={styles.card}>
      <Text style={styles.title}>📅 Select Preferred Training Days</Text>
      <Text style={styles.subtitle}>Tap days to toggle your weekly workout schedule:</Text>
      
      <View style={styles.daysRow}>
        {DAYS.map((day) => {
          const isSelected = selectedDays.includes(day);
          return (
            <TouchableOpacity
              key={day}
              style={[styles.dayPill, isSelected && styles.dayPillSelected]}
              onPress={() => toggleDay(day)}
            >
              <Text style={[styles.dayText, isSelected && styles.dayTextSelected]}>
                {day}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <TouchableOpacity style={styles.confirmBtn} onPress={handleConfirm}>
        <LinearGradient colors={['#00E5FF', '#0099FF']} style={styles.confirmGradient}>
          <Text style={styles.confirmText}>
            Confirm ({selectedDays.length} days/week)
          </Text>
        </LinearGradient>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 14,
    marginVertical: 8,
    width: '100%',
  },
  title: {
    color: '#00E5FF',
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  subtitle: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 10,
  },
  daysRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  dayPill: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 10,
    alignItems: 'center',
    flex: 1,
    marginHorizontal: 2,
  },
  dayPillSelected: {
    backgroundColor: 'rgba(0, 229, 255, 0.15)',
    borderColor: '#00E5FF',
  },
  dayText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
  },
  dayTextSelected: {
    color: '#00E5FF',
    fontWeight: 'bold',
  },
  confirmBtn: {
    borderRadius: 8,
    overflow: 'hidden',
  },
  confirmGradient: {
    paddingVertical: 8,
    alignItems: 'center',
  },
  confirmText: {
    color: '#020617',
    fontWeight: 'bold',
    fontSize: 13,
  },
});
