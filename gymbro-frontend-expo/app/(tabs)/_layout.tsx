import React from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Platform } from 'react-native';
import { Colors } from '../../constants/Colors';

export default function TabsLayout() {
  return (
    <Tabs
      initialRouteName="today"
      screenOptions={{
        tabBarActiveTintColor: Colors.light.primary,
        tabBarInactiveTintColor: Colors.light.mutedText,
        tabBarStyle: {
          backgroundColor: Colors.light.card,
          borderTopColor: Colors.light.borderSubtle,
          borderTopWidth: 1,
          height: Platform.OS === 'ios' ? 88 : 68,
          paddingBottom: Platform.OS === 'ios' ? 28 : 12,
          paddingTop: 8,
          elevation: 8,
          shadowColor: Colors.light.shadowColor,
          shadowOffset: { width: 0, height: -4 },
          shadowOpacity: 0.03,
          shadowRadius: 10,
        },
        tabBarLabelStyle: {
          fontWeight: '600',
          fontSize: 11,
          marginTop: 2,
        },
        headerStyle: {
          backgroundColor: Colors.light.background,
          borderBottomColor: Colors.light.borderSubtle,
          borderBottomWidth: 1,
          elevation: 0,
          shadowOpacity: 0,
        },
        headerTintColor: Colors.light.text,
        headerTitleStyle: {
          fontWeight: '700',
          fontSize: 18,
          letterSpacing: -0.3,
        },
      }}
    >
      <Tabs.Screen
        name="today"
        options={{
          title: 'Today',
          tabBarLabel: 'Today',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'sunny' : 'sunny-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="training"
        options={{
          title: 'Training',
          tabBarLabel: 'Training',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'barbell' : 'barbell-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="coach"
        options={{
          title: 'Coach',
          tabBarLabel: 'Coach',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'chatbubbles' : 'chatbubbles-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="nutrition"
        options={{
          title: 'Nutrition',
          tabBarLabel: 'Nutrition',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'nutrition' : 'nutrition-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="analytics"
        options={{
          title: 'Analytics',
          tabBarLabel: 'Analytics',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'analytics' : 'analytics-outline'} size={22} color={color} />
          ),
        }}
      />
      {/* Recovery kept as a secondary screen (journal / deep biometrics) — not a primary hub */}
      <Tabs.Screen
        name="recovery"
        options={{
          href: null,
          title: 'Recovery & Journal',
        }}
      />
    </Tabs>
  );
}
