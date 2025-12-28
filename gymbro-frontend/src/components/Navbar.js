// src/components/Navbar.js
import React, { useContext } from 'react';
import { AppBar, Toolbar, Typography, Button, Box, IconButton, useTheme, useMediaQuery } from '@mui/material';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';

function Navbar() {
  const { authToken, setAuthToken, darkMode, setDarkMode } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const handleLogout = () => {
    setAuthToken(null);
    navigate('/');
  };

  const navItems = [
    { label: 'Dashboard', path: '/dashboard' },
    { label: 'Coach', path: '/coach' },
    { label: 'Chats', path: '/chats' },
    { label: 'Calendar', path: '/calendar' },
    { label: 'Profile', path: '/profile' },
  ];

  const getButtonSx = (path) => ({
    textTransform: 'none',
    fontWeight: location.pathname.startsWith(path) && path !== '/' ? 700 : 500,
    color: location.pathname.startsWith(path) && path !== '/' ? 'primary.main' : 'text.secondary',
    mx: 1,
    '&:hover': {
      color: 'primary.light',
      bgcolor: 'rgba(108, 99, 255, 0.08)'
    },
    borderBottom: location.pathname.startsWith(path) && path !== '/' ? '2px solid' : '2px solid transparent',
    borderColor: location.pathname.startsWith(path) && path !== '/' ? 'primary.main' : 'transparent',
    borderRadius: '4px 4px 0 0',
    pb: 0.5
  });

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: 'background.default',
        borderBottom: '1px solid',
        borderColor: 'divider',
        backdropFilter: 'blur(10px)',
        background: 'linear-gradient(to right, rgba(10, 14, 23, 0.95), rgba(17, 22, 37, 0.95))'
      }}
    >
      <Toolbar>
        <Typography
          variant="h6"
          component={Link}
          to="/"
          sx={{
            flexGrow: 1,
            textDecoration: 'none',
            color: 'text.primary',
            fontWeight: 800,
            letterSpacing: -0.5,
            background: 'linear-gradient(45deg, #6C63FF, #00E5FF)',
            backgroundClip: 'text',
            textFillColor: 'transparent',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            display: 'flex',
            alignItems: 'center',
            gap: 1
          }}
        >
          GymBro
        </Typography>

        {isMobile ? (
          // Simplified Mobile View ideally would act as a drawer, but for now just basic actions
          <Box display="flex">
            <IconButton onClick={() => setDarkMode(!darkMode)} color="inherit">
              {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
            </IconButton>
          </Box>
        ) : (
          <Box display="flex" alignItems="center">
            {authToken ? (
              <>
                {navItems.map((item) => (
                  <Button
                    key={item.label}
                    component={Link}
                    to={item.path}
                    disableRipple
                    sx={getButtonSx(item.path)}
                  >
                    {item.label}
                  </Button>
                ))}

                <Box sx={{ width: 1, height: 24, bgcolor: 'divider', mx: 2 }} />

                <Button
                  color="inherit"
                  onClick={handleLogout}
                  sx={{
                    textTransform: 'none',
                    color: 'text.secondary',
                    '&:hover': { color: 'error.main' }
                  }}
                >
                  Logout
                </Button>
                <IconButton onClick={() => setDarkMode(!darkMode)} color="inherit" sx={{ ml: 1 }}>
                  {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
                </IconButton>
              </>
            ) : (
              <>
                <Button component={Link} to="/" sx={getButtonSx('/')}>Login</Button>
                <Button
                  component={Link}
                  to="/register"
                  variant="contained"
                  color="primary"
                  sx={{ ml: 2, borderRadius: '20px', px: 3 }}
                >
                  Register
                </Button>
                <IconButton onClick={() => setDarkMode(!darkMode)} color="inherit" sx={{ ml: 1 }}>
                  {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
                </IconButton>
              </>
            )}
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
}

export default Navbar;