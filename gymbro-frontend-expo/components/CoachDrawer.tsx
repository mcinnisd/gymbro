import React, { useState, useEffect, useRef, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  TextInput,
  ScrollView,
  Animated,
  Dimensions,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { AuthContext } from '../context/AuthContext';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');
const DRAWER_PEEK_HEIGHT = 60;
const DRAWER_EXPANDED_HEIGHT = SCREEN_HEIGHT * 0.75;

interface Message {
  sender: 'user' | 'bot' | 'system';
  content: string;
  timestamp: string;
  is_interview_complete?: boolean;
  proposal?: any;
  chart_data?: any;
}

export default function CoachDrawer() {
  const { authToken, user, apiUrl } = useContext(AuthContext);
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatId, setChatId] = useState<number | null>(null);

  const slideAnim = useRef(new Animated.Value(SCREEN_HEIGHT - DRAWER_PEEK_HEIGHT)).current;
  const scrollViewRef = useRef<ScrollView>(null);

  // Initialize or fetch the active coach chat session
  useEffect(() => {
    if (authToken) {
      fetchOrCreateChat();
    }
  }, [authToken]);

  // Scroll to bottom when messages or open state changes
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        scrollViewRef.current?.scrollToEnd({ animated: true });
      }, 300);
    }
  }, [messages, isOpen, statusMessage]);

  const fetchOrCreateChat = async () => {
    try {
      // 1. Get existing chats
      const response = await fetch(`${apiUrl}/chats/`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!response.ok) throw new Error('Failed to fetch chats');
      const data = await response.json();
      
      // Look for a chat that is not an interview, or the first chat
      const existingChat = data.chats.find((c: any) => c.type !== 'interview') || data.chats[0];

      if (existingChat) {
        setChatId(existingChat.id);
        setMessages(existingChat.messages || []);
      } else {
        // Create a new general coach session
        const createRes = await fetch(`${apiUrl}/chats/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({ title: 'Coach Bro' }),
        });
        if (createRes.ok) {
          const createData = await createRes.json();
          setChatId(createData.chat_id);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error('Error fetching/creating chat:', err);
    }
  };

  const toggleDrawer = () => {
    const toValue = isOpen
      ? SCREEN_HEIGHT - DRAWER_PEEK_HEIGHT
      : SCREEN_HEIGHT - DRAWER_EXPANDED_HEIGHT;

    Animated.spring(slideAnim, {
      toValue,
      useNativeDriver: true,
      tension: 40,
      friction: 8,
    }).start();

    setIsOpen(!isOpen);
  };

  const handleSendMessage = async () => {
    if (!inputText.trim() || !chatId) return;

    const userMessageContent = inputText;
    setInputText('');

    // Prepend a page route context string so the agent is aware of what screen we are currently looking at!
    const contextPrompt = `[Context: User is currently on screen "${pathname}"] ${userMessageContent}`;

    // Optimistically update UI
    const userMsg: Message = {
      sender: 'user',
      content: userMessageContent,
      timestamp: new Date().toISOString(),
    };
    const botPlaceholder: Message = {
      sender: 'bot',
      content: '',
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg, botPlaceholder]);
    setStatusMessage('Thinking...');

    try {
      const response = await fetch(`${apiUrl}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ message: contextPrompt }),
      });

      if (!response.ok) throw new Error('Send failed');

      const contentType = response.headers.get('content-type');

      // If it's a JSON response (like the interview check-in replies)
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            sender: 'bot',
            content: data.message || data.content || '',
            timestamp: new Date().toISOString(),
            is_interview_complete: data.is_complete,
          };
          return updated;
        });
        setStatusMessage('');
        return;
      }

      // Handle stream (with fallback for React Native native environment)
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

                if (data.status) {
                  setStatusMessage(data.status);
                }
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
                    if (!lastMsg.content) {
                      lastMsg.content = `I propose executing ${data.proposal.action}:`;
                    }
                    updated[updated.length - 1] = lastMsg;
                    return updated;
                  });
                }
                if (data.chart) {
                  setMessages((prev) => {
                    const updated = [...prev];
                    const lastMsg = { ...updated[updated.length - 1] };
                    lastMsg.chart_data = data.chart;
                    updated[updated.length - 1] = lastMsg;
                    return updated;
                  });
                }
                if (data.done) {
                  setStatusMessage('');
                }
              } catch (e) {
                // Ignore incomplete JSON chunks
              }
            }
          }
        }
      } else {
        // Fallback: Read full response text (essential for Expo Go native builds)
        const text = await response.text();
        // Parse individual SSE lines
        const lines = text.split('\n\n');
        let fullAnswer = '';
        let proposal = null;
        let chart = null;

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.token) fullAnswer += data.token;
              if (data.proposal) proposal = data.proposal;
              if (data.chart) chart = data.chart;
            } catch (e) {}
          }
        }

        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            sender: 'bot',
            content: fullAnswer || 'Action prepared.',
            proposal,
            chart_data: chart,
            timestamp: new Date().toISOString(),
          };
          return updated;
        });
        setStatusMessage('');
      }
    } catch (err) {
      console.error('Error sending message:', err);
      setStatusMessage('Error connection');
    }
  };

  const handleApproveProposal = async (proposal: any, msgIndex: number) => {
    if (!chatId) return;
    setStatusMessage('Executing action...');
    try {
      const response = await fetch(`${apiUrl}/chats/${chatId}/actions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          action: proposal.action,
          data: proposal.data,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        // Clear proposal from message so user can't double-approve
        setMessages((prev) => {
          const updated = [...prev];
          const msg = { ...updated[msgIndex] };
          delete msg.proposal;
          updated[msgIndex] = msg;
          return [
            ...updated,
            {
              sender: 'system',
              content: `✅ Action completed: ${result.message || 'Success'}`,
              timestamp: new Date().toISOString(),
            },
          ];
        });
      } else {
        const err = await response.json();
        Alert.alert('Execution Error', err.error || 'Failed to complete action.');
      }
    } catch (error) {
      console.error('Error approving proposal:', error);
      Alert.alert('Error', 'Network error executing action.');
    }
    setStatusMessage('');
  };

  const handleDenyProposal = (msgIndex: number) => {
    setMessages((prev) => {
      const updated = [...prev];
      const msg = { ...updated[msgIndex] };
      delete msg.proposal;
      updated[msgIndex] = msg;
      return [
        ...updated,
        {
          sender: 'system',
          content: '❌ Proposal denied.',
          timestamp: new Date().toISOString(),
        },
      ];
    });
  };

  if (!authToken) return null;

  return (
    <Animated.View style={[styles.drawerContainer, { transform: [{ translateY: slideAnim }] }]}>
      {/* Peek Header */}
      <TouchableOpacity activeOpacity={0.9} style={styles.header} onPress={toggleDrawer}>
        <View style={styles.headerIndicator} />
        <View style={styles.headerContent}>
          <View style={styles.titleRow}>
            <View style={styles.liveDot} />
            <Text style={styles.headerTitle}>Coach Bro</Text>
            {pathname !== '/' && (
              <Text style={styles.contextBadge}>Viewing {pathname.replace('/', '') || 'Dashboard'}</Text>
            )}
          </View>
          <Ionicons
            name={isOpen ? 'chevron-down' : 'chevron-up'}
            size={20}
            color="#94A3B8"
          />
        </View>
      </TouchableOpacity>

      {/* Expanded Content */}
      {isOpen && (
        <KeyboardAvoidingView
          style={styles.keyboardView}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          keyboardVerticalOffset={20}
        >
          {/* Scroll Area */}
          <ScrollView
            ref={scrollViewRef}
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
          >
            {messages.length === 0 ? (
              <View style={styles.emptyContainer}>
                <Ionicons name="chatbubbles-outline" size={48} color="#475569" />
                <Text style={styles.emptyText}>Hey Bro! Ask me anything about your runs, recovery, or diet.</Text>
              </View>
            ) : (
              messages.map((msg, index) => (
                <View
                  key={index}
                  style={[
                    styles.messageRow,
                    msg.sender === 'user'
                      ? styles.userRow
                      : msg.sender === 'system'
                      ? styles.systemRow
                      : styles.botRow,
                  ]}
                >
                  <View
                    style={[
                      styles.bubble,
                      msg.sender === 'user'
                        ? styles.userBubble
                        : msg.sender === 'system'
                        ? styles.systemBubble
                        : styles.botBubble,
                    ]}
                  >
                    <Text
                      style={[
                        styles.senderName,
                        msg.sender === 'user' ? styles.userSender : styles.botSender,
                      ]}
                    >
                      {msg.sender === 'user'
                        ? 'You'
                        : msg.sender === 'system'
                        ? 'System'
                        : 'Coach Bro'}
                    </Text>
                    <Text style={styles.messageText}>{msg.content}</Text>

                    {/* Proposal Widget */}
                    {msg.proposal && (
                      <View style={styles.proposalCard}>
                        <View style={styles.proposalHeader}>
                          <Ionicons name="git-pull-request-outline" size={16} color="#00E5FF" />
                          <Text style={styles.proposalTitle}>Proposed Action</Text>
                        </View>
                        <Text style={styles.proposalDetails}>
                          Type: <Text style={styles.bold}>{msg.proposal.action}</Text>
                        </Text>
                        {msg.proposal.data && (
                          <Text style={styles.proposalDetailsJSON}>
                            {JSON.stringify(msg.proposal.data, null, 2)}
                          </Text>
                        )}
                        <View style={styles.proposalButtons}>
                          <TouchableOpacity
                            style={[styles.propBtn, styles.approveBtn]}
                            onPress={() => handleApproveProposal(msg.proposal, index)}
                          >
                            <Text style={styles.propBtnText}>Approve</Text>
                          </TouchableOpacity>
                          <TouchableOpacity
                            style={[styles.propBtn, styles.denyBtn]}
                            onPress={() => handleDenyProposal(index)}
                          >
                            <Text style={styles.propBtnText}>Deny</Text>
                          </TouchableOpacity>
                        </View>
                      </View>
                    )}

                    {/* Chart Widget */}
                    {msg.chart_data && (
                      <View style={styles.chartWidget}>
                        <Text style={styles.chartTitle}>📊 {msg.chart_data.title || 'Metric Trend'}</Text>
                        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                          <View style={styles.chartBarRow}>
                            {msg.chart_data.data?.map((val: any, idx: number) => {
                              const value = typeof val === 'object' ? val.value : val;
                              const label = typeof val === 'object' ? val.label : `${idx + 1}`;
                              // Normalize height for rendering (e.g. max height 80)
                              const heightVal = Math.min(Math.max((value / (msg.chart_data.max_val || 100)) * 80, 10), 80);
                              return (
                                <View key={idx} style={styles.chartCol}>
                                  <View style={[styles.chartBar, { height: heightVal }]} />
                                  <Text style={styles.chartLabel} numberOfLines={1}>
                                    {label}
                                  </Text>
                                  <Text style={styles.chartVal}>{value}</Text>
                                </View>
                              );
                            })}
                          </View>
                        </ScrollView>
                      </View>
                    )}
                  </View>
                </View>
              ))
            )}

            {/* Status Update Banner */}
            {statusMessage !== '' && (
              <View style={styles.statusRow}>
                <ActivityIndicator size="small" color="#00E5FF" style={{ marginRight: 8 }} />
                <Text style={styles.statusText}>{statusMessage}</Text>
              </View>
            )}
          </ScrollView>

          {/* Chat Input Area */}
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.textInput}
              placeholder="Ask Coach Bro... (e.g. 'reschedule tomorrow's workout')"
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
      )}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  drawerContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#0F172A',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: '#334155',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 20,
    zIndex: 9999,
  },
  header: {
    height: DRAWER_PEEK_HEIGHT,
    justifyContent: 'center',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    paddingHorizontal: 20,
  },
  headerIndicator: {
    width: 36,
    height: 4,
    backgroundColor: '#475569',
    borderRadius: 2,
    marginBottom: 6,
  },
  headerContent: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#10B981',
    marginRight: 8,
    shadowColor: '#10B981',
    shadowOpacity: 0.6,
    shadowRadius: 4,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  contextBadge: {
    fontSize: 11,
    color: '#00E5FF',
    backgroundColor: 'rgba(0, 229, 255, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
    marginLeft: 10,
    fontWeight: '600',
  },
  keyboardView: {
    height: DRAWER_EXPANDED_HEIGHT - DRAWER_PEEK_HEIGHT,
    justifyContent: 'space-between',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 24,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    color: '#94A3B8',
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 20,
    paddingHorizontal: 20,
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
  systemRow: {
    justifyContent: 'center',
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
  systemBubble: {
    backgroundColor: 'rgba(251, 191, 36, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(251, 191, 36, 0.3)',
    borderRadius: 10,
  },
  senderName: {
    fontSize: 10,
    fontWeight: '600',
    marginBottom: 4,
  },
  userSender: {
    color: 'rgba(255,255,255,0.7)',
  },
  botSender: {
    color: '#94A3B8',
  },
  messageText: {
    color: '#F1F5F9',
    fontSize: 14,
    lineHeight: 20,
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
  proposalCard: {
    marginTop: 10,
    padding: 10,
    backgroundColor: '#0F172A',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#334155',
  },
  proposalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  proposalTitle: {
    color: '#00E5FF',
    fontSize: 13,
    fontWeight: 'bold',
    marginLeft: 6,
  },
  proposalDetails: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 4,
  },
  bold: {
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  proposalDetailsJSON: {
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontSize: 10,
    color: '#F1F5F9',
    backgroundColor: '#1E293B',
    padding: 6,
    borderRadius: 4,
    marginBottom: 8,
  },
  proposalButtons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
  },
  propBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    marginLeft: 8,
  },
  approveBtn: {
    backgroundColor: '#10B981',
  },
  denyBtn: {
    backgroundColor: '#EF4444',
  },
  propBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  chartWidget: {
    marginTop: 10,
    padding: 10,
    backgroundColor: '#0F172A',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#334155',
  },
  chartTitle: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  chartBarRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 110,
    paddingBottom: 20,
    paddingHorizontal: 8,
  },
  chartCol: {
    alignItems: 'center',
    width: 45,
    marginHorizontal: 4,
  },
  chartBar: {
    width: 16,
    backgroundColor: '#6C63FF',
    borderRadius: 4,
  },
  chartLabel: {
    fontSize: 8,
    color: '#94A3B8',
    marginTop: 4,
  },
  chartVal: {
    fontSize: 9,
    color: '#00E5FF',
    fontWeight: '600',
    marginTop: 1,
  },
});
