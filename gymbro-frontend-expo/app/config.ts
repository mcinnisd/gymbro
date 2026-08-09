import Constants from 'expo-constants';

// Supabase details
export const SUPABASE_URL = 'https://frsoqqglyiepgoudxnyu.supabase.co';
export const SUPABASE_KEY = 'sb_publishable_t1FuptaCgcr_N8qSqzTRpg_feSa02cM';

// Local Flask API Server Address
// Automatically resolves host computer IP when running on Expo Go/Physical device
const getBackendUrl = () => {
  // If we have a debugger host, extract the IP
  const manifest = Constants.expoConfig || {};
  // For Expo SDK 50+ / Router: hostUri is inside expoConfig or manifest
  const hostUri = (manifest as any).hostUri || '';
  if (hostUri) {
    const ip = hostUri.split(':')[0];
    return `http://${ip}:5001`;
  }
  return 'http://127.0.0.1:5001';
};

export const API_URL = getBackendUrl();
console.log('[Gymbro Config] Supabase URL:', SUPABASE_URL);
console.log('[Gymbro Config] Backend API URL:', API_URL);
