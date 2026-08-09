import React, { useState, useEffect, useRef, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  TextInput,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Alert,
  Linking,
} from 'react-native';
import { AuthContext } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { MarkdownText } from '../components/MarkdownText';
import { DaySelectorWidget } from '../components/DaySelectorWidget';
import { TrainingVolumeChart } from '../components/TrainingVolumeChart';

interface Message {
  sender: 'user' | 'bot' | 'system';
  content: string;
  timestamp: string;
  is_interview_complete?: boolean;
  proposal?: any;
  chart_data?: any;
}

export default function ChatScreen() {
  const { authToken, user, setUser, apiUrl } = useContext(AuthContext);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  
  // Local Coach Status to manage views: 'not_started' | 'interviewing' | 'completed_waiting_plan' | 'active'
  const [coachStatus, setCoachStatus] = useState<string>('not_started');
  
  // Reasoning Mode state: 'fast' (7-day biometrics context) | 'deep_dive' (Hybrid GraphRAG + Tools)
  const [reasoningMode, setReasoningMode] = useState<'fast' | 'deep_dive'>('fast');

  // Onboarding wizard states
  const [onboardingStep, setOnboardingStep] = useState<number>(1);
  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');
  const [garminStatus, setGarminStatus] = useState<string>('disconnected'); // 'disconnected' | 'connecting' | 'syncing' | 'completed' | 'failed'
  const [garminProgress, setGarminProgress] = useState<number>(0);
  const [stravaConnected, setStravaConnected] = useState<boolean>(false);
  const [healthkitConnected, setHealthkitConnected] = useState<boolean>(false);

  const handleSyncHealthKit = async () => {
    const { syncAppleHealthKitData } = await import('../services/healthkit');
    const data = await syncAppleHealthKitData();
    if (data) {
      setHealthkitConnected(true);
      if (data.resting_hr) setRestingHr(String(data.resting_hr));
      if (data.sleep_hours) setSleepHours(String(data.sleep_hours));
      Alert.alert('Apple Health Synced', 'Resting HR, sleep, and activity metrics auto-imported!');
    }
  };
  const [pollingInterval, setPollingInterval] = useState<any>(null);

  // Pre-population profile states
  const [age, setAge] = useState('');
  const [weight, setWeight] = useState('');
  const [height, setHeight] = useState('');
  const [sportHistory, setSportHistory] = useState('Running');
  const [runningExperience, setRunningExperience] = useState('Beginner');
  const [weeklyVolume, setWeeklyVolume] = useState('0');
  const [restingHr, setRestingHr] = useState('');
  const [sleepHours, setSleepHours] = useState('');
  
  // Personal Records
  const [pr5k, setPr5k] = useState('');
  const [pr10k, setPr10k] = useState('');
  const [prHalf, setPrHalf] = useState('');
  const [prBikeLongest, setPrBikeLongest] = useState('');
  const [prSwim100m, setPrSwim100m] = useState('');
  const [prHikePeak, setPrHikePeak] = useState('');

  // Clear polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, [pollingInterval]);

  const checkIntegrationStatus = async () => {
    try {
      const response = await fetch(`${apiUrl}/auth/profile`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        const profile = data.profile || {};
        setStravaConnected(profile.strava_connected || false);
        if (profile.garmin_connected) {
          setGarminStatus('completed');
        }
      }
    } catch (err) {
      console.error('Error fetching integration status:', err);
    }
  };

  useEffect(() => {
    if (authToken && coachStatus === 'not_started') {
      checkIntegrationStatus();
    }
  }, [authToken, coachStatus]);

  useEffect(() => {
    if (onboardingStep === 2) {
      fetchPrepopulatedProfile();
    }
  }, [onboardingStep]);

  const pollGarminStatus = () => {
    if (pollingInterval) clearInterval(pollingInterval);
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${apiUrl}/garmin/status`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (response.ok) {
          const data = await response.json();
          const status = data.garmin_sync_status;
          const progress = data.garmin_sync_progress || 0;
          setGarminProgress(progress);
          
          if (status === 'completed' || status === 'synced') {
            setGarminStatus('completed');
            clearInterval(interval);
          } else if (status === 'failed' || status === 'error') {
            setGarminStatus('failed');
            Alert.alert('Garmin Sync Failed', data.garmin_last_sync_error || 'Could not sync Garmin data. Please verify your credentials.');
            clearInterval(interval);
          } else {
            setGarminStatus('syncing');
          }
        }
      } catch (err) {
        console.error('Error polling Garmin status:', err);
      }
    }, 3000);
    setPollingInterval(interval);
  };

  const handleConnectGarmin = async () => {
    if (!garminEmail || !garminPassword) {
      Alert.alert('Required Fields', 'Please enter your Garmin email and password.');
      return;
    }
    setGarminStatus('connecting');
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
        setGarminStatus('syncing');
        pollGarminStatus();
      } else {
        const err = await response.json();
        setGarminStatus('failed');
        Alert.alert('Connection Error', err.error || 'Failed to connect Garmin account.');
      }
    } catch (err) {
      console.error('Error connecting Garmin:', err);
      setGarminStatus('failed');
      Alert.alert('Error', 'Network error connecting to Garmin.');
    }
  };

  const handleConnectStrava = async () => {
    try {
      const response = await fetch(`${apiUrl}/strava/connect_strava?json=true`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${authToken}`,
          Accept: 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        if (data.url) {
          Linking.openURL(data.url);
          pollStravaStatus();
        } else {
          Alert.alert('Error', 'Strava connection link not found.');
        }
      } else {
        Alert.alert('Error', 'Failed to get Strava authorize URL.');
      }
    } catch (err) {
      console.error('Error connecting Strava:', err);
      Alert.alert('Error', 'Network error connecting to Strava.');
    }
  };

  const pollStravaStatus = () => {
    if (pollingInterval) clearInterval(pollingInterval);
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${apiUrl}/auth/profile`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (response.ok) {
          const data = await response.json();
          const profile = data.profile || {};
          if (profile.strava_connected) {
            setStravaConnected(true);
            clearInterval(interval);
          }
        }
      } catch (err) {
        console.error('Error polling Strava status:', err);
      }
    }, 3000);
    setPollingInterval(interval);
  };

  const fetchPrepopulatedProfile = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/coach/prepopulate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setAge(data.age ? String(data.age) : '');
        setWeight(data.weight ? String(data.weight) : '');
        setHeight(data.height ? String(data.height) : '');
        setSportHistory(data.sport_history || 'Running');
        setRunningExperience(data.running_experience || 'Beginner');
        setWeeklyVolume(data.weekly_volume ? String(data.weekly_volume) : '0');
        setRestingHr(data.resting_hr ? String(data.resting_hr) : '');
        setSleepHours(data.sleep_hours ? String(data.sleep_hours) : '');
        
        const prs = data.personal_records || {};
        setPr5k(prs.run_5k || '');
        setPr10k(prs.run_10k || '');
        setPrHalf(prs.run_half || '');
        setPrBikeLongest(prs.bike_longest || '');
        setPrSwim100m(prs.swim_100m || '');
        setPrHikePeak(prs.hike_peak || '');
      }
    } catch (err) {
      console.error('Error fetching prepopulated profile:', err);
    }
    setLoading(false);
  };

  const handleConfirmProfileAndStartInterview = async () => {
    setLoading(true);
    try {
      const profilePayload = {
        age: age ? parseInt(age, 10) : null,
        weight: weight ? parseFloat(weight) : null,
        height: height ? parseFloat(height) : null,
        sport_history: sportHistory,
        running_experience: runningExperience,
        goals: {
          resting_hr: restingHr ? parseInt(restingHr, 10) : null,
          sleep_hours: sleepHours ? parseFloat(sleepHours) : null,
          personal_records: {
            run_5k: pr5k || null,
            run_10k: pr10k || null,
            run_half: prHalf || null,
            bike_longest: prBikeLongest || null,
            swim_100m: prSwim100m || null,
            hike_peak: prHikePeak || null,
          }
        }
      };

      const response = await fetch(`${apiUrl}/auth/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(profilePayload),
      });

      if (!response.ok) {
        const err = await response.json();
        Alert.alert('Error', err.error || 'Failed to save profile details.');
        setLoading(false);
        return;
      }

      await handleStartInterview();
    } catch (err) {
      console.error('Error confirming profile & starting interview:', err);
      Alert.alert('Error', 'Network error starting onboarding.');
    }
    setLoading(false);
  };

  const handleSendQuickReply = (text: string) => {
    handleSendMessageText(text);
  };

  const parseOptions = (text: string) => {
    const regex = /\[([^\]]+)\]/g;
    const options = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      options.push(match[1]);
    }
    return options;
  };

  const cleanMessageContent = (text: string) => {
    return text.replace(/\[([^\]]+)\]/g, '').trim();
  };

  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    if (user) {
      const status = user.coach_status;
      if (status === 'interview_completed') {
        setCoachStatus('completed_waiting_plan');
      } else if (status === 'plan_phased' || status === 'active') {
        setCoachStatus('active');
      } else if (status === 'interview_in_progress' || status === 'interviewing') {
        setCoachStatus('interviewing');
      } else {
        setCoachStatus('not_started');
      }

      if (user.interview_chat_id) {
        setActiveChatId(user.interview_chat_id);
        fetchChatMessages(user.interview_chat_id);
      }
    }
  }, [user]);

  useEffect(() => {
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated: true });
    }, 100);
  }, [messages, statusMessage]);

  const fetchChatMessages = async (chatId: number) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/chats/${chatId}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        setMessages(data.chat.messages || []);
      }
    } catch (err) {
      console.error('Error fetching chat messages:', err);
    }
    setLoading(false);
  };

  const handleStartInterview = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/coach/start_interview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setActiveChatId(data.chat_id);
        setCoachStatus('interviewing');
        
        // Add first question to message stream
        if (data.question) {
          setMessages([
            {
              sender: 'bot',
              content: data.question,
              timestamp: new Date().toISOString(),
            },
          ]);
        }
        
        // Update user context
        if (user) {
          setUser({
            ...user,
            coach_status: 'interviewing',
            interview_chat_id: data.chat_id,
          });
        }
      } else {
        const err = await response.json();
        Alert.alert('Error', err.error || 'Failed to start interview.');
      }
    } catch (err) {
      console.error('Error starting interview:', err);
      Alert.alert('Error', 'Network error starting onboarding interview.');
    }
    setLoading(false);
  };

  const handleSendMessage = () => {
    handleSendMessageText(inputText);
  };

  const handleSendMessageText = async (textToSend: string) => {
    if (!textToSend.trim() || !activeChatId) return;

    setInputText('');

    // Prepend page context
    const contextPrompt = `[Context: Fullscreen Onboarding Chat] ${textToSend}`;

    // Optimistically add user message
    const userMsg: Message = {
      sender: 'user',
      content: textToSend,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setStatusMessage('⚡ Coach Bro is calculating response...');

    try {
      const response = await fetch(`${apiUrl}/chats/${activeChatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ message: contextPrompt }),
      });

      if (!response.ok) throw new Error('Failed to send');

      const contentType = response.headers.get('content-type');

      // If it's the interview endpoint returning JSON (standard for questions)
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        setMessages((prev) => [
          ...prev,
          {
            sender: 'bot',
            content: data.message || data.content || data.question || '',
            timestamp: new Date().toISOString(),
            is_interview_complete: data.is_complete,
          },
        ]);

        if (data.is_complete) {
          setCoachStatus('completed_waiting_plan');
          if (user) {
            setUser({ ...user, coach_status: 'completed_waiting_plan' });
          }
        }
        setStatusMessage('');
        return;
      }

      // Stream fallback parsing
      if (response.body && typeof response.body.getReader === 'function') {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const rawJson = line.slice(6);
                if (rawJson.trim() === '[DONE]') continue;
                const data = JSON.parse(rawJson);

                if (data.status) setStatusMessage(data.status);
                if (data.token) {
                  setMessages((prev) => {
                    const updated = [...prev];
                    const lastMsg = { ...updated[updated.length - 1] };
                    lastMsg.content += data.token;
                    updated[updated.length - 1] = lastMsg;
                    return updated;
                  });
                }
                if (data.proposal) {
                  setMessages((prev) => {
                    const updated = [...prev];
                    const lastMsg = { ...updated[updated.length - 1] };
                    lastMsg.proposal = data.proposal;
                    updated[updated.length - 1] = lastMsg;
                    return updated;
                  });
                }
                if (data.done) setStatusMessage('');
              } catch (e) {}
            }
          }
        }
      } else {
        // Full response fallback
        const text = await response.text();
        const lines = text.split('\n\n');
        let fullAnswer = '';
        let proposal = null;

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.token) fullAnswer += data.token;
              if (data.proposal) proposal = data.proposal;
            } catch (e) {}
          }
        }

        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            sender: 'bot',
            content: fullAnswer || 'Answer complete.',
            proposal,
            timestamp: new Date().toISOString(),
          };
          return updated;
        });
        setStatusMessage('');
      }
    } catch (err) {
      console.error('Error in chat stream:', err);
      setStatusMessage('Error sending message');
    }
  };

  const handleGenerateTrainingPlan = async () => {
    setLoading(true);
    setStatusMessage('Analyzing profile & generating plan...');
    try {
      const response = await fetch(`${apiUrl}/coach/generate_plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ chat_id: activeChatId }),
      });

      if (response.ok) {
        setStatusMessage('Structuring plan into training phases...');
        // Structure plan into phases
        const phaseRes = await fetch(`${apiUrl}/coach/organize_plan`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
        });

        if (phaseRes.ok) {
          Alert.alert(
            'Plan Created!',
            'Coach Bro has generated and structured your calendar training plan! Check your Training calendar tab.'
          );
          setCoachStatus('active');
          if (user) {
            setUser({ ...user, coach_status: 'active' });
          }
        } else {
          Alert.alert('Partial Success', 'Plan was generated but failed to structure in phases.');
        }
      } else {
        const err = await response.json();
        Alert.alert('Plan Generation Failed', err.error || 'Failed to construct plan.');
      }
    } catch (err) {
      console.error('Plan generation error:', err);
      Alert.alert('Error', 'Network error generating calendar plan.');
    }
    setLoading(false);
    setStatusMessage('');
  };

  // 1. Initial Welcome / Interview Starting Screen
  if (coachStatus === 'not_started') {
    if (onboardingStep === 1) {
      return (
        <View style={styles.container}>
          <ScrollView contentContainerStyle={styles.introContainer} keyboardShouldPersistTaps="handled">
            <LinearGradient
              colors={['rgba(108, 99, 255, 0.15)', 'rgba(0, 229, 255, 0.05)']}
              style={styles.introCard}
            >
              <View style={styles.wizardHeader}>
                <Text style={styles.wizardStepText}>Step 1 of 2</Text>
                <Text style={styles.wizardTitle}>Connect Integrations or Health Data</Text>
                <Text style={styles.wizardSubTitle}>
                  Connect Apple Health, Garmin, or Strava — or proceed directly with manual baseline inputs.
                </Text>
              </View>

              {/* Apple HealthKit Card */}
              <View style={styles.integrationCard}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleRow}>
                    <View style={[styles.cardIconBox, { backgroundColor: 'rgba(239, 68, 68, 0.1)' }]}>
                      <Ionicons name="heart" size={20} color="#EF4444" />
                    </View>
                    <Text style={styles.cardTitle}>Apple Health (iOS)</Text>
                  </View>
                  <View
                    style={[
                      styles.statusBadge,
                      { backgroundColor: healthkitConnected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.1)' },
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusBadgeText,
                        { color: healthkitConnected ? '#10B981' : '#94A3B8' },
                      ]}
                    >
                      {healthkitConnected ? 'Connected' : 'Disconnected'}
                    </Text>
                  </View>
                </View>

                {!healthkitConnected ? (
                  <TouchableOpacity style={styles.connectButton} onPress={handleSyncHealthKit}>
                    <LinearGradient colors={['#EF4444', '#B91C1C']} style={styles.connectButtonGradient}>
                      <Text style={styles.connectButtonText}>Sync Apple HealthKit</Text>
                    </LinearGradient>
                  </TouchableOpacity>
                ) : (
                  <Text style={{ color: '#94A3B8', fontSize: 13, textAlign: 'center' }}>
                    Apple Health data (Resting HR, Sleep, HRV) connected and auto-imported.
                  </Text>
                )}
              </View>

              {/* Garmin Card */}
              <View style={styles.integrationCard}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleRow}>
                    <View style={styles.cardIconBox}>
                      <Ionicons name="watch-outline" size={20} color="#00E5FF" />
                    </View>
                    <Text style={styles.cardTitle}>Garmin Connect</Text>
                  </View>
                  <View
                    style={[
                      styles.statusBadge,
                      {
                        backgroundColor:
                          garminStatus === 'completed'
                            ? 'rgba(16, 185, 129, 0.15)'
                            : garminStatus === 'syncing' || garminStatus === 'connecting'
                            ? 'rgba(245, 158, 11, 0.15)'
                            : 'rgba(148, 163, 184, 0.1)',
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusBadgeText,
                        {
                          color:
                            garminStatus === 'completed'
                              ? '#10B981'
                              : garminStatus === 'syncing' || garminStatus === 'connecting'
                              ? '#F59E0B'
                              : '#94A3B8',
                        },
                      ]}
                    >
                      {garminStatus === 'completed'
                        ? 'Connected'
                        : garminStatus === 'syncing'
                        ? 'Syncing Data'
                        : garminStatus === 'connecting'
                        ? 'Connecting'
                        : 'Disconnected'}
                    </Text>
                  </View>
                </View>

                {garminStatus === 'disconnected' || garminStatus === 'failed' ? (
                  <View style={styles.formContainer}>
                    <Text style={styles.inputLabel}>Garmin Email</Text>
                    <TextInput
                      style={styles.inputField}
                      placeholder="email@example.com"
                      placeholderTextColor="#64748B"
                      value={garminEmail}
                      onChangeText={setGarminEmail}
                      keyboardType="email-address"
                      autoCapitalize="none"
                    />
                    <Text style={styles.inputLabel}>Garmin Password</Text>
                    <TextInput
                      style={styles.inputField}
                      placeholder="Password"
                      placeholderTextColor="#64748B"
                      secureTextEntry
                      value={garminPassword}
                      onChangeText={setGarminPassword}
                      autoCapitalize="none"
                    />
                    <TouchableOpacity style={styles.connectButton} onPress={handleConnectGarmin}>
                      <LinearGradient colors={['#6C63FF', '#3F3DA1']} style={styles.connectButtonGradient}>
                        <Text style={styles.connectButtonText}>Connect Garmin Account</Text>
                      </LinearGradient>
                    </TouchableOpacity>
                  </View>
                ) : (
                  <View style={{ width: '100%' }}>
                    <Text style={{ color: '#94A3B8', fontSize: 13, textAlign: 'center', lineHeight: 18 }}>
                      {garminStatus === 'completed'
                        ? 'Your Garmin account is successfully connected and training history is imported.'
                        : 'Syncing your activities, daily health, and sleep data...'}
                    </Text>
                    {(garminStatus === 'syncing' || garminStatus === 'connecting') && (
                      <View style={{ width: '100%', marginTop: 8 }}>
                        <ActivityIndicator size="small" color="#00E5FF" style={{ marginBottom: 4 }} />
                        <View style={styles.progressBarContainer}>
                          <View style={[styles.progressBarFill, { width: `${garminProgress}%` }]} />
                        </View>
                        <Text style={styles.progressText}>{garminProgress}% Synced</Text>
                      </View>
                    )}
                  </View>
                )}
              </View>

              {/* Strava Card */}
              <View style={styles.integrationCard}>
                <View style={styles.cardHeader}>
                  <View style={styles.cardTitleRow}>
                    <View style={[styles.cardIconBox, { backgroundColor: 'rgba(252, 76, 2, 0.1)' }]}>
                      <Ionicons name="flame-outline" size={20} color="#FC4C02" />
                    </View>
                    <Text style={styles.cardTitle}>Strava</Text>
                  </View>
                  <View
                    style={[
                      styles.statusBadge,
                      {
                        backgroundColor: stravaConnected
                          ? 'rgba(16, 185, 129, 0.15)'
                          : 'rgba(148, 163, 184, 0.1)',
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusBadgeText,
                        { color: stravaConnected ? '#10B981' : '#94A3B8' },
                      ]}
                    >
                      {stravaConnected ? 'Connected' : 'Disconnected'}
                    </Text>
                  </View>
                </View>

                {!stravaConnected ? (
                  <TouchableOpacity style={styles.connectButton} onPress={handleConnectStrava}>
                    <LinearGradient colors={['#FC4C02', '#C63600']} style={styles.connectButtonGradient}>
                      <Text style={styles.connectButtonText}>Connect Strava Account</Text>
                    </LinearGradient>
                  </TouchableOpacity>
                ) : (
                  <Text style={{ color: '#94A3B8', fontSize: 13, textAlign: 'center' }}>
                    Your Strava account is successfully connected and activities are synced.
                  </Text>
                )}
              </View>

              <View style={styles.wizardActions}>
                <TouchableOpacity
                  style={styles.nextBtn}
                  onPress={() => setOnboardingStep(2)}
                >
                  <LinearGradient colors={['#10B981', '#059669']} style={styles.nextBtnGradient}>
                    <Text style={styles.nextBtnText}>Next: Verify My Profile</Text>
                  </LinearGradient>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.skipLink}
                  onPress={() => setOnboardingStep(2)}
                >
                  <Text style={styles.skipLinkText}>Skip integrations for now</Text>
                </TouchableOpacity>
              </View>
            </LinearGradient>
          </ScrollView>
        </View>
      );
    } else if (onboardingStep === 2) {
      return (
        <View style={styles.container}>
          <ScrollView contentContainerStyle={styles.introContainer} keyboardShouldPersistTaps="handled">
            <LinearGradient
              colors={['rgba(16, 185, 129, 0.15)', 'rgba(0, 229, 255, 0.05)']}
              style={styles.introCard}
            >
              <View style={styles.wizardHeader}>
                <Text style={styles.wizardStepText}>Step 2 of 2</Text>
                <Text style={styles.wizardTitle}>Verify Baseline Profile</Text>
                <Text style={styles.wizardSubTitle}>
                  Verify or adjust the baseline details extracted from your connected accounts.
                </Text>
              </View>

              {loading ? (
                <View style={{ padding: 40, alignItems: 'center' }}>
                  <ActivityIndicator size="large" color="#00E5FF" />
                  <Text style={{ color: '#94A3B8', marginTop: 12, fontSize: 13 }}>Analyzing synced data...</Text>
                </View>
              ) : (
                <View style={{ width: '100%' }}>
                  <Text style={styles.sectionTitle}>Demographic & Bio</Text>
                  <View style={styles.formRow}>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Age (years)</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 30"
                        placeholderTextColor="#64748B"
                        keyboardType="numeric"
                        value={age}
                        onChangeText={setAge}
                      />
                    </View>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Weight (kg)</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 70"
                        placeholderTextColor="#64748B"
                        keyboardType="numeric"
                        value={weight}
                        onChangeText={setWeight}
                      />
                    </View>
                  </View>

                  <View style={styles.formRow}>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Height (cm)</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 175"
                        placeholderTextColor="#64748B"
                        keyboardType="numeric"
                        value={height}
                        onChangeText={setHeight}
                      />
                    </View>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Weekly Volume (km)</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 25"
                        placeholderTextColor="#64748B"
                        keyboardType="numeric"
                        value={weeklyVolume}
                        onChangeText={setWeeklyVolume}
                      />
                    </View>
                  </View>

                  {/* Sport History Selection */}
                  <Text style={styles.inputLabel}>Primary Sport</Text>
                  <View style={styles.selectorRow}>
                    {['Running', 'Cycling', 'Triathlon', 'Other'].map((sport) => (
                      <TouchableOpacity
                        key={sport}
                        style={[
                          styles.selectorPill,
                          sportHistory === sport && styles.selectorPillActive,
                        ]}
                        onPress={() => setSportHistory(sport)}
                      >
                        <Text
                          style={[
                            styles.selectorPillText,
                            sportHistory === sport && styles.selectorPillTextActive,
                          ]}
                        >
                          {sport}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  {/* Running Experience Selection */}
                  <Text style={styles.inputLabel}>Running Experience</Text>
                  <View style={styles.selectorRow}>
                    {['Beginner', 'Intermediate', 'Advanced'].map((level) => (
                      <TouchableOpacity
                        key={level}
                        style={[
                          styles.selectorPill,
                          runningExperience === level && styles.selectorPillActive,
                        ]}
                        onPress={() => setRunningExperience(level)}
                      >
                        <Text
                          style={[
                            styles.selectorPillText,
                            runningExperience === level && styles.selectorPillTextActive,
                          ]}
                        >
                          {level}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  <Text style={styles.sectionTitle}>Calculated Insights</Text>
                  <View style={styles.formRow}>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Resting HR (bpm)</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 60"
                        placeholderTextColor="#64748B"
                        keyboardType="numeric"
                        value={restingHr}
                        onChangeText={setRestingHr}
                      />
                    </View>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Avg Sleep (hours)</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 7.5"
                        placeholderTextColor="#64748B"
                        keyboardType="numeric"
                        value={sleepHours}
                        onChangeText={setSleepHours}
                      />
                    </View>
                  </View>

                  <Text style={styles.sectionTitle}>Personal Records</Text>
                  <View style={styles.formRow}>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>5k PR</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 22:30"
                        placeholderTextColor="#64748B"
                        value={pr5k}
                        onChangeText={setPr5k}
                      />
                    </View>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>10k PR</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 48:15"
                        placeholderTextColor="#64748B"
                        value={pr10k}
                        onChangeText={setPr10k}
                      />
                    </View>
                  </View>

                  <View style={styles.formRow}>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Half Marathon PR</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 1:45:00"
                        placeholderTextColor="#64748B"
                        value={prHalf}
                        onChangeText={setPrHalf}
                      />
                    </View>
                    <View style={styles.formCol}>
                      <Text style={styles.inputLabel}>Longest Ride</Text>
                      <TextInput
                        style={styles.inputField}
                        placeholder="e.g. 80 km"
                        placeholderTextColor="#64748B"
                        value={prBikeLongest}
                        onChangeText={setPrBikeLongest}
                      />
                    </View>
                  </View>

                  <View style={styles.wizardActions}>
                    <TouchableOpacity
                      style={styles.nextBtn}
                      onPress={handleConfirmProfileAndStartInterview}
                    >
                      <LinearGradient colors={['#10B981', '#059669']} style={styles.nextBtnGradient}>
                        <Text style={styles.nextBtnText}>Confirm Profile & Start Chat</Text>
                      </LinearGradient>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.skipLink}
                      onPress={() => setOnboardingStep(1)}
                    >
                      <Text style={styles.skipLinkText}>Back to Integrations</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}
            </LinearGradient>
          </ScrollView>
        </View>
      );
    }
  }

  // 2. Waiting for plan generation screen (Interview finished)
  if (coachStatus === 'completed_waiting_plan') {
    return (
      <View style={styles.container}>
        <View style={styles.introContainer}>
          <LinearGradient
            colors={['rgba(16, 185, 129, 0.15)', 'rgba(0, 229, 255, 0.05)']}
            style={styles.introCard}
          >
            <View style={[styles.introLogo, { borderColor: '#10B981' }]}>
              <Ionicons name="checkmark-done-circle" size={36} color="#10B981" />
            </View>
            <Text style={styles.introTitle}>Interview Completed!</Text>
            <Text style={styles.introDesc}>
              Awesome! Coach Bro has successfully collected all details about your experience, goals, and schedule.
            </Text>

            <TrainingVolumeChart />

            {statusMessage !== '' && (
              <View style={styles.planStatusBox}>
                <ActivityIndicator size="small" color="#00E5FF" style={{ marginRight: 8 }} />
                <Text style={styles.planStatusText}>{statusMessage}</Text>
              </View>
            )}

            <TouchableOpacity
              style={styles.startBtn}
              onPress={handleGenerateTrainingPlan}
              disabled={loading}
            >
              <LinearGradient colors={['#10B981', '#059669']} style={styles.startBtnGradient}>
                {loading ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.startBtnText}>Generate My Training Plan</Text>
                )}
              </LinearGradient>
            </TouchableOpacity>
          </LinearGradient>
        </View>
      </View>
    );
  }

  // 3. Full Chat Stream / Onboarding interview message logs screen
  return (
    <View style={styles.container}>
      {/* Reasoning Mode Header Switch */}
      <View style={styles.modeToggleBar}>
        <TouchableOpacity
          style={[styles.modePill, reasoningMode === 'fast' && styles.modePillActive]}
          onPress={() => setReasoningMode('fast')}
        >
          <Ionicons name="flash-outline" size={14} color={reasoningMode === 'fast' ? '#00E5FF' : '#94A3B8'} />
          <Text style={[styles.modePillText, reasoningMode === 'fast' && styles.modePillTextActive]}>⚡ Fast Mode</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.modePill, reasoningMode === 'deep_dive' && styles.modePillActive]}
          onPress={() => setReasoningMode('deep_dive')}
        >
          <Ionicons name="analytics-outline" size={14} color={reasoningMode === 'deep_dive' ? '#10B981' : '#94A3B8'} />
          <Text style={[styles.modePillText, reasoningMode === 'deep_dive' && styles.modePillTextActive]}>🧠 Deep Analysis</Text>
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 88 : 0}
      >
        <ScrollView
          ref={scrollViewRef}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {messages.map((msg, index) => {
            const isLastMessage = index === messages.length - 1;
            const options = msg.sender === 'bot' ? parseOptions(msg.content) : [];
            return (
              <View key={index} style={{ width: '100%', marginVertical: 6 }}>
                <View
                  style={[
                    styles.messageRow,
                    msg.sender === 'user' ? styles.userRow : styles.botRow,
                  ]}
                >
                  <View
                    style={[
                      styles.bubble,
                      msg.sender === 'user' ? styles.userBubble : styles.botBubble,
                    ]}
                  >
                    {msg.sender === 'bot' ? (
                      <MarkdownText content={cleanMessageContent(msg.content)} />
                    ) : (
                      <Text style={styles.messageText}>{msg.content}</Text>
                    )}
                  </View>
                </View>

                {msg.sender === 'bot' && isLastMessage && coachStatus === 'interviewing' && (
                  /days|schedule|frequency|which days|available days|days\/week|select days/i.test(msg.content)
                ) && (
                  <DaySelectorWidget onSelectDays={(formatted) => handleSendMessageText(formatted)} />
                )}

                {msg.sender === 'bot' && isLastMessage && coachStatus === 'interviewing' && options.length > 0 && (
                  <View style={styles.quickRepliesContainer}>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.quickRepliesScroll}>
                      {options.map((opt, oIdx) => (
                        <TouchableOpacity
                          key={`opt-${oIdx}`}
                          style={styles.quickReplyPill}
                          onPress={() => handleSendQuickReply(opt)}
                        >
                          <Text style={styles.quickReplyText}>{opt}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                )}
              </View>
            );
          })}

          {statusMessage !== '' && (
            <View style={styles.statusRow}>
              <ActivityIndicator size="small" color="#00E5FF" style={{ marginRight: 8 }} />
              <Text style={styles.statusText}>{statusMessage}</Text>
            </View>
          )}
        </ScrollView>

        <View style={styles.inputContainer}>
          <TextInput
            style={styles.textInput}
            placeholder="Type your reply here..."
            placeholderTextColor="#64748B"
            value={inputText}
            onChangeText={setInputText}
            onSubmitEditing={handleSendMessage}
            returnKeyType="send"
          />
          <TouchableOpacity style={styles.sendBtn} onPress={handleSendMessage}>
            <Ionicons name="send" size={18} color="#FFFFFF" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0A0E17',
  },
  modeToggleBar: {
    flexDirection: 'row',
    backgroundColor: '#1E293B',
    padding: 6,
    marginHorizontal: 16,
    marginTop: Platform.OS === 'ios' ? 50 : 16,
    marginBottom: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    justifyContent: 'space-between',
  },
  modePill: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    borderRadius: 8,
    marginHorizontal: 2,
  },
  modePillActive: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.4)',
  },
  modePillText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#94A3B8',
    marginLeft: 6,
  },
  modePillTextActive: {
    color: '#F8FAFC',
    fontWeight: 'bold',
  },
  introContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
    paddingBottom: 140,
  },
  introCard: {
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 28,
    alignItems: 'center',
  },
  introLogo: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.3)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  introTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 10,
  },
  introDesc: {
    fontSize: 13,
    color: '#94A3B8',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  startBtn: {
    borderRadius: 12,
    overflow: 'hidden',
    width: '100%',
  },
  startBtnGradient: {
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  startBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  keyboardView: {
    flex: 1,
    justifyContent: 'space-between',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 90, // space for keyboard
  },
  messageRow: {
    flexDirection: 'row',
    marginVertical: 6,
    width: '100%',
  },
  userRow: {
    justifyContent: 'flex-end',
  },
  botRow: {
    justifyContent: 'flex-start',
  },
  bubble: {
    padding: 12,
    borderRadius: 16,
    maxWidth: '85%',
  },
  userBubble: {
    backgroundColor: '#6C63FF',
    borderBottomRightRadius: 2,
  },
  botBubble: {
    backgroundColor: '#1E293B',
    borderBottomLeftRadius: 2,
    borderWidth: 1,
    borderColor: '#334155',
  },
  messageText: {
    color: '#F1F5F9',
    fontSize: 14,
    lineHeight: 20,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 8,
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(0, 229, 255, 0.05)',
    borderRadius: 8,
    marginVertical: 4,
  },
  statusText: {
    color: '#00E5FF',
    fontSize: 12,
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    alignItems: 'center',
    backgroundColor: '#0F172A',
  },
  textInput: {
    flex: 1,
    height: 40,
    backgroundColor: '#1E293B',
    borderRadius: 20,
    paddingHorizontal: 16,
    color: '#F8FAFC',
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sendBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#6C63FF',
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  planStatusBox: {
    flexDirection: 'row',
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    padding: 10,
    alignItems: 'center',
    marginBottom: 16,
    width: '100%',
  },
  planStatusText: {
    color: '#00E5FF',
    fontSize: 12,
    fontWeight: '600',
  },
  wizardHeader: {
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    marginBottom: 20,
    width: '100%',
    alignItems: 'center',
  },
  wizardStepText: {
    color: '#00E5FF',
    fontSize: 12,
    fontWeight: 'bold',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 4,
  },
  wizardTitle: {
    color: '#F8FAFC',
    fontSize: 20,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  wizardSubTitle: {
    color: '#94A3B8',
    fontSize: 13,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 18,
    paddingHorizontal: 8,
  },
  integrationCard: {
    width: '100%',
    backgroundColor: '#0F172A',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 16,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  cardTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  cardIconBox: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(0, 229, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  cardTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: 'bold',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: 'bold',
  },
  formContainer: {
    width: '100%',
  },
  inputLabel: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 6,
    fontWeight: '600',
  },
  inputField: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    height: 40,
    color: '#F8FAFC',
    paddingHorizontal: 12,
    fontSize: 14,
    marginBottom: 12,
  },
  connectButton: {
    borderRadius: 8,
    overflow: 'hidden',
    marginTop: 4,
  },
  connectButtonGradient: {
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  connectButtonText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 13,
  },
  progressBarContainer: {
    height: 6,
    backgroundColor: '#1E293B',
    borderRadius: 3,
    width: '100%',
    overflow: 'hidden',
    marginTop: 12,
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#00E5FF',
    borderRadius: 3,
  },
  progressText: {
    color: '#00E5FF',
    fontSize: 11,
    marginTop: 4,
    fontWeight: '600',
    textAlign: 'right',
  },
  wizardActions: {
    width: '100%',
    marginTop: 12,
    alignItems: 'center',
  },
  nextBtn: {
    borderRadius: 12,
    overflow: 'hidden',
    width: '100%',
    marginBottom: 16,
  },
  nextBtnGradient: {
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  nextBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 15,
  },
  skipLink: {
    paddingVertical: 8,
  },
  skipLinkText: {
    color: '#94A3B8',
    fontSize: 13,
    textDecorationLine: 'underline',
  },
  sectionTitle: {
    color: '#00E5FF',
    fontSize: 14,
    fontWeight: 'bold',
    marginTop: 16,
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  formRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
  },
  formCol: {
    width: '48%',
  },
  quickRepliesContainer: {
    marginTop: 8,
    width: '100%',
  },
  quickRepliesScroll: {
    paddingHorizontal: 4,
    paddingVertical: 2,
  },
  quickReplyPill: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#00E5FF',
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 16,
    marginRight: 8,
  },
  staticPill: {
    borderColor: '#6C63FF',
  },
  quickReplyText: {
    color: '#F1F5F9',
    fontSize: 13,
    fontWeight: '600',
  },
  selectorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 16,
  },
  selectorPill: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginRight: 8,
    marginBottom: 8,
  },
  selectorPillActive: {
    backgroundColor: 'rgba(0, 229, 255, 0.15)',
    borderColor: '#00E5FF',
  },
  selectorPillText: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: '600',
  },
  selectorPillTextActive: {
    color: '#00E5FF',
  },
});
