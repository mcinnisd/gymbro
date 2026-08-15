import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from '../context/AuthContext';
import CoachDrawer from '../components/CoachDrawer';
import { Colors } from '../constants/Colors';

export default function RootLayout() {
  return (
    <AuthProvider>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            headerStyle: {
              backgroundColor: Colors.light.card,
            },
            headerTintColor: Colors.light.text,
            headerTitleStyle: {
              fontWeight: 'bold',
            },
            contentStyle: {
              backgroundColor: Colors.light.background,
            },
          }}
        >
          {/* Main Screens */}
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        </Stack>
        
        {/* Persistent contextual Coach chatbot overlay */}
        <CoachDrawer />
      </SafeAreaProvider>
    </AuthProvider>
  );
}

