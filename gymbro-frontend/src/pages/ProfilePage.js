import React, { useState, useEffect, useContext } from 'react';
import { Container, Typography, Paper, Grid, TextField, Button, MenuItem, Box, Alert, CircularProgress, Divider, Chip } from '@mui/material';
import { AuthContext } from '../context/AuthContext';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import GlassPaper from '../components/GlassPaper';

function ProfilePage() {
	const { authToken } = useContext(AuthContext);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [message, setMessage] = useState('');
	const [profile, setProfile] = useState({
		age: '',
		weight: '',
		height: '',
		sport_history: '',
		running_experience: '',
		past_injuries: '',
		lifestyle: '',
		weekly_availability: '',
		terrain_preference: '',
		equipment: '',
		units: 'metric',
		llm_model: 'local',
		garmin_connected: false,
		strava_connected: false
	});

	useEffect(() => {
		const fetchProfile = async () => {
			if (!authToken) return;
			try {
				const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/auth/profile`, {
					headers: { 'Authorization': `Bearer ${authToken}` }
				});
				if (response.ok) {
					const data = await response.json();
					if (data.profile) {
						setProfile(prev => ({
							...prev,
							...data.profile,
							// Ensure defaults
							units: data.profile.units || 'metric',
							llm_model: data.profile.llm_model || 'local'
						}));
					}
				}
			} catch (err) {
				console.error("Error fetching profile:", err);
			} finally {
				setLoading(false);
			}
		};
		fetchProfile();
	}, [authToken]);

	const handleChange = (e) => {
		const { name, value } = e.target;
		setProfile(prev => ({ ...prev, [name]: value }));
	};

	const handleSave = async () => {
		setSaving(true);
		setMessage('');
		try {
			const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/auth/profile`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${authToken}`
				},
				body: JSON.stringify(profile)
			});

			if (response.ok) {
				setMessage('Profile updated successfully!');
			} else {
				setMessage('Failed to update profile.');
			}
		} catch (err) {
			console.error("Error saving profile:", err);
			setMessage('Error saving profile.');
		} finally {
			setSaving(false);
		}
	};

	if (loading) return <Container sx={{ mt: 4, textAlign: 'center' }}><CircularProgress /></Container>;

	return (
		<Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
			<Typography variant="h4" gutterBottom>Profile & Settings</Typography>

			{message && <Alert severity={message.includes('success') ? 'success' : 'error'} sx={{ mb: 2 }}>{message}</Alert>}

			{/* AI Settings */}
			<GlassPaper sx={{ p: 3, mb: 3 }}>
				<Typography variant="h6" gutterBottom>AI Coach Settings</Typography>
				<Grid container spacing={2}>
					<Grid item xs={12} sm={6}>
						<TextField
							select
							fullWidth
							label="AI Model Provider"
							name="llm_model"
							value={profile.llm_model}
							onChange={handleChange}
							helperText="Choose which AI brain powers your coach."
						>
							<MenuItem value="local">Local (Free, Private)</MenuItem>
							<MenuItem value="xai">Grok (xAI - Fast)</MenuItem>
							<MenuItem value="openai">OpenAI (GPT-4o)</MenuItem>
							<MenuItem value="gemini">Gemini (Flash)</MenuItem>
						</TextField>
					</Grid>
				</Grid>
			</GlassPaper>

			{/* Integrations Status */}
			<GlassPaper sx={{ p: 3, mb: 3 }}>
				<Typography variant="h6" gutterBottom>Integrations</Typography>
				<Box display="flex" gap={2}>
					<Chip
						icon={profile.garmin_connected ? <CheckCircleIcon /> : <ErrorIcon />}
						label="Garmin"
						color={profile.garmin_connected ? "success" : "default"}
						variant={profile.garmin_connected ? "filled" : "outlined"}
					/>
					<Chip
						icon={profile.strava_connected ? <CheckCircleIcon /> : <ErrorIcon />}
						label="Strava"
						color={profile.strava_connected ? "success" : "default"}
						variant={profile.strava_connected ? "filled" : "outlined"}
					/>
				</Box>
				{!profile.garmin_connected && (
					<Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
						Go to Onboarding to connect your accounts.
					</Typography>
				)}
			</GlassPaper>

			{/* Personal Details */}
			<GlassPaper sx={{ p: 3, mb: 3, pb: 2 }}>
				<Typography variant="h6" gutterBottom>Personal Details</Typography>
				<Grid container spacing={2}>
					<Grid item xs={12} sm={6}>
						<TextField
							fullWidth
							label="Age"
							name="age"
							type="number"
							value={profile.age}
							onChange={handleChange}
						/>
					</Grid>
					<Grid item xs={12} sm={6}>
						<TextField
							select
							fullWidth
							label="Units"
							name="units"
							value={profile.units}
							onChange={handleChange}
						>
							<MenuItem value="metric">Metric (kg/cm)</MenuItem>
							<MenuItem value="imperial">Imperial (lbs/ft)</MenuItem>
						</TextField>
					</Grid>
					<Grid item xs={12} sm={6}>
						<TextField
							fullWidth
							label={`Weight (${profile.units === 'metric' ? 'kg' : 'lbs'})`}
							name="weight"
							type="number"
							value={profile.weight}
							onChange={handleChange}
						/>
					</Grid>
					<Grid item xs={12} sm={6}>
						<TextField
							fullWidth
							label={`Height (${profile.units === 'metric' ? 'cm' : 'ft'})`}
							name="height"
							type="number"
							value={profile.height}
							onChange={handleChange}
							helperText={profile.units === 'imperial' ? "Enter as decimal (e.g. 6.0 for 6ft)" : ""}
						/>
					</Grid>
					<Grid item xs={12}>
						<TextField
							fullWidth
							label="Sport History"
							name="sport_history"
							multiline
							rows={2}
							value={profile.sport_history}
							onChange={handleChange}
						/>
					</Grid>
					<Grid item xs={12}>
						<TextField
							fullWidth
							label="Current Goals"
							name="current_goal"
							multiline
							rows={2}
							value={profile.goals?.current_goal || ''}
							onChange={(e) => setProfile(prev => ({
								...prev,
								goals: { ...prev.goals, current_goal: e.target.value }
							}))}
						/>
					</Grid>
				</Grid>
			</GlassPaper>

			<Box display="flex" justifyContent="flex-end">
				<Button
					variant="contained"
					color="primary"
					size="large"
					onClick={handleSave}
					disabled={saving}
				>
					{saving ? 'Saving...' : 'Save Changes'}
				</Button>
			</Box>
		</Container>
	);
}

export default ProfilePage;
