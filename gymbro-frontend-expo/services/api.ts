import { Platform } from 'react-native';
import Constants from 'expo-constants';
import tunnelConfig from '../tunnel.json';

// Default LAN IP and Tunnel URLs
export const DEFAULT_LAN_URL = 'http://192.168.10.30:5001';
export const DEFAULT_TUNNEL_URL = (tunnelConfig as any)?.tunnel_url || 'https://shaky-donkeys-double.loca.lt';

let activeToken: string | null = null;
let customApiUrl: string | null = null;
let activeApiUrl: string = DEFAULT_LAN_URL;

/**
 * Determine the initial backend API URL based on runtime environment.
 */
export const resolveInitialApiUrl = (): string => {
  if (customApiUrl) return customApiUrl;

  // 1. Web environment
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
    // If running with Expo Tunnel (--tunnel), default to backend tunnel URL
    if (host.includes('exp.direct') || host.includes('ngrok') || host.includes('tunnel')) {
      return DEFAULT_TUNNEL_URL;
    }
    // If running on local LAN, use host computer IP
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:5001`;
    }
  }

  return DEFAULT_LAN_URL;
};

activeApiUrl = resolveInitialApiUrl();

export const setAuthTokenInApi = (token: string | null) => {
  activeToken = token;
};

/**
 * Set a custom API URL override at runtime.
 */
export const setCustomApiUrl = (url: string | null) => {
  customApiUrl = url;
  if (url) {
    activeApiUrl = url.trim().replace(/\/+$/, '');
  } else {
    activeApiUrl = resolveInitialApiUrl();
  }
};

/**
 * Get current active API base URL.
 */
export const getEffectiveApiUrl = (): string => {
  return activeApiUrl;
};

/**
 * Centralized fetch with auto-headers, auth token injection, and instant LAN/Tunnel fallback.
 */
export const apiFetch = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  const baseHeaders: Record<string, string> = {
    'Accept': 'application/json',
    'bypass-tunnel-reminder': 'true',
    'Bypass-Tunnel-Reminder': 'true',
  };

  // Only add Content-Type if body is not FormData
  if (!(options.body instanceof FormData)) {
    baseHeaders['Content-Type'] = 'application/json';
  }

  if (activeToken) {
    baseHeaders['Authorization'] = `Bearer ${activeToken}`;
  }

  const mergedHeaders = {
    ...baseHeaders,
    ...(options.headers as Record<string, string> || {}),
  };

  const primaryBase = activeApiUrl.replace(/\/+$/, '');
  const primaryUrl = `${primaryBase}${cleanEndpoint}`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(primaryUrl, {
      ...options,
      headers: mergedHeaders,
      signal: options.signal || controller.signal,
    });
    clearTimeout(timeoutId);

    // If localtunnel returned an HTML interstitial by mistake, trigger fallback
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('text/html') && !cleanEndpoint.includes('html')) {
      throw new Error('Received HTML response from tunnel interstitial');
    }

    return response;
  } catch (primaryErr: any) {
    console.warn(`[apiFetch] Primary request failed for ${primaryUrl}:`, primaryErr?.message || primaryErr);

    // Determine alternate fallback URL
    const fallbackBase =
      activeApiUrl === DEFAULT_TUNNEL_URL ? DEFAULT_LAN_URL : DEFAULT_TUNNEL_URL;

    if (fallbackBase && fallbackBase !== activeApiUrl) {
      const fallbackUrl = `${fallbackBase.replace(/\/+$/, '')}${cleanEndpoint}`;
      console.log(`[apiFetch] Attempting automatic failover to ${fallbackUrl}...`);

      try {
        const fallbackRes = await fetch(fallbackUrl, {
          ...options,
          headers: mergedHeaders,
        });

        // If fallback succeeded, persist activeApiUrl for future calls
        activeApiUrl = fallbackBase;
        console.log(`[apiFetch] Failover succeeded! Switched active backend to: ${fallbackBase}`);
        return fallbackRes;
      } catch (fallbackErr) {
        console.error(`[apiFetch] Failover to ${fallbackUrl} also failed.`);
      }
    }

    throw primaryErr;
  }
};

/**
 * Ping check to verify server connectivity.
 */
export const testApiConnection = async (targetUrl?: string): Promise<boolean> => {
  const base = (targetUrl || activeApiUrl).replace(/\/+$/, '');
  try {
    const res = await fetch(`${base}/chats`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'bypass-tunnel-reminder': 'true',
      },
    });
    return res.status >= 200 && res.status < 500;
  } catch {
    return false;
  }
};
