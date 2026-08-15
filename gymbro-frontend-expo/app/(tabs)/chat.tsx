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
} from 'react-native';
import { AuthContext } from '../../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { MarkdownText } from '../../components/MarkdownText';
import Colors from '../../constants/Colors';
import { isGymbroWidget, ChatWidgetEnvelope } from '../../services/widgetProtocol';
import { InteractiveChartWidget } from '../../components/chat/InteractiveChartWidget';
import { PlanProposalWidget } from '../../components/chat/PlanProposalWidget';
import { MacroSliderWidget } from '../../components/chat/MacroSliderWidget';
import { ReadinessActionWidget } from '../../components/chat/ReadinessActionWidget';

interface Message {
  sender: 'user' | 'bot' | 'system';
  content: string;
  timestamp: string;
  ui_payload?: any;
}


export default function ChatScreen() {
  const { authToken, user, apiUrl } = useContext(AuthContext);
  const [agentMode, setAgentMode] = useState<'fast' | 'debug' | 'rag'>('fast');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);

  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    if (authToken) {
      initChatSession();
    }
  }, [authToken]);

  useEffect(() => {
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated: true });
    }, 100);
  }, [messages, statusMessage]);

  const initChatSession = async () => {
    setLoading(true);
    try {
      // Fetch user's existing chats
      const response = await fetch(`${apiUrl}/chats`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        const chats = data.chats || [];
        if (chats.length > 0) {
          const mainChat = chats[0];
          setActiveChatId(mainChat.id);
          fetchChatMessages(mainChat.id);
        } else {
          createNewChatSession('Athletic Intelligence Consultation');
        }
      }
    } catch (err) {
      console.error('Error initializing chat session:', err);
    }
    setLoading(false);
  };

  const createNewChatSession = async (title: string = 'Athletic Intelligence Consultation') => {
    try {
      const response = await fetch(`${apiUrl}/chats`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ title }),
      });
      if (response.ok) {
        const data = await response.json();
        const newChat = data.chat;
        setActiveChatId(newChat.id);
        setMessages([
          {
            sender: 'bot',
            content: `👋 Hello! I am your GYMBro AI Athletic Intelligence Agent.\n\nAsk me anything about your recovery, plan a race, adjust your macros, or analyze your HRV.`,
            timestamp: new Date().toISOString(),
          },
        ]);
      }
    } catch (err) {
      console.error('Error creating chat session:', err);
    }
  };

  const fetchChatMessages = async (chatId: number) => {
    try {
      const response = await fetch(`${apiUrl}/chats/${chatId}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        const fetchedMsgs = data.chat?.messages || [];
        if (fetchedMsgs.length === 0) {
          setMessages([
            {
              sender: 'bot',
              content: `👋 Welcome back! I have loaded your latest biometric context.\n\nHow can I help you optimize your training today?`,
              timestamp: new Date().toISOString(),
            },
          ]);
        } else {
          setMessages(fetchedMsgs);
        }
      }
    } catch (err) {
      console.error('Error fetching chat messages:', err);
    }
  };

  const handleQuickPrompt = (promptText: string) => {
    setInputText(promptText);
    handleSendMessageText(promptText);
  };

  const handleSendMessage = () => {
    if (!inputText.trim()) return;
    handleSendMessageText(inputText);
  };

  const handleSendMessageText = async (textToSend: string) => {
    if (!textToSend.trim() || loading) return;

    let chatId = activeChatId;
    if (!chatId) {
      await createNewChatSession();
      chatId = activeChatId;
    }

    setInputText('');

    const userMsg: Message = {
      sender: 'user',
      content: textToSend,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setStatusMessage(
      agentMode === 'fast'
        ? '⚡ Fast Context (<50ms)...'
        : agentMode === 'debug'
        ? '🔍 Analyzing Telemetry & Debug Traces...'
        : '🧠 Multi-hop Deep RAG Search...'
    );

    try {
      const response = await fetch(`${apiUrl}/coach/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          message: textToSend,
          chat_id: chatId,
          mode: agentMode,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const botMsg: Message = {
          sender: 'bot',
          content: data.reply || data.message || "I've processed your update.",
          timestamp: new Date().toISOString(),
          ui_payload: data.ui_payload || data.chart_data || null,
        };
        setMessages((prev) => [...prev, botMsg]);
      } else {
        const errorData = await response.json().catch(() => ({}));
        const errorMsg: Message = {
          sender: 'bot',
          content: `⚠️ Could not complete request: ${errorData.error || 'Server error'}`,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    } catch (err: any) {
      console.error('Error sending chat message:', err);
      const errorMsg: Message = {
        sender: 'bot',
        content: `⚠️ Connection error: ${err.message || 'Please check backend server connection.'}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      setStatusMessage('');
    }
  };

  const handleExecuteWidgetAction = async (widgetId: string, actionId: string, actionPayload?: any) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.ui_payload && (msg.ui_payload.widget_id === widgetId || msg.ui_payload.payload?.chart_id === widgetId)) {
          return {
            ...msg,
            ui_payload: {
              ...msg.ui_payload,
              state: 'confirmed',
              last_action_result: 'Action executed successfully.',
            },
          };
        }
        return msg;
      })
    );

    if (activeChatId && authToken) {
      try {
        await fetch(`${apiUrl}/chats/${activeChatId}/actions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({
            action: actionId,
            data: actionPayload || { widget_id: widgetId },
          }),
        });
      } catch (err) {
        console.warn('Widget action dispatch warning:', err);
      }
    }
  };

  const renderUiPayload = (payload: any) => {
    if (!payload) return null;

    if (isGymbroWidget(payload)) {
      switch (payload.widget_type) {
        case 'interactive_chart':
          return (
            <InteractiveChartWidget
              widget={payload}
              onTriggerPrompt={handleSendMessageText}
              onExecuteAction={handleExecuteWidgetAction}
            />
          );
        case 'calendar_proposal':
          return (
            <PlanProposalWidget
              widget={payload}
              onExecuteAction={handleExecuteWidgetAction}
            />
          );
        case 'macro_slider':
          return (
            <MacroSliderWidget
              widget={payload}
              onExecuteAction={handleExecuteWidgetAction}
            />
          );
        case 'readiness_action':
          return (
            <ReadinessActionWidget
              widget={payload}
              onExecuteAction={handleExecuteWidgetAction}
            />
          );
        default:
          break;
      }
    }

    // Auto-convert legacy chart payloads to InteractiveChartWidget
    if (payload.type === 'chart' || payload.type === 'CHART' || payload.labels || payload.data?.labels) {
      const chartData = payload.data || payload;
      const labels: string[] = chartData.labels || [];
      const datasets: any[] = chartData.datasets || [];
      const points = labels.map((lbl: string, idx: number) => {
        const vals: Record<string, number> = {};
        datasets.forEach((ds: any) => {
          vals[ds.label || 'Metric'] = ds.data?.[idx] ?? 0;
        });
        return {
          date: lbl,
          label: lbl,
          values: vals,
        };
      });

      const metrics = datasets.map((ds: any) => ({
        key: ds.label || 'Metric',
        label: ds.label || 'Metric',
        unit: '',
        color: ds.borderColor || Colors.light.primary,
        y_axis: 'left' as const,
        chart_type: 'line' as const,
      }));

      const convertedEnvelope: ChatWidgetEnvelope = {
        protocol: 'gymbro.widget/v1',
        widget_id: `chart_${Date.now()}`,
        widget_type: 'interactive_chart',
        title: chartData.title || payload.title || 'Biometric Trend',
        subtitle: '60fps interactive scrubbing',
        state: 'active',
        payload: {
          chart_id: `chart_${Date.now()}`,
          time_range: '7d',
          metrics: metrics.length > 0 ? metrics : [{ key: 'Metric', label: 'Metric', unit: '', color: Colors.light.primary, y_axis: 'left', chart_type: 'line' }],
          points: points.length > 0 ? points : [{ date: 'Today', label: 'Today', values: { Metric: 0 } }],
          interactive_scrubbing: true,
        },
        actions: [],
        emitted_at: new Date().toISOString(),
      };

      return (
        <InteractiveChartWidget
          widget={convertedEnvelope}
          onTriggerPrompt={handleSendMessageText}
          onExecuteAction={handleExecuteWidgetAction}
        />
      );
    }

    if (payload.type === 'plan_preview' || payload.phases) {
      return (
        <View style={styles.payloadCard}>
          <View style={styles.payloadHeader}>
            <Ionicons name="calendar" size={16} color={Colors.light.vitality} />
            <Text style={styles.payloadTitle}>{payload.name || 'Structured Plan'}</Text>
          </View>
          <Text style={styles.payloadSubtitle}>
            {payload.weeks_count ? `${payload.weeks_count} Weeks • ${payload.phases?.length || 0} Phases` : 'Plan Details'}
          </Text>
        </View>
      );
    }

    return null;
  };


  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {/* Warm Ambient Top Bar */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <View style={styles.avatarCircle}>
            <Ionicons name="sparkles" size={18} color="#FFFFFF" />
          </View>
          <View>
            <Text style={styles.coachName}>AI Coach</Text>
            <Text style={styles.coachStatusText}>
              {agentMode === 'fast'
                ? '⚡ Fast Context (<50ms)'
                : agentMode === 'debug'
                ? '🔍 Debug Trace Mode'
                : '🧠 Deep Context RAG'}
            </Text>
          </View>
        </View>

        <TouchableOpacity
          style={styles.newChatBtn}
          onPress={() => createNewChatSession('New Consultation')}
        >
          <Ionicons name="add" size={16} color={Colors.light.primary} />
          <Text style={styles.newChatText}>New</Text>
        </TouchableOpacity>
      </View>

      {/* Agent Mode Selector Switcher */}
      <View style={styles.modeBar}>
        <TouchableOpacity
          style={[styles.modeChip, agentMode === 'fast' && styles.modeChipActive]}
          onPress={() => setAgentMode('fast')}
        >
          <Text style={[styles.modeChipText, agentMode === 'fast' && styles.modeChipTextActive]}>
            ⚡ Fast Context
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.modeChip, agentMode === 'debug' && styles.modeChipActive]}
          onPress={() => setAgentMode('debug')}
        >
          <Text style={[styles.modeChipText, agentMode === 'debug' && styles.modeChipTextActive]}>
            🔍 Debug
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.modeChip, agentMode === 'rag' && styles.modeChipActive]}
          onPress={() => setAgentMode('rag')}
        >
          <Text style={[styles.modeChipText, agentMode === 'rag' && styles.modeChipTextActive]}>
            🧠 Deep RAG
          </Text>
        </TouchableOpacity>
      </View>

      {/* Messages List */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.messageList}
        contentContainerStyle={styles.messageContent}
      >
        {messages.map((msg, index) => {
          const isUser = msg.sender === 'user';
          return (
            <View
              key={index}
              style={[
                styles.msgRow,
                isUser ? styles.msgRowUser : styles.msgRowBot,
              ]}
            >
              {!isUser && (
                <View style={styles.botIcon}>
                  <Ionicons name="sparkles" size={14} color={Colors.light.primary} />
                </View>
              )}
              <View
                style={[
                  styles.msgBubble,
                  isUser ? styles.msgBubbleUser : styles.msgBubbleBot,
                ]}
              >
                <MarkdownText
                  content={msg.content}
                  textColor={isUser ? '#FFFFFF' : Colors.light.text}
                />
                {msg.ui_payload && renderUiPayload(msg.ui_payload)}
                <Text
                  style={[
                    styles.timestampText,
                    isUser ? styles.timestampUser : styles.timestampBot,
                  ]}
                >
                  {new Date(msg.timestamp).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </Text>
              </View>
            </View>
          );
        })}

        {loading && statusMessage ? (
          <View style={styles.statusRow}>
            <ActivityIndicator size="small" color={Colors.light.primary} style={{ marginRight: 8 }} />
            <Text style={styles.statusText}>{statusMessage}</Text>
          </View>
        ) : null}
      </ScrollView>

      {/* Quick Interactive Prompt Suggestions */}
      <View style={styles.quickPromptsContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <TouchableOpacity
            style={styles.quickPill}
            onPress={() => handleQuickPrompt('How is my HRV and sleep recovery looking?')}
          >
            <Text style={styles.quickPillText}>🌿 How's my recovery?</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.quickPill}
            onPress={() => handleQuickPrompt('Can you generate my upcoming training plan?')}
          >
            <Text style={styles.quickPillText}>🏃 Generate training plan</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.quickPill}
            onPress={() => handleQuickPrompt('Review my recent running pace and mileage.')}
          >
            <Text style={styles.quickPillText}>📊 Review my running pace</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.quickPill}
            onPress={() => handleQuickPrompt('What should my daily macros be for muscle gain?')}
          >
            <Text style={styles.quickPillText}>🥩 Macro recommendations</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>

      {/* Warm Input Container */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.textInput}
          placeholder="Ask your athletic agent..."
          placeholderTextColor={Colors.light.mutedText}
          value={inputText}
          onChangeText={setInputText}
          multiline
          maxLength={1000}
        />
        <TouchableOpacity
          style={[styles.sendBtn, !inputText.trim() && styles.sendBtnDisabled]}
          onPress={handleSendMessage}
          disabled={!inputText.trim() || loading}
        >
          <LinearGradient
            colors={[Colors.light.primary, Colors.light.primaryHover]}
            style={styles.sendGradient}
          >
            <Ionicons name="arrow-up" size={20} color="#FFFFFF" />
          </LinearGradient>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: Colors.light.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.borderSubtle,
    shadowColor: Colors.light.shadowColor,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 8,
  },
  topBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatarCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: Colors.light.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    shadowColor: Colors.light.primary,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
  },
  coachName: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.light.text,
    letterSpacing: -0.3,
  },
  coachStatusText: {
    fontSize: 11,
    color: Colors.light.vitality,
    fontWeight: '600',
    marginTop: 1,
  },
  newChatBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
  },
  newChatText: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.light.primary,
    marginLeft: 4,
  },
  messageList: {
    flex: 1,
  },
  messageContent: {
    padding: 16,
    paddingBottom: 24,
  },
  msgRow: {
    flexDirection: 'row',
    marginBottom: 16,
    maxWidth: '88%',
  },
  msgRowUser: {
    alignSelf: 'flex-end',
    justifyContent: 'flex-end',
  },
  msgRowBot: {
    alignSelf: 'flex-start',
  },
  botIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: Colors.light.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
    marginTop: 4,
  },
  msgBubble: {
    borderRadius: 20,
    padding: 14,
    shadowColor: Colors.light.shadowColor,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
  },
  msgBubbleUser: {
    backgroundColor: Colors.light.primary,
    borderBottomRightRadius: 4,
  },
  msgBubbleBot: {
    backgroundColor: Colors.light.card,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderBottomLeftRadius: 4,
  },
  timestampText: {
    fontSize: 10,
    marginTop: 6,
    alignSelf: 'flex-end',
  },
  timestampUser: {
    color: 'rgba(255, 255, 255, 0.75)',
  },
  timestampBot: {
    color: Colors.light.mutedText,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: Colors.light.card,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginTop: 8,
    shadowColor: Colors.light.shadowColor,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 4,
  },
  statusText: {
    fontSize: 12,
    color: Colors.light.primary,
    fontWeight: '600',
  },
  quickPromptsContainer: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: Colors.light.card,
    borderTopWidth: 1,
    borderTopColor: Colors.light.borderSubtle,
  },
  quickPill: {
    backgroundColor: Colors.light.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    marginRight: 8,
  },
  quickPillText: {
    fontSize: 12,
    color: Colors.light.text,
    fontWeight: '600',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: Colors.light.card,
    borderTopWidth: 1,
    borderTopColor: Colors.light.borderSubtle,
  },
  textInput: {
    flex: 1,
    maxHeight: 100,
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 14,
    color: Colors.light.text,
    marginRight: 10,
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    overflow: 'hidden',
  },
  sendBtnDisabled: {
    opacity: 0.35,
  },
  sendGradient: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  payloadCard: {
    marginTop: 12,
    padding: 12,
    backgroundColor: Colors.light.cardSubtle,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  payloadHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  payloadTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.light.text,
    marginLeft: 6,
  },
  payloadSubtitle: {
    fontSize: 12,
    color: Colors.light.secondaryText,
  },
  actionCommitBtn: {
    marginTop: 10,
    backgroundColor: Colors.light.primary,
    paddingVertical: 8,
    borderRadius: 10,
    alignItems: 'center',
  },
  actionCommitBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 12,
  },
  modeBar: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: Colors.light.background,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.borderSubtle,
    gap: 8,
  },
  modeChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    backgroundColor: Colors.light.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.light.borderSubtle,
  },
  modeChipActive: {
    backgroundColor: Colors.light.primaryLight,
    borderColor: Colors.light.primary,
  },
  modeChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.light.secondaryText,
  },
  modeChipTextActive: {
    color: Colors.light.primary,
    fontWeight: '700',
  },
});

