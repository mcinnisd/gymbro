import React, { useState, useEffect, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
  TextInput,
  Alert,
} from 'react-native';
import { AuthContext } from '../../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import Colors from '../../constants/Colors';

interface TrainingEvent {
  id: number;
  date: string;
  title: string;
  description: string;
  event_type: 'run' | 'strength' | 'rest' | 'race' | 'other';
  status: 'planned' | 'completed' | 'skipped';
}

export default function TrainingScreen() {
  const { authToken, apiUrl } = useContext(AuthContext);
  const [events, setEvents] = useState<TrainingEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [weekDates, setWeekDates] = useState<string[]>([]);
  
  // Reschedule Modal State
  const [rescheduleEvent, setRescheduleEvent] = useState<TrainingEvent | null>(null);
  const [newDateInput, setNewDateInput] = useState('');
  
  // Manual Log Modal State
  const [showLogModal, setShowLogModal] = useState(false);
  const [logTitle, setLogTitle] = useState('');
  const [logDesc, setLogDesc] = useState('');
  const [logType, setLogType] = useState<'run' | 'strength' | 'rest' | 'race' | 'other'>('run');

  useEffect(() => {
    // Generate dates for current week (Mon-Sun)
    const current = new Date();
    const week = [];
    // Get Monday
    const distanceToMonday = current.getDay() === 0 ? -6 : 1 - current.getDay();
    const monday = new Date(current.setDate(current.getDate() + distanceToMonday));
    
    for (let i = 0; i < 7; i++) {
      const day = new Date(monday);
      day.setDate(monday.getDate() + i);
      week.push(day.toISOString().split('T')[0]);
    }
    setWeekDates(week);
  }, []);

  useEffect(() => {
    if (authToken) {
      fetchEvents();
    }
  }, [authToken]);

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/calendar/events`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        setEvents(data.events || []);
      }
    } catch (err) {
      console.error('Error fetching calendar events:', err);
    }
    setLoading(false);
  };

  const handleUpdateStatus = async (eventId: number, status: 'planned' | 'completed' | 'skipped') => {
    try {
      const response = await fetch(`${apiUrl}/calendar/events/${eventId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ status }),
      });
      if (response.ok) {
        setEvents((prev) =>
          prev.map((e) => (e.id === eventId ? { ...e, status } : e))
        );
      }
    } catch (err) {
      console.error('Error updating event status:', err);
    }
  };

  const handleReschedule = async () => {
    if (!rescheduleEvent || !newDateInput) return;
    
    // Check YYYY-MM-DD format
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(newDateInput)) {
      Alert.alert('Invalid Date', 'Please use YYYY-MM-DD format.');
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/calendar/events/${rescheduleEvent.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ date: newDateInput }),
      });
      if (response.ok) {
        Alert.alert('Rescheduled', 'Workout successfully moved!');
        setRescheduleEvent(null);
        setNewDateInput('');
        fetchEvents();
      } else {
        const err = await response.json();
        Alert.alert('Failed', err.error || 'Reschedule failed');
      }
    } catch (err) {
      console.error('Error rescheduling event:', err);
      Alert.alert('Error', 'Network error rescheduling workout.');
    }
  };

  const handleAddManualWorkout = async () => {
    if (!logTitle.trim()) {
      Alert.alert('Missing Info', 'Please provide a workout title.');
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/calendar/events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          date: selectedDate,
          title: logTitle,
          description: logDesc,
          event_type: logType,
          status: 'completed', // completed by default since they are manually logging it
        }),
      });

      if (response.ok) {
        setShowLogModal(false);
        setLogTitle('');
        setLogDesc('');
        fetchEvents();
        Alert.alert('Logged', 'Workout logged successfully!');
      } else {
        const err = await response.json();
        Alert.alert('Failed', err.error || 'Failed to log workout.');
      }
    } catch (err) {
      console.error('Error logging workout:', err);
      Alert.alert('Error', 'Network error saving workout.');
    }
  };

  const handleDeleteWorkout = async (eventId: number) => {
    Alert.alert('Delete Workout', 'Are you sure you want to delete this workout?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            const response = await fetch(`${apiUrl}/calendar/events/${eventId}`, {
              method: 'DELETE',
              headers: { Authorization: `Bearer ${authToken}` },
            });
            if (response.ok) {
              setEvents((prev) => prev.filter((e) => e.id !== eventId));
            }
          } catch (err) {
            console.error('Error deleting event:', err);
          }
        },
      },
    ]);
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'run':
        return 'walk';
      case 'strength':
        return 'barbell';
      case 'race':
        return 'trophy';
      case 'rest':
        return 'bed';
      default:
        return 'fitness';
    }
  };

  const getEventColor = (type: string) => {
    switch (type) {
      case 'run':
        return '#10B981'; // Emerald
      case 'strength':
        return '#6C63FF'; // Purple
      case 'race':
        return '#F59E0B'; // Amber
      case 'rest':
        return '#64748B'; // Cool grey
      default:
        return '#00E5FF'; // Cyan
    }
  };

  const renderSourceBadge = (source?: string) => {
    const src = (source || 'manual').toLowerCase();
    if (src === 'garmin') {
      return (
        <View style={[styles.sourceBadge, { backgroundColor: 'rgba(0, 229, 255, 0.15)', borderColor: 'rgba(0, 229, 255, 0.3)' }]}>
          <Text style={[styles.sourceBadgeText, { color: '#00E5FF' }]}>⌚ Garmin (Primary)</Text>
        </View>
      );
    } else if (src === 'strava') {
      return (
        <View style={[styles.sourceBadge, { backgroundColor: 'rgba(249, 115, 22, 0.15)', borderColor: 'rgba(249, 115, 22, 0.3)' }]}>
          <Text style={[styles.sourceBadgeText, { color: '#F97316' }]}>🔥 Strava</Text>
        </View>
      );
    } else if (src === 'apple_health') {
      return (
        <View style={[styles.sourceBadge, { backgroundColor: 'rgba(239, 68, 68, 0.15)', borderColor: 'rgba(239, 68, 68, 0.3)' }]}>
          <Text style={[styles.sourceBadgeText, { color: '#EF4444' }]}>🍎 Apple Health</Text>
        </View>
      );
    }
    return (
      <View style={[styles.sourceBadge, { backgroundColor: 'rgba(148, 163, 184, 0.15)', borderColor: 'rgba(148, 163, 184, 0.3)' }]}>
        <Text style={[styles.sourceBadgeText, { color: '#94A3B8' }]}>📝 Manual</Text>
      </View>
    );
  };

  const filteredEvents = events.filter((e) => e.date === selectedDate);

  return (
    <View style={styles.container}>
      {/* Calendar Bar */}
      <View style={styles.calendarStrip}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.stripScroll}>
          {weekDates.map((dateStr) => {
            const dateObj = new Date(dateStr + 'T00:00:00');
            const isSelected = selectedDate === dateStr;
            const isToday = new Date().toISOString().split('T')[0] === dateStr;
            const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
            const dayNum = dateObj.getDate();
            const dateEvents = events.filter((e) => e.date === dateStr);

            return (
              <TouchableOpacity
                key={dateStr}
                style={[
                  styles.calendarDayCard,
                  isSelected && styles.selectedDayCard,
                  isToday && styles.todayDayCard,
                ]}
                onPress={() => setSelectedDate(dateStr)}
              >
                <Text style={[styles.dayNameText, isSelected && styles.selectedDayText]}>{dayName}</Text>
                <Text style={[styles.dayNumText, isSelected && styles.selectedDayText]}>{dayNum}</Text>
                {/* Dots */}
                <View style={styles.dotsContainer}>
                  {dateEvents.slice(0, 3).map((e) => (
                    <View
                      key={e.id}
                      style={[
                        styles.eventDot,
                        {
                          backgroundColor:
                            e.status === 'completed'
                              ? '#10B981'
                              : e.status === 'skipped'
                              ? '#EF4444'
                              : '#6C63FF',
                        },
                      ]}
                    />
                  ))}
                </View>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      <ScrollView contentContainerStyle={styles.mainScroll} showsVerticalScrollIndicator={false}>
        {/* Header Summary */}
        <View style={styles.dayHeader}>
          <Text style={styles.dateLabel}>
            {new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
            })}
          </Text>
          <TouchableOpacity style={styles.addBtn} onPress={() => setShowLogModal(true)}>
            <Ionicons name="add" size={16} color="#00E5FF" />
            <Text style={styles.addBtnText}>Log Workout</Text>
          </TouchableOpacity>
        </View>

        {loading ? (
          <ActivityIndicator size="large" color="#00E5FF" style={{ marginTop: 40 }} />
        ) : filteredEvents.length === 0 ? (
          <View style={styles.emptyWorkouts}>
            <Ionicons name="calendar-outline" size={48} color="#475569" />
            <Text style={styles.emptyWorkoutsText}>No workouts scheduled for this day.</Text>
            <Text style={styles.emptyWorkoutsSub}>Enjoy your rest, or manually log a workout above!</Text>
          </View>
        ) : (
          filteredEvents.map((event) => {
            const eventColor = getEventColor(event.event_type);
            const isCompleted = event.status === 'completed';
            const isSkipped = event.status === 'skipped';

            return (
              <View key={event.id} style={styles.workoutCard}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <View style={[styles.workoutTypeTag, { backgroundColor: eventColor, marginBottom: 0 }]}>
                    <Ionicons name={getEventIcon(event.event_type) as any} size={14} color="#FFFFFF" />
                    <Text style={styles.workoutTypeText}>{event.event_type.toUpperCase()}</Text>
                  </View>
                  {renderSourceBadge((event as any).source || (event.event_type === 'run' ? 'garmin' : 'manual'))}
                </View>

                <View style={styles.workoutInfo}>
                  <Text style={styles.workoutTitle}>{event.title}</Text>
                  {event.description !== '' && (
                    <Text style={styles.workoutDesc}>{event.description}</Text>
                  )}
                </View>

                {/* Status Bar */}
                <View style={styles.actionBar}>
                  <View style={styles.statusGroup}>
                    <Text style={styles.statusLabel}>Status: </Text>
                    <Text
                      style={[
                        styles.statusValue,
                        isCompleted && styles.statusSuccess,
                        isSkipped && styles.statusDanger,
                      ]}
                    >
                      {event.status.toUpperCase()}
                    </Text>
                  </View>

                  <View style={styles.buttonsGroup}>
                    {!isCompleted ? (
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.btnSuccess]}
                        onPress={() => handleUpdateStatus(event.id, 'completed')}
                      >
                        <Ionicons name="checkmark-circle-outline" size={16} color="#FFFFFF" />
                      </TouchableOpacity>
                    ) : (
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.btnUndo]}
                        onPress={() => handleUpdateStatus(event.id, 'planned')}
                      >
                        <Ionicons name="refresh" size={16} color="#94A3B8" />
                      </TouchableOpacity>
                    )}

                    {!isSkipped && !isCompleted && (
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.btnDanger]}
                        onPress={() => handleUpdateStatus(event.id, 'skipped')}
                      >
                        <Ionicons name="close-circle-outline" size={16} color="#FFFFFF" />
                      </TouchableOpacity>
                    )}

                    <TouchableOpacity
                      style={styles.actionBtn}
                      onPress={() => {
                        setRescheduleEvent(event);
                        setNewDateInput(event.date);
                      }}
                    >
                      <Ionicons name="calendar" size={16} color="#00E5FF" />
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={[styles.actionBtn, styles.btnTrash]}
                      onPress={() => handleDeleteWorkout(event.id)}
                    >
                      <Ionicons name="trash-outline" size={16} color="#EF4444" />
                    </TouchableOpacity>
                  </View>
                </View>
              </View>
            );
          })
        )}
      </ScrollView>

      {/* Reschedule Modal */}
      <Modal
        visible={rescheduleEvent !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setRescheduleEvent(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Reschedule Workout</Text>
            <Text style={styles.modalSubtitle}>Enter target date in YYYY-MM-DD format:</Text>
            
            <TextInput
              style={styles.modalInput}
              value={newDateInput}
              onChangeText={setNewDateInput}
              placeholder="YYYY-MM-DD"
              placeholderTextColor="#64748B"
            />
            
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnCancel]}
                onPress={() => setRescheduleEvent(null)}
              >
                <Text style={styles.modalBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnSave]}
                onPress={handleReschedule}
              >
                <Text style={styles.modalBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Manual Workout Logger Modal */}
      <Modal
        visible={showLogModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowLogModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Log Completed Workout</Text>

            <Text style={styles.modalLabel}>Activity Type</Text>
            <View style={styles.typeSelectorRow}>
              {(['run', 'strength', 'race', 'rest', 'other'] as const).map((t) => (
                <TouchableOpacity
                  key={t}
                  style={[
                    styles.typeChip,
                    logType === t && { backgroundColor: getEventColor(t) },
                  ]}
                  onPress={() => setLogType(t)}
                >
                  <Text style={styles.typeChipText}>{t.toUpperCase()}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.modalLabel}>Workout Title</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="e.g. 5k Recovery Jog, Leg Day"
              placeholderTextColor="#64748B"
              value={logTitle}
              onChangeText={setLogTitle}
            />

            <Text style={styles.modalLabel}>Workout Description / Feedback</Text>
            <TextInput
              style={[styles.modalInput, styles.textArea]}
              placeholder="e.g. felt good, average heart rate 142 bpm"
              placeholderTextColor="#64748B"
              multiline
              numberOfLines={3}
              value={logDesc}
              onChangeText={setLogDesc}
            />

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnCancel]}
                onPress={() => setShowLogModal(false)}
              >
                <Text style={styles.modalBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.btnSave]}
                onPress={handleAddManualWorkout}
              >
                <Text style={styles.modalBtnText}>Log Workout</Text>
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
    backgroundColor: Colors.light.background,
  },
  calendarStrip: {
    backgroundColor: Colors.light.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
    paddingVertical: 12,
  },
  stripScroll: {
    paddingHorizontal: 16,
  },
  calendarDayCard: {
    width: 48,
    height: 70,
    backgroundColor: Colors.light.background,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  selectedDayCard: {
    backgroundColor: Colors.light.primary,
    borderColor: Colors.light.primary,
  },
  todayDayCard: {
    borderColor: Colors.light.primary,
    borderWidth: 2,
  },
  dayNameText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: Colors.light.subtext,
  },
  dayNumText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginTop: 4,
  },
  selectedDayText: {
    color: '#FFFFFF',
  },
  dotsContainer: {
    flexDirection: 'row',
    marginTop: 6,
    height: 6,
    alignItems: 'center',
  },
  eventDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    marginHorizontal: 1,
  },
  mainScroll: {
    padding: 16,
    paddingBottom: 80,
  },
  dayHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  dateLabel: {
    fontSize: 16,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(37, 99, 235, 0.1)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(37, 99, 235, 0.2)',
  },
  addBtnText: {
    color: Colors.light.primary,
    fontSize: 12,
    fontWeight: 'bold',
    marginLeft: 4,
  },
  emptyWorkouts: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyWorkoutsText: {
    color: Colors.light.text,
    fontSize: 14,
    fontWeight: 'bold',
    marginTop: 12,
  },
  emptyWorkoutsSub: {
    color: Colors.light.subtext,
    fontSize: 12,
    marginTop: 4,
  },
  workoutCard: {
    backgroundColor: Colors.light.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  workoutTypeTag: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    marginBottom: 10,
  },
  workoutTypeText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: 'bold',
    marginLeft: 4,
  },
  workoutInfo: {
    marginBottom: 12,
  },
  workoutTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  workoutDesc: {
    fontSize: 13,
    color: Colors.light.subtext,
    marginTop: 4,
    lineHeight: 18,
  },
  actionBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
    paddingTop: 12,
  },
  statusGroup: {
    flexDirection: 'row',
  },
  statusLabel: {
    fontSize: 12,
    color: Colors.light.subtext,
  },
  statusValue: {
    fontSize: 12,
    fontWeight: 'bold',
    color: Colors.light.primary,
  },
  statusSuccess: {
    color: Colors.light.secondary,
  },
  statusDanger: {
    color: '#DC2626',
  },
  buttonsGroup: {
    flexDirection: 'row',
  },
  actionBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.light.background,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 6,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  btnSuccess: {
    backgroundColor: Colors.light.secondary,
    borderColor: Colors.light.secondary,
  },
  btnUndo: {
    backgroundColor: Colors.light.card,
    borderColor: Colors.light.border,
  },
  btnDanger: {
    backgroundColor: '#DC2626',
    borderColor: '#DC2626',
  },
  btnTrash: {
    borderColor: '#DC2626',
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
    padding: 24,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginBottom: 8,
  },
  modalSubtitle: {
    fontSize: 13,
    color: Colors.light.subtext,
    marginBottom: 16,
  },
  modalLabel: {
    fontSize: 12,
    fontWeight: 'bold',
    color: Colors.light.subtext,
    marginTop: 12,
    marginBottom: 6,
  },
  modalInput: {
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 8,
    height: 44,
    paddingHorizontal: 12,
    color: Colors.light.text,
    fontSize: 15,
  },
  textArea: {
    height: 80,
    paddingTop: 10,
    textAlignVertical: 'top',
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
    backgroundColor: Colors.light.border,
  },
  btnSave: {
    backgroundColor: Colors.light.primary,
  },
  modalBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  typeSelectorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 8,
  },
  typeChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginRight: 6,
    marginBottom: 6,
  },
  typeChipText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  sourceBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
  },
  sourceBadgeText: {
    fontSize: 10,
    fontWeight: 'bold',
  },
});
