/**
 * GYMBro Organic Light Design System Color Tokens.
 *
 * Moab Terracotta, Forest Sage, Eggshell canvas, Espresso Charcoal typography.
 * Aligns with Wayfinder #38 while keeping warm biometric domain accents.
 */

export const Colors = {
  light: {
    // Canvas & Surfaces — Eggshell / organic paper
    background: '#FAF7F2', // Eggshell canvas
    card: '#FFFFFF',
    cardElevated: '#F3EEE6',
    cardSubtle: '#F6F1E9',
    border: '#E8E1D6',
    borderSubtle: '#F0EBE3',

    // Typography — Espresso Charcoal
    text: '#22252A',
    secondaryText: '#6B6560',
    mutedText: '#9A948C',
    subtext: '#6B6560',

    // Core Brand Accents
    primary: '#D96B43', // Moab Terracotta
    primaryHover: '#C45A35',
    primaryLight: '#F8E6DC', // Soft terracotta wash
    secondary: '#2D5A46', // Forest Sage

    // Domain & Biometric Accents
    vitality: '#2D5A46', // Forest Sage (HRV, recovery)
    vitalityLight: '#DCEBE3',
    recovery: '#3D7A5F', // Sage lift (optimal readiness)
    recoveryLight: '#E8F3ED',
    cardio: '#C45A35', // Terracotta-adjacent intensity
    cardioLight: '#F8E6DC',
    sleepDusk: '#4A5568', // Soft dusk slate (restorative sleep)
    sleepLight: '#EEF1F5',
    warning: '#D97706', // Warm amber attention
    danger: '#DC2626',

    // Navigation & Headers
    tint: '#D96B43',
    tabIconDefault: '#9A948C',
    tabIconSelected: '#D96B43',
    tabBarBackground: '#FFFFFF',
    headerBackground: '#FAF7F2',
    headerTint: '#22252A',

    // Shadows & Elevation
    shadowColor: '#2C2218',
  },
  dark: {
    background: '#141210',
    card: '#1F1D1A',
    cardElevated: '#282521',
    cardSubtle: '#24211D',
    border: '#332E29',
    borderSubtle: '#292521',

    text: '#FDFCF7',
    secondaryText: '#A8A29E',
    mutedText: '#78716C',
    subtext: '#A8A29E',

    primary: '#E8845C',
    primaryHover: '#D96B43',
    primaryLight: '#3D2418',
    secondary: '#4A8A6C',

    vitality: '#4A8A6C',
    vitalityLight: '#1A3328',
    recovery: '#5C9B7A',
    recoveryLight: '#1A3328',
    cardio: '#E8845C',
    cardioLight: '#3D2418',
    sleepDusk: '#94A3B8',
    sleepLight: '#1E2430',
    warning: '#FBBF24',
    danger: '#F87171',

    tint: '#E8845C',
    tabIconDefault: '#78716C',
    tabIconSelected: '#E8845C',
    tabBarBackground: '#1F1D1A',
    headerBackground: '#141210',
    headerTint: '#FDFCF7',

    shadowColor: '#000000',
  },
};

export default Colors;
