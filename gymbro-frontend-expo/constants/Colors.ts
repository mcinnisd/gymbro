/**
 * GYMBro Warm & Motivating Modern Design System Color Tokens.
 * 
 * Inspired by warm natural paper, rich espresso typography,
 * earthy forest sage, and energizing warm terracotta accents.
 */

export const Colors = {
  light: {
    // Canvas & Surfaces
    background: '#FBF9F5',       // Warm linen / daylight parchment canvas
    card: '#FFFFFF',             // Clean crisp paper card surface
    cardElevated: '#F5F2EA',     // Soft secondary card tint
    cardSubtle: '#F7F4EC',       // Subtle grouping background
    border: '#EAE5DC',           // Warm organic stone border
    borderSubtle: '#F0EBE1',     // Ultra-soft separator border

    // Typography
    text: '#1C1917',             // Rich warm espresso / charcoal
    secondaryText: '#78716C',    // Warm stone 500
    mutedText: '#A8A29E',        // Warm stone 400
    subtext: '#78716C',

    // Core Brand Accents
    primary: '#D97706',          // Warm Amber / Terracotta energy (motivating, human)
    primaryHover: '#B45309',
    primaryLight: '#FEF3C7',     // Soft glowing amber wash
    secondary: '#059669',        // Earthy Forest Sage
    
    // Domain & Biometric Accents
    vitality: '#059669',         // Forest Sage (HRV, recovery, fresh health)
    vitalityLight: '#D1FAE5',    // Soft sage wash
    recovery: '#10B981',         // Earthy Emerald (optimal readiness)
    recoveryLight: '#ECFDF5',
    cardio: '#E11D48',           // Coral Rose (active heart rate, intense runs)
    cardioLight: '#FFE4E6',
    sleepDusk: '#4F46E5',        // Twilight Indigo (deep restorative sleep)
    sleepLight: '#EEF2FF',
    warning: '#D97706',          // Warm Sun Amber (attention, elevated load)
    danger: '#DC2626',           // Crimson (critical strain / overreaching)

    // Navigation & Headers
    tint: '#D97706',             // Active navigation accent
    tabIconDefault: '#A8A29E',   // Inactive tab icon
    tabIconSelected: '#D97706',  // Active tab icon
    tabBarBackground: '#FFFFFF', // Tab bar surface
    headerBackground: '#FBF9F5', // Top bar canvas
    headerTint: '#1C1917',       // Header title color

    // Shadows & Elevation
    shadowColor: '#2C2218',
  },
  dark: {
    background: '#141210',       // Warm midnight obsidian
    card: '#1F1D1A',             // Dark charcoal slate
    cardElevated: '#282521',
    cardSubtle: '#24211D',
    border: '#332E29',
    borderSubtle: '#292521',

    text: '#FDFCF7',
    secondaryText: '#A8A29E',
    mutedText: '#78716C',
    subtext: '#A8A29E',

    primary: '#F59E0B',
    primaryHover: '#D97706',
    primaryLight: '#3D2800',
    secondary: '#10B981',

    vitality: '#10B981',
    vitalityLight: '#064E3B',
    recovery: '#34D399',
    recoveryLight: '#064E3B',
    cardio: '#FB7185',
    cardioLight: '#4C0519',
    sleepDusk: '#818CF8',
    sleepLight: '#1E1B4B',
    warning: '#FBBF24',
    danger: '#F87171',

    tint: '#F59E0B',
    tabIconDefault: '#78716C',
    tabIconSelected: '#F59E0B',
    tabBarBackground: '#1F1D1A',
    headerBackground: '#141210',
    headerTint: '#FDFCF7',

    shadowColor: '#000000',
  },
};

export default Colors;
