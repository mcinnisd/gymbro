import React, { useState, useContext } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { AuthContext } from './context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import Colors from '../constants/Colors';

export default function WelcomeScreen() {
  const router = useRouter();
  const { login, register, loading, apiUrl, setApiUrl } = useContext(AuthContext);
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  const handleSubmit = async () => {
    setErrorMsg('');
    if (!email || !password || (isRegister && !name)) {
      setErrorMsg('Please fill in all required fields.');
      return;
    }

    let loggedInUser = null;
    if (isRegister) {
      loggedInUser = await register(name, email, password);
    } else {
      loggedInUser = await login(email, password);
    }

    if (loggedInUser) {
      router.replace('/(tabs)/training');
    } else {
      setErrorMsg(
        isRegister
          ? 'Registration failed. Username/email may already exist or check backend server URL.'
          : 'Login failed. Please check your credentials or backend server URL in settings (gear icon).'
      );
    }
  };

  return (
    <View style={styles.container}>
      {/* Settings toggle button */}
      <TouchableOpacity
        style={styles.settingsToggle}
        onPress={() => setShowSettings(!showSettings)}
        activeOpacity={0.7}
      >
        <Ionicons name={showSettings ? 'close' : 'settings-outline'} size={20} color={Colors.light.text} />
      </TouchableOpacity>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
          {showSettings && (
            <View style={styles.settingsCard}>
              <Text style={styles.settingsHeader}>🔧 Server Configuration</Text>
              <Text style={styles.settingsLabel}>Backend API URL:</Text>
              <TextInput
                style={styles.settingsInput}
                value={apiUrl}
                onChangeText={setApiUrl}
                placeholder="http://192.168.1.xxx:5001"
                placeholderTextColor={Colors.light.subtext}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <Text style={styles.settingsTip}>
                * Match your laptop's local IP or Cloud Run production API URL.
              </Text>
            </View>
          )}

          <View style={styles.brandContainer}>
            <View style={styles.logoCircle}>
              <Ionicons name="fitness-outline" size={44} color={Colors.light.primary} />
            </View>
            <Text style={styles.title}>GYMBRO</Text>
            <Text style={styles.subtitle}>Autonomous AI Athletic Coach & Health Tracking</Text>
          </View>

          <View style={styles.formCard}>
            <Text style={styles.formHeader}>{isRegister ? 'Create Account' : 'Welcome Back'}</Text>

            {errorMsg !== '' && (
              <View style={styles.errorContainer}>
                <Ionicons name="alert-circle" size={18} color="#DC2626" />
                <Text style={styles.errorText}>{errorMsg}</Text>
              </View>
            )}

            {isRegister && (
              <View style={styles.inputWrapper}>
                <Ionicons name="person-outline" size={18} color={Colors.light.subtext} style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="Full Name"
                  placeholderTextColor={Colors.light.subtext}
                  value={name}
                  onChangeText={setName}
                  autoCapitalize="words"
                />
              </View>
            )}

            <View style={styles.inputWrapper}>
              <Ionicons name="mail-outline" size={18} color={Colors.light.subtext} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Email Address"
                placeholderTextColor={Colors.light.subtext}
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
              />
            </View>

            <View style={styles.inputWrapper}>
              <Ionicons name="lock-closed-outline" size={18} color={Colors.light.subtext} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Password"
                placeholderTextColor={Colors.light.subtext}
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                autoCapitalize="none"
              />
            </View>

            <TouchableOpacity style={styles.submitBtn} onPress={handleSubmit} disabled={loading}>
              <LinearGradient
                colors={[Colors.light.primary, '#1D4ED8']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.gradientBtn}
              >
                {loading ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.submitText}>{isRegister ? 'Sign Up' : 'Log In'}</Text>
                )}
              </LinearGradient>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.toggleBtn}
              onPress={() => {
                setIsRegister(!isRegister);
                setErrorMsg('');
              }}
            >
              <Text style={styles.toggleText}>
                {isRegister ? 'Already have an account? Log In' : "Don't have an account? Sign Up"}
              </Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  settingsToggle: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 54 : 30,
    right: 20,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.light.card,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.light.border,
    zIndex: 9999,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  settingsCard: {
    backgroundColor: Colors.light.card,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginBottom: 20,
    marginTop: 40,
  },
  settingsHeader: {
    fontSize: 14,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginBottom: 8,
  },
  settingsLabel: {
    fontSize: 12,
    color: Colors.light.subtext,
    marginBottom: 4,
  },
  settingsInput: {
    backgroundColor: Colors.light.background,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 8,
    height: 40,
    paddingHorizontal: 12,
    color: Colors.light.text,
    fontSize: 14,
  },
  settingsTip: {
    fontSize: 11,
    color: Colors.light.subtext,
    marginTop: 6,
  },
  brandContainer: {
    alignItems: 'center',
    marginBottom: 32,
  },
  logoCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(37, 99, 235, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: 'rgba(37, 99, 235, 0.2)',
  },
  title: {
    fontSize: 34,
    fontWeight: '900',
    color: Colors.light.text,
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 13,
    color: Colors.light.subtext,
    marginTop: 4,
    textAlign: 'center',
  },
  formCard: {
    backgroundColor: Colors.light.card,
    borderRadius: 20,
    padding: 24,
    borderWidth: 1,
    borderColor: Colors.light.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 3,
  },
  formHeader: {
    fontSize: 22,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginBottom: 20,
    textAlign: 'center',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FCA5A5',
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
  },
  errorText: {
    color: '#DC2626',
    fontSize: 13,
    marginLeft: 8,
    flex: 1,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
    borderRadius: 10,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: Colors.light.border,
    paddingHorizontal: 12,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    height: 48,
    color: Colors.light.text,
    fontSize: 15,
  },
  submitBtn: {
    borderRadius: 10,
    marginTop: 8,
    overflow: 'hidden',
  },
  gradientBtn: {
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  toggleBtn: {
    marginTop: 16,
    alignItems: 'center',
  },
  toggleText: {
    color: Colors.light.primary,
    fontSize: 14,
    fontWeight: '600',
  },
});
