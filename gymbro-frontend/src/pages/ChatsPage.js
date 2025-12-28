// src/pages/ChatsPage.js

import React, { useEffect, useState, useContext } from 'react';
import { Container, Grid, Box, Typography, Button, Dialog, DialogTitle, DialogContent, TextField, DialogActions } from '@mui/material';
import ChatList from '../components/ChatList';
import ChatWindow from '../components/ChatWindow';
import { useNavigate, useParams } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

function ChatsPage() {
  const { authToken } = useContext(AuthContext);
  const { chatId } = useParams();
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
          if (chatId) {
            const selected = data.chats.find(c => String(c.id) === String(chatId));
            if (selected) {
              setSelectedChatId(selected.id);
              setSelectedChatTitle(selected.title);
            } else if (data.chats.length > 0) {
              setSelectedChatId(data.chats[0].id);
              setSelectedChatTitle(data.chats[0].title);
            }
          } else if (data.chats.length > 0) {
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
  }, [authToken, navigate, chatId]);

  const handleChatSelect = (chatId, title) => {
    setSelectedChatId(chatId);
    setSelectedChatTitle(title);
    navigate(`/chats/${chatId}`);
  };

  const handleOpenDialog = () => {
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setNewChatTitle('');
  };

  const handleCreateChat = async () => {
    console.log('ChatsPage: Creating chat with title:', newChatTitle);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ title: newChatTitle }),
      });

      console.log('ChatsPage: Create chat response status:', response.status);

      if (response.ok) {
        const data = await response.json();
        console.log('ChatsPage: Chat created:', data);
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
        const errorData = await response.json();
        console.error("ChatsPage: Error creating chat:", errorData);
        // Optionally, display an error message to the user
      }
    } catch (error) {
      console.error("ChatsPage: Error creating chat:", error);
      // Optionally, display an error message to the user
    }
  };

  const handleDeleteChat = async (chatId) => {
    console.log("handleDeleteChat called for:", chatId);
    if (!window.confirm("Are you sure you want to delete this chat?")) {
      console.log("Delete cancelled by user.");
      return;
    }

    try {
      console.log("Sending DELETE request...");
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/chats/${chatId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` },
      });
      console.log("DELETE response status:", response.status);

      if (response.ok) {
        setChats(chats.filter(c => c.id !== chatId));
        if (selectedChatId === chatId) {
          setSelectedChatId(null);
          setSelectedChatTitle('');
        }
      } else {
        const err = await response.json();
        console.error("Failed to delete chat:", err);
        alert("Failed to delete chat: " + (err.error || "Unknown error"));
      }
    } catch (error) {
      console.error("Error deleting chat:", error);
      alert("Error deleting chat.");
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
          <ChatList chats={chats} selectedChatId={selectedChatId} onSelect={handleChatSelect} onDelete={handleDeleteChat} />
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