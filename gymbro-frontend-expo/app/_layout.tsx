import React, { useEffect, useContext } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider, AuthContext } from '../context/AuthContext';
import CoachDrawer from '../components/CoachDrawer';
import { Colors } from '../constants/Colors';

function NavigationGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const segments = useSegments();
  const { authToken, user, loading } = useContext(AuthContext);

  useEffect(() => {
    if (loading) return;

    const firstSegment = segments[0];
    const isRootOrWelcome = !firstSegment || firstSegment === 'index';
    const inOnboarding = firstSegment === '(onboarding)';
    const inTabs = firstSegment === '(tabs)';

    // If authenticated:
    if (authToken && user) {
      const isCoachActive = user.coach_status === 'active';

      if (!isCoachActive && !inOnboarding) {
        console.log('[NavigationGate] Redirecting un-onboarded athlete to /(onboarding)');
        router.replace('/(onboarding)');
      } else if (isCoachActive && (inOnboarding || isRootOrWelcome)) {
        console.log('[NavigationGate] Active athlete at root/onboarding -> redirecting to /(tabs)/training');
        router.replace('/(tabs)/training');
      }
    }
  }, [authToken, user, segments, loading]);

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        <NavigationGate>
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
            <Stack.Screen name="(onboarding)" options={{ headerShown: false }} />
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          </Stack>
        </NavigationGate>

        {/* Persistent contextual Coach chatbot overlay */}
        <CoachDrawer />
      </SafeAreaProvider>
    </AuthProvider>
  );
}
