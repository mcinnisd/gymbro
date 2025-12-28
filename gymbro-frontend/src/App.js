// src/App.js

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ChatsPage from './pages/ChatsPage';
import CoachPage from './pages/CoachPage';
import OnboardingPage from './pages/OnboardingPage';
import PrivateRoute from './components/PrivateRoute';
import Navbar from './components/Navbar';
import ActivityDetailsPage from './pages/ActivityDetailsPage';
import SleepDetailsPage from './pages/SleepDetailsPage';
import CalendarPage from './pages/CalendarPage'; // Added import
import ProfilePage from './pages/ProfilePage';
import { AuthProvider } from './context/AuthContext';
import { SettingsProvider } from './context/SettingsContext';
import Layout from './components/Layout'; // Import Layout

function App() {
  return (
    <SettingsProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/onboarding" element={<PrivateRoute><OnboardingPage /></PrivateRoute>} />
            <Route path="/dashboard" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
            <Route path="/coach" element={<PrivateRoute><CoachPage /></PrivateRoute>} />
            <Route path="/chats" element={<PrivateRoute><ChatsPage /></PrivateRoute>} />
            <Route path="/chats/:chatId" element={<PrivateRoute><ChatsPage /></PrivateRoute>} />
            <Route path="/activities/:activityId" element={<PrivateRoute><ActivityDetailsPage /></PrivateRoute>} />
            <Route path="/sleep/:date" element={<PrivateRoute><SleepDetailsPage /></PrivateRoute>} />
            <Route path="/calendar" element={<PrivateRoute><CalendarPage /></PrivateRoute>} />
            <Route path="/profile" element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="*" element={<Navigate to="/dashboard" />} />
          </Routes>
        </Layout>
      </Router>
    </SettingsProvider>
  );
}

export default App;