import Constants from 'expo-constants';
import { Platform } from 'react-native';

// Supabase details
export const SUPABASE_URL = 'https://frsoqqglyiepgoudxnyu.supabase.co';
export const SUPABASE_KEY = 'sb_publishable_t1FuptaCgcr_N8qSqzTRpg_feSa02cM';

// Local Flask API Server Address
// Automatically resolves host computer IP when running on Expo Go/Physical device or Web
const getBackendUrl = () => {
  // 1. Web environment
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined' && window.location) {
      const hostname = window.location.hostname;
      if (
        hostname &&
        hostname !== 'localhost' &&
        hostname !== '127.0.0.1' &&
        !hostname.includes('exp.direct') &&
        !hostname.includes('ngrok')
      ) {
        return `http://${hostname}:5001`;
      }
    }
    return 'http://127.0.0.1:5001';
  }

  // 2. Native environment (Expo Go / physical device / emulator)
  const manifest = Constants.expoConfig || {};
  const hostUri = (manifest as any).hostUri || (Constants as any).manifest?.debuggerHost || '';
  if (hostUri) {
    const host = hostUri.split(':')[0];
    // Only use host if it looks like a local IP/hostname, not a remote tunnel domain
    if (
      host &&
      !host.includes('exp.direct') &&
      !host.includes('ngrok') &&
      !host.includes('tunnel')
    ) {
      return `http://${host}:5001`;
    }
  }
  return 'http://127.0.0.1:5001';
};

export const API_URL = getBackendUrl();
console.log('[Gymbro Config] Supabase URL:', SUPABASE_URL);
console.log('[Gymbro Config] Backend API URL:', API_URL);
