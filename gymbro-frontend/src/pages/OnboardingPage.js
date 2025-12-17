import React, { useState, useContext, useEffect } from 'react';
import { Container, Typography, TextField, Button, Box, Paper, Stepper, Step, StepLabel, CircularProgress, Alert, Grid } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

function OnboardingPage() {
	const { authToken } = useContext(AuthContext);
	const navigate = useNavigate();
	const [activeStep, setActiveStep] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState('');
	const [successMsg, setSuccessMsg] = useState('');

	// Garmin State
	const [garminEmail, setGarminEmail] = useState('');
	const [garminPassword, setGarminPassword] = useState('');

	// Profile State
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
		current_goal: '',
		units: 'metric' // Default to metric
	});

	// Fetch existing profile on mount
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
							current_goal: data.profile.goals?.current_goal || '',
							units: data.profile.units || 'metric'
						}));
					}
				}
			} catch (err) {
				console.error("Error fetching profile:", err);
			}
		};
		fetchProfile();
	}, [authToken]);

	const steps = ['Connect Garmin', 'Connect Strava', 'Profile Details', 'Ready'];

	const handleProfileChange = (e) => {
		setProfile({ ...profile, [e.target.name]: e.target.value });
	};

	const handleProfileSubmit = async () => {
		setLoading(true);
		setError('');
		try {
			const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/auth/profile`, {
				method: 'PUT',
				headers: {
					'Authorization': `Bearer ${authToken}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					...profile,
					goals: { current_goal: profile.current_goal }
				})
			});

			if (!response.ok) {
				throw new Error('Failed to update profile');
			}

			setSuccessMsg('Profile updated!');
			setTimeout(() => {
				setActiveStep((prev) => prev + 1);
				setSuccessMsg('');
			}, 1000);
		} catch (err) {
			console.error(err);
			setError('Failed to save profile.');
		} finally {
			setLoading(false);
		}
	};

	const handleGarminConnect = async () => {
		setLoading(true);
		setError('');
		setSuccessMsg('');
		try {
			// 1. Save Credentials
			const connectResp = await fetch(`${process.env.REACT_APP_API_BASE_URL}/garmin/connect`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${authToken}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ email: garminEmail, password: garminPassword })
			});

			if (!connectResp.ok) {
				throw new Error('Failed to save Garmin credentials');
			}

			// 2. Trigger Sync
			const syncResp = await fetch(`${process.env.REACT_APP_API_BASE_URL}/garmin/sync`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${authToken}`
				}
			});

			if (!syncResp.ok) {
				throw new Error('Failed to trigger Garmin sync');
			}

			setSuccessMsg('Garmin connected and syncing!');
			setTimeout(() => {
				setActiveStep((prev) => prev + 1);
				setSuccessMsg('');
			}, 1500);

		} catch (err) {
			console.error(err);
			setError(err.message || 'Error connecting Garmin');
		} finally {
			setLoading(false);
		}
	};

	const handleStravaConnect = () => {
		// Placeholder for Strava OAuth flow
		// In a real app, this would redirect to Strava's OAuth URL
		// For now, we'll just skip or show a "Coming Soon" message
		setActiveStep((prev) => prev + 1);
	};

	const handleFinish = () => {
		navigate('/coach');
	};

	return (
		<Container maxWidth="md" sx={{ mt: 8, mb: 8 }}>
			<Paper elevation={3} sx={{ p: 4 }}>
				<Typography variant="h4" align="center" gutterBottom>
					Setup Integrations & Profile
				</Typography>

				<Stepper activeStep={activeStep} sx={{ mb: 4 }} alternativeLabel>
					{steps.map((label) => (
						<Step key={label}>
							<StepLabel>{label}</StepLabel>
						</Step>
					))}
				</Stepper>

				{error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
				{successMsg && <Alert severity="success" sx={{ mb: 2 }}>{successMsg}</Alert>}

				{activeStep === 0 && (
					<Box maxWidth="sm" mx="auto">
						<Typography variant="h6" gutterBottom>Connect Garmin</Typography>
						<Typography variant="body2" color="text.secondary" paragraph>
							Enter your Garmin Connect credentials to sync your activities and health metrics.
						</Typography>
						<TextField
							label="Email"
							fullWidth
							margin="normal"
							value={garminEmail}
							onChange={(e) => setGarminEmail(e.target.value)}
						/>
						<TextField
							label="Password"
							type="password"
							fullWidth
							margin="normal"
							value={garminPassword}
							onChange={(e) => setGarminPassword(e.target.value)}
						/>
						<Button
							variant="contained"
							fullWidth
							sx={{ mt: 2 }}
							onClick={handleGarminConnect}
							disabled={loading || !garminEmail || !garminPassword}
						>
							{loading ? <CircularProgress size={24} /> : 'Connect & Sync'}
						</Button>
						<Button
							variant="text"
							fullWidth
							sx={{ mt: 1 }}
							onClick={() => setActiveStep(1)}
						>
							Skip
						</Button>
					</Box>
				)}

				{activeStep === 1 && (
					<Box maxWidth="sm" mx="auto" textAlign="center">
						<Typography variant="h6" gutterBottom>Connect Strava</Typography>
						<Typography variant="body2" color="text.secondary" paragraph>
							Connect your Strava account to import activities.
						</Typography>
						<Button
							variant="contained"
							color="warning"
							fullWidth
							sx={{ mt: 2 }}
							onClick={handleStravaConnect}
						>
							Connect with Strava (Coming Soon)
						</Button>
						<Button
							variant="text"
							fullWidth
							sx={{ mt: 1 }}
							onClick={() => setActiveStep(2)}
						>
							Skip
						</Button>
					</Box>
				)}

				{activeStep === 2 && (
					<Box>
						<Typography variant="h6" gutterBottom>Profile Details</Typography>
						<Typography variant="body2" color="text.secondary" paragraph>
							Help the Coach understand your background.
						</Typography>

						{/* Units Toggle */}
						<Box display="flex" justifyContent="center" mb={3}>
							<Button
								variant={profile.units === 'metric' ? 'contained' : 'outlined'}
								onClick={() => setProfile({ ...profile, units: 'metric' })}
								sx={{ mr: 1 }}
							>
								Metric (kg/cm)
							</Button>
							<Button
								variant={profile.units === 'imperial' ? 'contained' : 'outlined'}
								onClick={() => setProfile({ ...profile, units: 'imperial' })}
							>
								Imperial (lbs/ft)
							</Button>
						</Box>

						<Grid container spacing={2}>
							<Grid item xs={12} sm={6}>
								<TextField label="Age" name="age" type="number" fullWidth value={profile.age} onChange={handleProfileChange} />
							</Grid>
							<Grid item xs={12} sm={6}>
								<TextField
									label={`Weight (${profile.units === 'metric' ? 'kg' : 'lbs'})`}
									name="weight"
									type="number"
									fullWidth
									value={profile.weight}
									onChange={handleProfileChange}
								/>
							</Grid>
							<Grid item xs={12} sm={6}>
								<TextField
									label={`Height (${profile.units === 'metric' ? 'cm' : 'ft/in'})`}
									name="height"
									type="number"
									fullWidth
									value={profile.height}
									onChange={handleProfileChange}
									helperText={profile.units === 'imperial' ? "Enter height in inches (e.g. 5'10\" = 70)" : ""}
								/>
							</Grid>
							<Grid item xs={12} sm={6}>
								<TextField label="Weekly Availability" name="weekly_availability" fullWidth value={profile.weekly_availability} onChange={handleProfileChange} placeholder="e.g. 5 days, 1 hour" />
							</Grid>
							<Grid item xs={12}>
								<TextField label="Current Goal" name="current_goal" fullWidth value={profile.current_goal} onChange={handleProfileChange} placeholder="e.g. Run a sub-4 hour marathon in October" />
							</Grid>
							<Grid item xs={12}>
								<TextField label="Sport History" name="sport_history" fullWidth multiline rows={2} value={profile.sport_history} onChange={handleProfileChange} placeholder="e.g. Played soccer in college..." />
							</Grid>
							<Grid item xs={12}>
								<TextField label="Running Experience" name="running_experience" fullWidth multiline rows={2} value={profile.running_experience} onChange={handleProfileChange} placeholder="e.g. Running for 2 years, best 5k is 25min..." />
							</Grid>
							<Grid item xs={12}>
								<TextField label="Past Injuries" name="past_injuries" fullWidth multiline rows={2} value={profile.past_injuries} onChange={handleProfileChange} placeholder="e.g. Knee pain in 2023..." />
							</Grid>
							<Grid item xs={12}>
								<TextField label="Lifestyle / Work" name="lifestyle" fullWidth multiline rows={2} value={profile.lifestyle} onChange={handleProfileChange} placeholder="e.g. Sedentary desk job..." />
							</Grid>
							<Grid item xs={12} sm={6}>
								<TextField label="Terrain Preference" name="terrain_preference" fullWidth value={profile.terrain_preference} onChange={handleProfileChange} />
							</Grid>
							<Grid item xs={12} sm={6}>
								<TextField label="Equipment" name="equipment" fullWidth value={profile.equipment} onChange={handleProfileChange} />
							</Grid>
						</Grid>

						<Button
							variant="contained"
							fullWidth
							sx={{ mt: 3 }}
							onClick={handleProfileSubmit}
							disabled={loading}
						>
							{loading ? <CircularProgress size={24} /> : 'Save Profile'}
						</Button>
						<Button
							variant="text"
							fullWidth
							sx={{ mt: 1 }}
							onClick={() => setActiveStep(3)}
						>
							Skip
						</Button>
					</Box>
				)}

				{activeStep === 3 && (
					<Box textAlign="center">
						<Typography variant="h5" gutterBottom>All Set!</Typography>
						<Typography paragraph>
							Your data is ready. The Coach has been briefed on your profile and recent activities.
						</Typography>
						<Button
							variant="contained"
							size="large"
							onClick={handleFinish}
						>
							Start Interview
						</Button>
					</Box>
				)}
			</Paper>
		</Container>
	);
}

export default OnboardingPage;
