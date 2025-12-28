import React, { useEffect, useState, useRef, useContext } from 'react';
import { Box, Typography, Paper } from '@mui/material';
import MessageInput from './MessageInput';
import { AuthContext } from '../context/AuthContext';
import ReactMarkdown from 'react-markdown';
import ChartMessage from './ChartMessage';
import ProposalCard from './ChatWidgets/ProposalCard';
import GlassPaper from '../components/GlassPaper';

function ChatWindow({ chatId, title }) {
  const { authToken } = useContext(AuthContext);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const fetchChat = async () => {
      console.log('ChatWindow: Fetching chat:', chatId, 'with token:', authToken);
      setLoading(true);
      if (!authToken) {
        console.error("No auth token found. Redirecting to login.");
        return;
      }
      try {
        const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats/${chatId}`, {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${authToken}` },
        });

        if (response.ok) {
          const data = await response.json();
          setMessages(data.chat.messages);
        } else {
          console.error("ChatWindow: Error fetching chat");
        }
      } catch (error) {
        console.error("ChatWindow: Error fetching chat:", error);
      }
      setLoading(false);
    };

    fetchChat();
  }, [chatId, authToken]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, statusMessage]);

  const handleApproveProposal = async (proposal) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats/${chatId}/actions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(proposal),
      });

      if (response.ok) {
        const result = await response.json();
        // Add system message or update UI
        setMessages(prev => [...prev, {
          sender: 'system',
          content: `Action completed: ${result.message}`,
          timestamp: new Date().toISOString()
        }]);
      } else {
        const err = await response.json();
        alert(`Error: ${err.message}`);
      }
    } catch (error) {
      console.error("Error approving proposal:", error);
      alert("Failed to execute action.");
    }
  };

  const handleDenyProposal = () => {
    setMessages(prev => [...prev, {
      sender: 'system',
      content: "Proposal denied.",
      timestamp: new Date().toISOString()
    }]);
  };

  const handleSendMessage = async (messageContent) => {
    // Optimistically add user message
    const userMsg = { sender: 'user', content: messageContent, timestamp: new Date().toISOString() };
    const botMsgPlaceholder = { sender: 'bot', content: '', timestamp: new Date().toISOString() };

    setMessages(prev => [...prev, userMsg, botMsgPlaceholder]);
    setStatusMessage("Thinking...");

    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ message: messageContent }),
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const contentType = response.headers.get('content-type');

      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        setMessages(prev => {
          const newMessages = [...prev];
          const lastMsgIndex = newMessages.length - 1;
          newMessages[lastMsgIndex] = {
            sender: 'bot',
            content: data.message || data.content || '',
            timestamp: new Date().toISOString(),
            is_interview_complete: data.is_complete
          };
          return newMessages;
        });
        setStatusMessage("");
        return;
      }

      // Handle Stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.status) {
                setStatusMessage(data.status);
              }

              if (data.token) {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsgIndex = newMessages.length - 1;
                  const lastMsg = { ...newMessages[lastMsgIndex] };
                  lastMsg.content += data.token;
                  newMessages[lastMsgIndex] = lastMsg;
                  return newMessages;
                });
              }

              if (data.proposal) {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsgIndex = newMessages.length - 1;
                  const lastMsg = { ...newMessages[lastMsgIndex] };
                  lastMsg.proposal = data.proposal;
                  if (!lastMsg.content) {
                    lastMsg.content = data.proposal.reasoning || "I have a proposal:";
                  }
                  newMessages[lastMsgIndex] = lastMsg;
                  return newMessages;
                });
              }

              if (data.chart) {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsgIndex = newMessages.length - 1;
                  const lastMsg = { ...newMessages[lastMsgIndex] };
                  lastMsg.chart_data = data.chart;
                  newMessages[lastMsgIndex] = lastMsg;
                  return newMessages;
                });
              }

              if (data.done) {
                setStatusMessage("");
              }

              if (data.error) {
                console.error("Stream error:", data.error);
                setStatusMessage("Error: " + data.error);
              }
            } catch (e) {
              console.error("Error parsing SSE data:", e);
            }
          }
        }
      }

    } catch (error) {
      console.error("ChatWindow: Error sending message:", error);
      setStatusMessage("Error sending message.");
    }
  };

  return (
    <Box display="flex" flexDirection="column" height="80vh">
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      <GlassPaper variant="outlined" sx={{ flexGrow: 1, padding: 2, overflowY: 'auto', marginBottom: 2 }}>
        {loading ? (
          <Typography variant="body1">Loading...</Typography>
        ) : messages.length > 0 ? (
          messages.map((msg, index) => (
            <Box key={index} mb={2} display="flex" justifyContent={msg.sender === 'user' ? 'flex-end' : 'flex-start'}>
              <Paper
                elevation={1}
                sx={{
                  padding: 2,
                  maxWidth: '70%',
                  bgcolor: msg.sender === 'user' ? 'primary.main' : 'background.paper',
                  color: msg.sender === 'user' ? 'primary.contrastText' : 'text.primary',
                  borderRadius: 2
                }}
              >
                <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ color: msg.sender === 'user' ? 'rgba(255,255,255,0.7)' : 'text.secondary' }}>
                  {msg.sender === 'user' ? 'You' : msg.sender === 'system' ? 'System' : 'Coach'}
                </Typography>
                <Box sx={{ '& p': { margin: 0 } }}>
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </Box>
                {msg.chart_data && <ChartMessage chartData={msg.chart_data} />}
                {msg.proposal && (
                  <ProposalCard
                    proposal={msg.proposal}
                    onApprove={handleApproveProposal}
                    onDeny={handleDenyProposal}
                  />
                )}
              </Paper>
            </Box>
          ))
        ) : (
          <Typography variant="body1">No messages yet.</Typography>
        )}

        {statusMessage && (
          <Box mb={2} display="flex" justifyContent="flex-start">
            <Typography variant="caption" color="textSecondary" sx={{ fontStyle: 'italic', ml: 2 }}>
              {statusMessage}
            </Typography>
          </Box>
        )}

        <div ref={messagesEndRef} />
      </GlassPaper>
      <MessageInput onSend={handleSendMessage} />
    </Box>
  );
}

export default ChatWindow;