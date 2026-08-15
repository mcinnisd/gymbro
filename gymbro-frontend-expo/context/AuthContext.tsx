import React, { createContext, useState, useEffect } from 'react';
import { API_URL as DEFAULT_API_URL } from '../config';

export interface User {
  id: number;
  email: string;
  name?: string;
  age?: number;
  weight?: number;
  height?: number;
  coach_status?: string;
  interview_chat_id?: number | null;
  training_plan?: any;
  goals?: any;
}

export interface AuthContextType {
  authToken: string | null;
  user: User | null;
  loading: boolean;
  apiUrl: string;
  setApiUrl: (url: string) => void;
  login: (email: string, password: string) => Promise<User | null>;
  register: (name: string, email: string, password: string) => Promise<User | null>;
  logout: () => void;
  setUser: React.Dispatch<React.SetStateAction<User | null>>;
  activeChatId: number | null;
  setActiveChatId: (id: number | null) => void;
}

export const AuthContext = createContext<AuthContextType>({
  authToken: null,
  user: null,
  loading: true,
  apiUrl: DEFAULT_API_URL,
  setApiUrl: () => {},
  login: async () => null,
  register: async () => null,
  logout: () => {},
  setUser: () => {},
  activeChatId: null,
  setActiveChatId: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [apiUrl, setApiUrl] = useState<string>(DEFAULT_API_URL);

  const login = async (email: string, password: string): Promise<User | null> => {
    setLoading(true);
    try {
      console.log(`[AuthContext] Connecting to: ${apiUrl}/auth/login`);
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Bypass-Tunnel-Reminder': 'true',
        },
        body: JSON.stringify({ username: email, password }),
      });
      if (response.ok) {
        const data = await response.json();
        setAuthToken(data.access_token);
        setUser(data.user);
        
        // If user has an interview chat ID, set it as active chat
        if (data.user?.interview_chat_id) {
          setActiveChatId(data.user.interview_chat_id);
        }
        setLoading(false);
        return data.user;
      }
    } catch (error) {
      console.error('Login error:', error);
    }
    setLoading(false);
    return null;
  };

  const register = async (name: string, email: string, password: string): Promise<User | null> => {
    setLoading(true);
    try {
      console.log(`[AuthContext] Connecting to: ${apiUrl}/auth/register`);
      const response = await fetch(`${apiUrl}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Bypass-Tunnel-Reminder': 'true',
        },
        body: JSON.stringify({ username: email, email, password, name }),
      });
      if (response.ok) {
        return login(email, password);
      } else {
        const errData = await response.json();
        console.error('Registration failed server response:', errData);
      }
    } catch (error) {
      console.error('Registration error:', error);
    }
    setLoading(false);
    return null;
  };

  const logout = () => {
    setAuthToken(null);
    setUser(null);
    setActiveChatId(null);
  };

  return (
    <AuthContext.Provider
      value={{
        authToken,
        user,
        loading,
        apiUrl,
        setApiUrl,
        login,
        register,
        logout,
        setUser,
        activeChatId,
        setActiveChatId,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
