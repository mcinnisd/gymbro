// src/context/AuthContext.js
import React, { createContext, useState, useEffect } from 'react';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('token') || null);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('darkMode') === 'true');

  useEffect(() => {
    if (authToken) {
      localStorage.setItem('token', authToken);
    } else {
      localStorage.removeItem('token');
    }
  }, [authToken]);

  useEffect(() => {
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode]);

  return (
    <AuthContext.Provider value={{ authToken, setAuthToken, darkMode, setDarkMode }}>
      {children}
    </AuthContext.Provider>
  );
};