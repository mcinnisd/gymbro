import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface BarData {
  day: string;
  volumeKm: number;
  type: 'easy' | 'tempo' | 'long' | 'rest';
}

const WEEKLY_DATA: BarData[] = [
  { day: 'Mon', volumeKm: 5, type: 'easy' },
  { day: 'Tue', volumeKm: 0, type: 'rest' },
  { day: 'Wed', volumeKm: 7, type: 'tempo' },
  { day: 'Thu', volumeKm: 4, type: 'easy' },
  { day: 'Fri', volumeKm: 0, type: 'rest' },
  { day: 'Sat', volumeKm: 12, type: 'long' },
  { day: 'Sun', volumeKm: 0, type: 'rest' },
];

export const TrainingVolumeChart: React.FC = () => {
  const maxVol = Math.max(...WEEKLY_DATA.map((d) => d.volumeKm), 1);

  return (
    <View style={styles.card}>
      <Text style={styles.title}>📊 Weekly Volume & Intensity Forecast</Text>
      <Text style={styles.subtitle}>Projected weekly training breakdown:</Text>

      <View style={styles.chartContainer}>
        {WEEKLY_DATA.map((item, idx) => {
          const heightPct = (item.volumeKm / maxVol) * 100;
          const barColor =
            item.type === 'long'
              ? '#6C63FF'
              : item.type === 'tempo'
              ? '#F59E0B'
              : item.type === 'easy'
              ? '#10B981'
              : '#334155';

          return (
            <View key={idx} style={styles.col}>
              <Text style={styles.valText}>{item.volumeKm > 0 ? `${item.volumeKm}k` : ''}</Text>
              <View style={styles.barTrack}>
                <View
                  style={[
                    styles.barFill,
                    {
                      height: `${Math.max(heightPct, 8)}%`,
                      backgroundColor: barColor,
                    },
                  ]}
                />
              </View>
              <Text style={styles.dayLabel}>{item.day}</Text>
            </View>
          );
        })}
      </View>
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
    marginVertical: 10,
    width: '100%',
  },
  title: {
    color: '#00E5FF',
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  subtitle: {
    color: '#94A3B8',
    fontSize: 11,
    marginBottom: 12,
  },
  chartContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: 90,
    paddingTop: 10,
  },
  col: {
    alignItems: 'center',
    flex: 1,
    height: '100%',
    justifyContent: 'flex-end',
  },
  barTrack: {
    width: 14,
    height: 55,
    backgroundColor: '#1E293B',
    borderRadius: 6,
    justifyContent: 'flex-end',
    overflow: 'hidden',
    marginVertical: 4,
  },
  barFill: {
    width: '100%',
    borderRadius: 6,
  },
  valText: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '600',
  },
  dayLabel: {
    color: '#CBD5E1',
    fontSize: 11,
    fontWeight: 'bold',
  },
});
