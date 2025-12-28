// src/theme.js
import { createTheme } from '@mui/material/styles';

const getTheme = (mode) => {
  // We force dark mode for the 'sleek' look, or respect the toggle if we want to keep it.
  // For this task "sleek" usually implies a curated dark mode.
  // Mode is passed in


  return createTheme({
    palette: {
      mode: mode,
      ...(mode === 'light'
        ? {
          // Light Mode
          primary: {
            main: '#6C63FF',
            contrastText: '#ffffff',
          },
          secondary: {
            main: '#00E5FF',
            contrastText: '#000000',
          },
          background: {
            default: '#F7FAFC', // Light gray/blue
            paper: '#FFFFFF',
          },
          text: {
            primary: '#1A202C',
            secondary: '#718096',
          },
        }
        : {
          // Dark Mode
          primary: {
            main: '#6C63FF',
            contrastText: '#ffffff',
          },
          secondary: {
            main: '#00E5FF',
            contrastText: '#000000',
          },
          background: {
            default: '#0A0E17',
            paper: '#111625',
          },
          text: {
            primary: '#E0E6ED',
            secondary: '#94A3B8',
          },
        }),
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: { fontWeight: 700 },
      h2: { fontWeight: 700 },
      h3: { fontWeight: 600 },
      h4: { fontWeight: 600 },
      h5: { fontWeight: 600 },
      h6: { fontWeight: 600 },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    shape: {
      borderRadius: 12,
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: '8px',
            padding: '8px 20px',
            boxShadow: 'none',
            '&:hover': {
              boxShadow: '0 4px 12px rgba(108, 99, 255, 0.4)',
            },
          },
          containedPrimary: {
            background: 'linear-gradient(45deg, #6C63FF 30%, #3f3da1 90%)',
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none', // Remove default MUI overlay
          },
          outlined: {
            borderColor: '#2D3748',
          }
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            background: '#1A202C',
            border: '1px solid #2D3748',
          },
        },
      },
    },
  });
};

export default getTheme;