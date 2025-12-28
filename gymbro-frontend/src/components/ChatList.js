import React from 'react';
import { List, ListItemButton, ListItemText, IconButton } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';

function ChatList({ chats, selectedChatId, onSelect, onDelete }) {
  return (
    <List component="nav">
      {chats.map((chat) => (
        <ListItemButton
          key={chat.id}
          selected={selectedChatId === chat.id}
          onClick={() => onSelect(chat.id, chat.title)}
        >
          <ListItemText primary={chat.title} />
          <IconButton
            edge="end"
            aria-label="delete"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(chat.id);
            }}
            size="small"
            sx={{ ml: 1, color: 'text.secondary', '&:hover': { color: 'error.main' } }}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </ListItemButton>
      ))}
    </List>
  );
}

export default ChatList;