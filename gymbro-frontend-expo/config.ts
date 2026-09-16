import Constants from 'expo-constants';
import { Platform } from 'react-native';
import tunnelConfig from './tunnel.json';

// Supabase details
export const SUPABASE_URL = 'https://frsoqqglyiepgoudxnyu.supabase.co';
export const SUPABASE_KEY = 'sb_publishable_t1FuptaCgcr_N8qSqzTRpg_feSa02cM';

// Active Backend URL configured by scripts/dev.sh or fallback
export const CONFIGURED_API_URL = (tunnelConfig as any)?.tunnel_url || '';

// Local Flask API Server Address
const getBackendUrl = () => {
  // 1. Web environment (Desktop Browser)
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined' && window.location) {
      const hostname = window.location.hostname;
      if (
        hostname &&
        hostname !== 'localhost' &&
        hostname !== '127.0.0.1' &&
        !hostname.includes('exp.direct') &&
        !hostname.includes('ngrok') &&
        !hostname.includes('loca.lt')
      ) {
        return `http://${hostname}:5001`;
      }
    }
    return 'http://127.0.0.1:5001';
  }

  // 2. Native environment (Expo Go / physical device / emulator)
  // If dev.sh configured a tunnel or LAN URL in tunnel.json, use it directly
  if (CONFIGURED_API_URL) {
    return CONFIGURED_API_URL;
  }

  const manifest = Constants.expoConfig || {};
  const hostUri = (manifest as any).hostUri || (Constants as any).manifest?.debuggerHost || '';
  if (hostUri) {
    const host = hostUri.split(':')[0];
    if (host && host !== 'localhost' && host !== '127.0.0.1' && !host.includes('exp.direct') && !host.includes('ngrok')) {
      return `http://${host}:5001`;
    }
  }

  return 'http://192.168.10.30:5001';
};

export const API_URL = getBackendUrl();
console.log('[Gymbro Config] Supabase URL:', SUPABASE_URL);
console.log('[Gymbro Config] Backend API URL:', API_URL);


