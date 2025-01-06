// src/components/ChatList.js

import React from 'react';
import { List, ListItemButton, ListItemText } from '@mui/material';

function ChatList({ chats, selectedChatId, onSelect }) {
  return (
    <List component="nav">
      {chats.map((chat) => (
        <ListItemButton
          key={chat.id}
          selected={selectedChatId === chat.id}
          onClick={() => onSelect(chat.id, chat.title)}
        >
          <ListItemText primary={chat.title} />
        </ListItemButton>
      ))}
    </List>
  );
}

export default ChatList;