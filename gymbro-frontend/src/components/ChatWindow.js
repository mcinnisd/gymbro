// src/components/ChatWindow.js

import React, { useEffect, useState, useRef, useContext } from 'react';
import { Box, Typography, Paper } from '@mui/material';
import MessageInput from './MessageInput';
import { AuthContext } from '../context/AuthContext';

function ChatWindow({ chatId, title }) {
  const { authToken } = useContext(AuthContext);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const fetchChat = async () => {
      console.log('ChatWindow: Fetching chat:', chatId, 'with token:', authToken);
      setLoading(true);
      if (!authToken) {
        console.error("No auth token found. Redirecting to login.");
        // Optionally, use navigate('/login') if accessible here
        return;
      }
      try {
        const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats/${chatId}`, {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${authToken}` },
        });

        console.log('ChatWindow: Fetch chat response status:', response.status);

        if (response.ok) {
          const data = await response.json();
          console.log('ChatWindow: Fetched chat messages:', data.chat.messages);
          setMessages(data.chat.messages);
        } else {
          const errorData = await response.json();
          console.error("ChatWindow: Error fetching chat:", errorData);
          // Optionally, handle redirection or display an error message
        }
      } catch (error) {
        console.error("ChatWindow: Error fetching chat:", error);
      }
      setLoading(false);
    };

    fetchChat();
  }, [chatId, authToken]);

  useEffect(() => {
    // Scroll to the bottom when messages update
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSendMessage = async (messageContent) => {
    console.log('ChatWindow: Sending message:', messageContent);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ message: messageContent }),
      });

      console.log('ChatWindow: Send message response status:', response.status);

      if (response.ok) {
        const data = await response.json();
        console.log('ChatWindow: Received bot reply:', data.reply);
        // Append the user's message and the bot's reply
        setMessages([
          ...messages,
          { sender: 'user', content: messageContent, timestamp: new Date().toISOString() },
          { sender: 'bot', content: data.reply, timestamp: new Date().toISOString() }
        ]);
      } else {
        const errorData = await response.json();
        console.error("ChatWindow: Error sending message:", errorData);
        // Optionally, handle error in UI
      }
    } catch (error) {
      console.error("ChatWindow: Error sending message:", error);
      // Optionally, handle error in UI
    }
  };

  return (
    <Box display="flex" flexDirection="column" height="80vh">
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      <Paper variant="outlined" sx={{ flexGrow: 1, padding: 2, overflowY: 'auto', marginBottom: 2 }}>
        {loading ? (
          <Typography variant="body1">Loading...</Typography>
        ) : messages.length > 0 ? (
          messages.map((msg, index) => (
            <Box key={index} mb={2} textAlign={msg.sender === 'user' ? 'right' : 'left'}>
              <Typography variant="subtitle2" color="textSecondary">
                {msg.sender === 'user' ? 'You' : 'GymBro Bot'}
              </Typography>
              <Typography variant="body1">{msg.content}</Typography>
            </Box>
          ))
        ) : (
          <Typography variant="body1">No messages yet.</Typography>
        )}
        <div ref={messagesEndRef} />
      </Paper>
      <MessageInput onSend={handleSendMessage} />
    </Box>
  );
}

export default ChatWindow;