import Constants from 'expo-constants';
import { Platform } from 'react-native';
import tunnelConfig from './tunnel.json';

// Supabase details
export const SUPABASE_URL = 'https://frsoqqglyiepgoudxnyu.supabase.co';
export const SUPABASE_KEY = 'sb_publishable_t1FuptaCgcr_N8qSqzTRpg_feSa02cM';

// Active Public Tunnel URL for remote mobile testing (Expo Go --tunnel)
export const PUBLIC_API_TUNNEL_URL = (tunnelConfig as any)?.tunnel_url || 'https://shaky-donkeys-double.loca.lt';

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
  const manifest = Constants.expoConfig || {};
  const hostUri = (manifest as any).hostUri || (Constants as any).manifest?.debuggerHost || '';
  if (hostUri) {
    const host = hostUri.split(':')[0];
    
    // If running in Expo Tunnel mode, default to the public backend tunnel URL
    if (host.includes('exp.direct') || host.includes('ngrok') || host.includes('tunnel')) {
      return PUBLIC_API_TUNNEL_URL;
    }

    // If running on local LAN (e.g. 192.168.x.x or 10.x.x.x), use host computer IP
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:5001`;
    }
  }

  // Standard local Wi-Fi host IP for mobile devices
  return 'http://192.168.10.30:5001';
};

export const API_URL = getBackendUrl();
console.log('[Gymbro Config] Supabase URL:', SUPABASE_URL);
console.log('[Gymbro Config] Backend API URL:', API_URL);


