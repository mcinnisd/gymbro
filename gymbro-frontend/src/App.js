// src/App.js

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ChatsPage from './pages/ChatsPage'; // Updated import
import PrivateRoute from './components/PrivateRoute';
import Navbar from './components/Navbar';

function App() {
  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <DashboardPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/chats" // Updated route path
          element={
            <PrivateRoute>
              <ChatsPage />
            </PrivateRoute>
          }
        />
        {/* Optionally, redirect /messaging to /chats if necessary */}
        {/* <Route
          path="/messaging"
          element={
            <PrivateRoute>
              <ChatsPage />
            </PrivateRoute>
          }
        /> */}
      </Routes>
    </Router>
  );
}

export default App;