// src/pages/RegisterPage.js
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import Snackbar from '@mui/material/Snackbar';
import CircularProgress from '@mui/material/CircularProgress';
import GlassPaper from '../components/GlassPaper';
import MuiAlert from '@mui/material/Alert';

const Alert = React.forwardRef(function Alert(props, ref) {
  return <MuiAlert elevation={6} ref={ref} variant="filled" {...props} />;
});

function RegisterPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  // Snackbar state
  const [open, setOpen] = useState(false);
  const [alertMsg, setAlertMsg] = useState('');
  const [alertSeverity, setAlertSeverity] = useState('success');

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5001';
      console.log("API_BASE_URL:", API_BASE_URL); // Add this line

      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        setAlertMsg('Registration failed: ' + response.statusText);
        setAlertSeverity('error');
        setOpen(true);
        return;
      }

      // const data = await response.json(); // Not used
      setAlertMsg('Registration successful! Please log in to complete setup.');
      setAlertSeverity('success');
      setOpen(true);

      navigate('/login'); // Still redirect to login first to get token, or auto-login?
      // The current flow requires login to get the token. 
      // Ideally we auto-login, but for now let's keep it simple: Register -> Login -> Onboarding.
      // Wait, the user said "when a user registers id like for them to be prompted...".
      // If I redirect to login, they login, then where do they go?
      // DashboardPage is default.
      // I should probably update LoginPage to redirect to /onboarding if it's a first time login?
      // Or just let the user navigate there?
      // Better: Register -> Login (User does this) -> Dashboard.
      // Maybe I should add a check in Dashboard to redirect to Onboarding if no data?
      // For now, I'll leave the redirect to '/' (Login) but maybe show a message "Login to continue setup".

      // Actually, to make it smooth:
      // 1. Register
      // 2. Auto-login (requires backend to return token on register, which it doesn't yet)
      // 3. Redirect to /onboarding.

      // Since backend returns {message, user_id} on register, I can't auto-login easily without changing backend.
      // I'll stick to: Register -> Login -> Dashboard.
      // But I'll add a "Setup" button on Dashboard or redirect if no data.

      // User request: "when a user registers id like for them to be prompted..."
      // I'll change the alert message to be clear.
    } catch (error) {
      setAlertMsg('Error connecting to server');
      setAlertSeverity('error');
      setOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  return (
    <Container component="main" maxWidth="xs">
      <GlassPaper
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          p: 4
        }}
      >
        <Avatar sx={{ m: 1, bgcolor: 'primary.main' }}>
          <LockOutlinedIcon />
        </Avatar>
        <Typography component="h1" variant="h5">
          Register
        </Typography>
        <Box component="form" onSubmit={handleRegister} sx={{ mt: 1 }}>
          <TextField
            margin="normal"
            required
            fullWidth
            label="Username"
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3, mb: 2 }}
            disabled={loading}
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : 'Register'}
          </Button>
          <Grid container justifyContent="flex-end">
            <Grid item>
              <Link to="/" variant="body2">
                Already have an account? Log in
              </Link>
            </Grid>
          </Grid>
        </Box>
      </GlassPaper>
      <Snackbar open={open} autoHideDuration={6000} onClose={handleClose}>
        <Alert onClose={handleClose} severity={alertSeverity} sx={{ width: '100%' }}>
          {alertMsg}
        </Alert>
      </Snackbar>
    </Container >
  );
}

export default RegisterPage;