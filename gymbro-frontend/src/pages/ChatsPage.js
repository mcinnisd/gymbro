// src/pages/ChatsPage.js

import React, { useEffect, useState, useContext } from 'react';
import { Container, Grid, Box, Typography, Button, Dialog, DialogTitle, DialogContent, TextField, DialogActions } from '@mui/material';
import ChatList from '../components/ChatList';
import ChatWindow from '../components/ChatWindow';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

function ChatsPage() {
  const { authToken } = useContext(AuthContext);
  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [selectedChatTitle, setSelectedChatTitle] = useState('');
  const [openDialog, setOpenDialog] = useState(false);
  const [newChatTitle, setNewChatTitle] = useState('');
  const navigate = useNavigate();

  // Fetch chats on component mount
  useEffect(() => {
    const fetchChats = async () => {
      console.log('ChatsPage: Fetching chats with token:', authToken);
      if (!authToken) {
        console.error("No auth token found. Redirecting to login.");
        navigate('/');
        return;
      }
      try {
        const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats`, {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${authToken}` },
        });

        console.log('ChatsPage: Fetch chats response status:', response.status);

        if (response.ok) {
          const data = await response.json();
          console.log('ChatsPage: Fetched chats:', data.chats);
          setChats(data.chats);
          if (data.chats.length > 0) {
            setSelectedChatId(data.chats[0].id);
            setSelectedChatTitle(data.chats[0].title);
          }
        } else {
          const errorData = await response.json();
          console.error("ChatsPage: Error fetching chats:", errorData);
          navigate('/');
        }
      } catch (error) {
        console.error("ChatsPage: Error fetching chats:", error);
      }
    };

    fetchChats();
  }, [authToken, navigate]);

  const handleChatSelect = (chatId, title) => {
    setSelectedChatId(chatId);
    setSelectedChatTitle(title);
  };

  const handleOpenDialog = () => {
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setNewChatTitle('');
  };

  const handleCreateChat = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ title: newChatTitle }),
      });

      if (response.ok) {
        const data = await response.json();
        const newChat = {
          id: data.chat_id,
          title: newChatTitle,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setChats([...chats, newChat]);
        setSelectedChatId(newChat.id);
        setSelectedChatTitle(newChat.title);
        handleCloseDialog();
      } else {
        // Handle error
        const errorData = await response.json();
        console.error("Error creating chat:", errorData);
        // Optionally, display an error message to the user
      }
    } catch (error) {
      console.error("Error creating chat:", error);
      // Optionally, display an error message to the user
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Grid container spacing={2}>
        {/* Chat List */}
        <Grid item xs={3}>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Chats</Typography>
            <Button variant="contained" size="small" onClick={handleOpenDialog}>
              New Chat
            </Button>
          </Box>
          <ChatList chats={chats} selectedChatId={selectedChatId} onSelect={handleChatSelect} />
        </Grid>

        {/* Chat Window */}
        <Grid item xs={9}>
          {selectedChatId ? (
            <ChatWindow chatId={selectedChatId} title={selectedChatTitle} />
          ) : (
            <Typography variant="h6">No chat selected.</Typography>
          )}
        </Grid>
      </Grid>

      {/* New Chat Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog}>
        <DialogTitle>Create New Chat</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Chat Title"
            type="text"
            fullWidth
            variant="standard"
            value={newChatTitle}
            onChange={(e) => setNewChatTitle(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleCreateChat} disabled={!newChatTitle.trim()}>Create</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}

export default ChatsPage;