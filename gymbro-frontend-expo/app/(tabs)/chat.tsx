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
import { AuthContext } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { MarkdownText } from '../components/MarkdownText';
import Colors from '../../constants/Colors';

interface Message {
  sender: 'user' | 'bot' | 'system';
  content: string;
  timestamp: string;
  ui_payload?: any;
}

export default function ChatScreen() {
  const { authToken, user, apiUrl } = useContext(AuthContext);
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
          // Create initial main coach chat
          createNewChatSession('Coach Consultation');
        }
      }
    } catch (err) {
      console.error('Error initializing chat session:', err);
    }
    setLoading(false);
  };

  const createNewChatSession = async (title: string = 'Coach Consultation') => {
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
        setActiveChatId(data.chat_id);
        setMessages([
          {
            sender: 'bot',
            content: "👋 Hello! I'm your AI Coach. Ask me about your recent runs, HRV trends, sleep recovery, or request a custom training plan!",
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
              content: "👋 Hello! I'm your AI Coach. Ask me about your recent runs, HRV trends, sleep recovery, or request a custom training plan!",
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

  const handleSendMessage = () => {
    handleSendMessageText(inputText);
  };

  const handleQuickPrompt = (promptText: string) => {
    handleSendMessageText(promptText);
  };

  const handleSendMessageText = async (textToSend: string) => {
    if (!textToSend.trim()) return;

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
    setStatusMessage('⚡ Coach is analyzing activities & biometrics...');

    try {
      const response = await fetch(`${apiUrl}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ message: textToSend }),
      });

      if (!response.ok) throw new Error('Failed to send message');

      const contentType = response.headers.get('content-type');

      // JSON response fallback
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        const replyText = data.message || data.response || data.content || 'I have analyzed your data.';
        setMessages((prev) => [
          ...prev,
          {
            sender: 'bot',
            content: replyText,
            timestamp: new Date().toISOString(),
            ui_payload: data.ui_payload,
          },
        ]);
        setStatusMessage('');
        return;
      }

      // Stream parsing
      if (response.body && typeof response.body.getReader === 'function') {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullAnswer = '';

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

                if (data.status && data.status !== 'Complete') {
                  setStatusMessage(data.status);
                }
                if (data.token) {
                  fullAnswer += data.token;
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last && last.sender === 'bot') {
                      last.content = fullAnswer;
                      updated[updated.length - 1] = { ...last };
                    } else {
                      updated.push({
                        sender: 'bot',
                        content: fullAnswer,
                        timestamp: new Date().toISOString(),
                      });
                    }
                    return updated;
                  });
                }
                if (data.done) {
                  setStatusMessage('');
                }
              } catch (e) {}
            }
          }
        }
      } else {
        // Text fallback
        const text = await response.text();
        let fullAnswer = '';
        const lines = text.split('\n\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.token) fullAnswer += data.token;
            } catch (e) {}
          }
        }

        const reply = fullAnswer.trim() || 'I have analyzed your training data and metrics.';
        setMessages((prev) => [
          ...prev,
          {
            sender: 'bot',
            content: reply,
            timestamp: new Date().toISOString(),
          },
        ]);
        setStatusMessage('');
      }
    } catch (err) {
      console.error('Error sending chat message:', err);
      setStatusMessage('');
      Alert.alert('Connection Error', 'Failed to reach coach backend service.');
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {/* Top Session Bar */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <View style={styles.avatarCircle}>
            <Ionicons name="fitness" size={20} color="#FFFFFF" />
          </View>
          <View>
            <Text style={styles.coachName}>Coach AI</Text>
            <Text style={styles.coachStatusText}>Active • RAG Biometrics & Activity Intelligence</Text>
          </View>
        </View>
        <TouchableOpacity style={styles.newChatBtn} onPress={() => createNewChatSession('New Chat')}>
          <Ionicons name="add" size={18} color={Colors.light.primary} />
          <Text style={styles.newChatText}>New Chat</Text>
        </TouchableOpacity>
      </View>

      {/* Messages Scroll Area */}
      <ScrollView ref={scrollViewRef} style={styles.messageList} contentContainerStyle={styles.messageContent}>
        {messages.map((msg, index) => {
          const isUser = msg.sender === 'user';
          return (
            <View key={index} style={[styles.msgRow, isUser ? styles.msgRowUser : styles.msgRowBot]}>
              {!isUser && (
                <View style={styles.botIcon}>
                  <Ionicons name="sparkles" size={14} color={Colors.light.primary} />
                </View>
              )}
              <View style={[styles.msgBubble, isUser ? styles.msgBubbleUser : styles.msgBubbleBot]}>
                <MarkdownText content={msg.content} isUser={isUser} />
              </View>
            </View>
          );
        })}

        {statusMessage !== '' && (
          <View style={styles.statusRow}>
            <ActivityIndicator size="small" color={Colors.light.primary} style={{ marginRight: 8 }} />
            <Text style={styles.statusText}>{statusMessage}</Text>
          </View>
        )}
      </ScrollView>

      {/* Quick Prompts Bar */}
      <View style={styles.quickPromptsContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {[
            '🏃 How were my runs this week?',
            '❤️ Show my HRV & sleep trends',
            '⚡ Generate 4-week marathon plan',
            '📊 Summarize weekly volume',
          ].map((prompt, i) => (
            <TouchableOpacity key={i} style={styles.quickPill} onPress={() => handleQuickPrompt(prompt.replace(/^[^\s]+\s/, ''))}>
              <Text style={styles.quickPillText}>{prompt}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Input Bar */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.textInput}
          placeholder="Ask Coach AI about workouts, runs, recovery..."
          placeholderTextColor={Colors.light.subtext}
          value={inputText}
          onChangeText={setInputText}
          multiline
        />
        <TouchableOpacity
          style={[styles.sendBtn, !inputText.trim() && styles.sendBtnDisabled]}
          onPress={handleSendMessage}
          disabled={!inputText.trim()}
        >
          <LinearGradient
            colors={[Colors.light.primary, '#1D4ED8']}
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
    borderBottomColor: Colors.light.border,
  },
  topBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatarCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.light.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  coachName: {
    fontSize: 15,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  coachStatusText: {
    fontSize: 11,
    color: Colors.light.secondary,
    fontWeight: '600',
  },
  newChatBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
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
    marginBottom: 14,
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
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(37, 99, 235, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
    marginTop: 4,
  },
  msgBubble: {
    borderRadius: 16,
    padding: 14,
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
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: Colors.light.card,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginTop: 8,
  },
  statusText: {
    fontSize: 12,
    color: Colors.light.primary,
    fontWeight: '600',
  },
  quickPromptsContainer: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: Colors.light.card,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
  },
  quickPill: {
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
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
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: Colors.light.card,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
  },
  textInput: {
    flex: 1,
    maxHeight: 100,
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 14,
    color: Colors.light.text,
    marginRight: 8,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    overflow: 'hidden',
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  sendGradient: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
