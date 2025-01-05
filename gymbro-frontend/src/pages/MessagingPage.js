// src/pages/MessagingPage.js
import React, { useState } from 'react';
import { Box, Typography, TextField, Button, Paper, List, ListItem, ListItemText } from '@mui/material';

function MessagingPage() {
  const [messages, setMessages] = useState([]);
  const [userInput, setUserInput] = useState('');

  const handleSend = async () => {
    if (!userInput.trim()) return;

    // Add user message to the list
    const newMessage = { sender: 'You', text: userInput };
    setMessages((prev) => [...prev, newMessage]);
    setUserInput('');

    // Call your Flask chatbot endpoint
    const response = await fetch('/chatbot/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userInput }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      setMessages((prev) => [...prev, { sender: 'Bot', text: `Error: ${errorText}` }]);
      return;
    }

    const data = await response.json();
    setMessages((prev) => [...prev, { sender: 'Bot', text: data.reply }]);
  };

  return (
    <Box sx={{ padding: 3 }}>
      <Typography variant="h4" gutterBottom>
        Chatbot
      </Typography>
      <Paper sx={{ padding: 2, height: '60vh', overflowY: 'auto', marginBottom: 2 }}>
        <List>
          {messages.map((msg, idx) => (
            <ListItem key={idx}>
              <ListItemText
                primary={msg.sender}
                secondary={msg.text}
                sx={{
                  textAlign: msg.sender === 'You' ? 'right' : 'left',
                }}
              />
            </ListItem>
          ))}
        </List>
      </Paper>
      <Box sx={{ display: 'flex' }}>
        <TextField
          label="Type your message"
          variant="outlined"
          fullWidth
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              handleSend();
            }
          }}
        />
        <Button variant="contained" color="primary" onClick={handleSend} sx={{ ml: 2 }}>
          Send
        </Button>
      </Box>
    </Box>
  );
}

export default MessagingPage;