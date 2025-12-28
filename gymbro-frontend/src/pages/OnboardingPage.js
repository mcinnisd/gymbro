import React, { useState, useContext, useEffect } from 'react';
import {
	Container, Typography, TextField, Button, Box, Paper,
	Stepper, Step, StepLabel, CircularProgress, Alert, Grid,
	Fade, Grow, IconButton, InputAdornment, Divider, useTheme,
	Card, CardContent, LinearProgress
} from '@mui/material';
import GlassPaper from '../components/GlassPaper';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import GarminIcon from '@mui/icons-material/Settings'; // Placeholder
import StravaIcon from '@mui/icons-material/DirectionsBike'; // Placeholder
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

function OnboardingPage() {
	const { authToken } = useContext(AuthContext);
	const navigate = useNavigate();
	const theme = useTheme();
	const [activeStep, setActiveStep] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState('');
	const [successMsg, setSuccessMsg] = useState('');
	const [syncStatus, setSyncStatus] = useState('not_connected');

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
		units: 'metric'
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
							current_goal: data.profile.goals?.current_goal || '',
							units: data.profile.units || 'metric'
						}));
						if (data.profile.garmin_connected) {
							setSyncStatus('connected');
						}
					}
				}
			} catch (err) {
				console.error("Error fetching profile:", err);
			}
		};
		fetchProfile();
	}, [authToken]);

	// Poll for sync status if syncing
	useEffect(() => {
		let interval;
		if (syncStatus === 'syncing') {
			interval = setInterval(async () => {
				try {
					const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/garmin/status`, {
						headers: { 'Authorization': `Bearer ${authToken}` }
					});
					if (res.ok) {
						const data = await res.json();
						if (data.garmin_sync_status === 'synced') {
							setSyncStatus('synced');
							clearInterval(interval);
						} else if (data.garmin_sync_status === 'error') {
							setSyncStatus('error');
							setError(data.garmin_last_sync_error || 'Sync failed');
							clearInterval(interval);
						}
					}
				} catch (e) {
					console.error("Error polling status:", e);
				}
			}, 3000);
		}
		return () => clearInterval(interval);
	}, [syncStatus, authToken]);

	const steps = ['Integrations', 'Survey', 'Ready'];

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
					goals: { ...profile.goals, current_goal: profile.current_goal }
				})
			});

			if (!response.ok) throw new Error('Failed to update profile');

			setSuccessMsg('Profile saved! You are ready.');
			setTimeout(() => {
				setActiveStep(2);
				setSuccessMsg('');
			}, 1000);
		} catch (err) {
			setError('Failed to save profile.');
		} finally {
			setLoading(false);
		}
	};

	const handleGarminConnect = async () => {
		if (loading || syncStatus !== 'not_connected') return;
		setLoading(true);
		setError('');
		setSuccessMsg('');
		try {
			const connectResp = await fetch(`${process.env.REACT_APP_API_BASE_URL}/garmin/connect`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${authToken}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ email: garminEmail, password: garminPassword })
			});

			if (!connectResp.ok) {
				const data = await connectResp.json();
				throw new Error(data.error || 'Failed to connect Garmin');
			}

			await fetch(`${process.env.REACT_APP_API_BASE_URL}/garmin/sync`, {
				method: 'POST',
				headers: { 'Authorization': `Bearer ${authToken}` }
			});

			setSyncStatus('syncing');
			setSuccessMsg('Garmin connected! Syncing in background...');
		} catch (err) {
			setError(err.message);
		} finally {
			setLoading(false);
		}
	};

	const handleNext = () => setActiveStep(prev => prev + 1);
	const handleBack = () => setActiveStep(prev => prev - 1);
	const handleFinish = async () => {
		setLoading(true);
		try {
			const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/coach/start_interview`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${authToken}`,
					'Content-Type': 'application/json'
				}
			});
			if (response.ok) {
				const data = await response.json();
				if (data.chat_id) {
					window.open(`/chats/${data.chat_id}`, '_blank');
					navigate('/coach'); // Go to coach page in current tab
				} else {
					navigate('/coach');
				}
			} else {
				navigate('/coach');
			}
		} catch (err) {
			console.error("Error starting interview from onboarding:", err);
			navigate('/coach');
		} finally {
			setLoading(false);
		}
	};



	return (
		<Container maxWidth="md" sx={{ py: 6 }}>
			<Fade in timeout={800}>
				<Box>
					<Typography variant="h3" align="center" sx={{ fontWeight: 800, mb: 1, background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
						Welcome to GymBro
					</Typography>
					<Typography variant="h6" align="center" color="text.secondary" sx={{ mb: 6 }}>
						Let's get you set up with your AI Coach
					</Typography>

					<Stepper activeStep={activeStep} sx={{ mb: 6 }}>
						{steps.map((label) => (
							<Step key={label}>
								<StepLabel>{label}</StepLabel>
							</Step>
						))}
					</Stepper>

					{error && <Alert severity="error" sx={{ mb: 3, borderRadius: '12px' }}>{error}</Alert>}
					{successMsg && <Alert severity="success" sx={{ mb: 3, borderRadius: '12px' }}>{successMsg}</Alert>}

					{successMsg && <Alert severity="success" sx={{ mb: 3, borderRadius: '12px' }}>{successMsg}</Alert>}

					<GlassPaper sx={{ mt: 4 }}>
						{activeStep === 0 && (
							<Grow in>
								<Box>
									<Typography variant="h5" gutterBottom sx={{ fontWeight: 700 }}>Connect Your Data</Typography>
									<Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
										Sync your Garmin or Strava to give your coach the full picture of your fitness.
									</Typography>

									<Grid container spacing={3}>
										<Grid item xs={12} md={6}>
											<Card sx={{ borderRadius: '16px', border: syncStatus === 'synced' ? '2px solid #4caf50' : '1px solid rgba(255,255,255,0.1)', bgcolor: 'rgba(0,0,0,0.2)' }}>
												<CardContent>
													<Box display="flex" alignItems="center" mb={2}>
														<IconButton color="primary" sx={{ bgcolor: 'rgba(33, 150, 243, 0.1)', mr: 2 }}>
															<GarminIcon />
														</IconButton>
														<Typography variant="h6">Garmin Connect</Typography>
													</Box>

													{syncStatus === 'not_connected' ? (
														<Box>
															<TextField label="Email" fullWidth size="small" sx={{ mb: 2 }} value={garminEmail} onChange={e => setGarminEmail(e.target.value)} />
															<TextField label="Password" type="password" fullWidth size="small" sx={{ mb: 2 }} value={garminPassword} onChange={e => setGarminPassword(e.target.value)} />
															<Button variant="contained" fullWidth onClick={handleGarminConnect} disabled={loading || !garminEmail || !garminPassword}>
																{loading ? <CircularProgress size={20} /> : 'Connect'}
															</Button>
														</Box>
													) : (
														<Box textAlign="center" py={2}>
															{syncStatus === 'syncing' ? (
																<Box>
																	<Typography variant="body2" color="primary" gutterBottom>Syncing your history...</Typography>
																	<LinearProgress sx={{ borderRadius: '4px', height: '8px' }} />
																</Box>
															) : (
																<Box display="flex" alignItems="center" justifyContent="center" color="success.main">
																	<CheckCircleOutlineIcon sx={{ mr: 1 }} />
																	<Typography>Synced Successfully</Typography>
																</Box>
															)}
														</Box>
													)}
												</CardContent>
											</Card>
										</Grid>

										<Grid item xs={12} md={6}>
											<Card sx={{ borderRadius: '16px', border: '1px solid rgba(255,255,255,0.1)', bgcolor: 'rgba(0,0,0,0.2)', opacity: 0.7 }}>
												<CardContent>
													<Box display="flex" alignItems="center" mb={2}>
														<IconButton color="warning" sx={{ bgcolor: 'rgba(255, 152, 0, 0.1)', mr: 2 }}>
															<StravaIcon />
														</IconButton>
														<Typography variant="h6">Strava</Typography>
													</Box>
													<Typography variant="body2" color="text.secondary" align="center" py={4}>
														Coming Soon
													</Typography>
												</CardContent>
											</Card>
										</Grid>
									</Grid>

									<Box display="flex" justifyContent="flex-end" mt={4}>
										<Button variant="text" onClick={handleNext} endIcon={<ArrowForwardIcon />}>
											Skip for now
										</Button>
										{syncStatus === 'synced' && (
											<Button variant="contained" onClick={handleNext} sx={{ ml: 2 }} endIcon={<ArrowForwardIcon />}>
												Continue
											</Button>
										)}
									</Box>
								</Box>
							</Grow>
						)}

						{activeStep === 1 && (
							<Grow in>
								<Box>
									<Typography variant="h5" gutterBottom sx={{ fontWeight: 700 }}>Tell Us About Yourself</Typography>
									<Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
										This helps the AI Coach tailor your training plan.
									</Typography>

									<Box display="flex" justifyContent="center" mb={4}>
										<Button variant={profile.units === 'metric' ? 'contained' : 'outlined'} onClick={() => setProfile({ ...profile, units: 'metric' })} sx={{ mr: 1, borderRadius: '20px' }}>Metric</Button>
										<Button variant={profile.units === 'imperial' ? 'contained' : 'outlined'} onClick={() => setProfile({ ...profile, units: 'imperial' })} sx={{ borderRadius: '20px' }}>Imperial</Button>
									</Box>

									<Grid container spacing={3}>
										<Grid item xs={12} sm={4}>
											<TextField label="Age" name="age" type="number" fullWidth value={profile.age} onChange={handleProfileChange} />
										</Grid>
										<Grid item xs={12} sm={4}>
											<TextField label={`Weight (${profile.units === 'metric' ? 'kg' : 'lbs'})`} name="weight" type="number" fullWidth value={profile.weight} onChange={handleProfileChange} />
										</Grid>
										<Grid item xs={12} sm={4}>
											<TextField label={`Height (${profile.units === 'metric' ? 'cm' : 'in'})`} name="height" type="number" fullWidth value={profile.height} onChange={handleProfileChange} />
										</Grid>
										<Grid item xs={12} sm={6}>
											<TextField label="Lifestyle" name="lifestyle" fullWidth select SelectProps={{ native: true }} value={profile.lifestyle} onChange={handleProfileChange}>
												<option value="">Select Lifestyle</option>
												<option value="sedentary">Sedentary (Office job, little exercise)</option>
												<option value="active">Active (On your feet, moderate exercise)</option>
												<option value="very_active">Very Active (Physical labor, heavy training)</option>
											</TextField>
										</Grid>
										<Grid item xs={12} sm={6}>
											<TextField label="Weekly Availability" name="weekly_availability" fullWidth placeholder="e.g. Mon, Wed, Fri mornings" value={profile.weekly_availability} onChange={handleProfileChange} />
										</Grid>
										<Grid item xs={12}>
											<TextField label="Primary Goal" name="current_goal" fullWidth value={profile.current_goal} onChange={handleProfileChange} placeholder="e.g. Sub-4 hour marathon" />
										</Grid>
										<Grid item xs={12}>
											<TextField label="Running Experience" name="running_experience" fullWidth multiline rows={2} value={profile.running_experience} onChange={handleProfileChange} />
										</Grid>
										<Grid item xs={12}>
											<TextField label="Past Injuries" name="past_injuries" fullWidth multiline rows={2} value={profile.past_injuries} onChange={handleProfileChange} />
										</Grid>
									</Grid>

									<Box display="flex" justifyContent="space-between" mt={4}>
										<Button startIcon={<ArrowBackIcon />} onClick={handleBack}>Back</Button>
										<Button variant="contained" onClick={handleProfileSubmit} disabled={loading}>
											{loading ? <CircularProgress size={24} /> : 'Save & Continue'}
										</Button>
									</Box>
								</Box>
							</Grow>
						)}

						{activeStep === 2 && (
							<Grow in>
								<Box textAlign="center" py={4}>
									<DirectionsRunIcon sx={{ fontSize: 80, color: 'primary.main', mb: 2 }} />
									<Typography variant="h4" gutterBottom sx={{ fontWeight: 800 }}>You're All Set!</Typography>
									<Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: '500px', mx: 'auto' }}>
										The Coach has your data and is ready to start the interview. This will take about 5-10 minutes.
									</Typography>
									<Button variant="contained" size="large" onClick={handleFinish} sx={{ px: 6, py: 1.5, borderRadius: '30px', fontSize: '1.1rem', fontWeight: 700 }}>
										Start Interview
									</Button>
								</Box>
							</Grow>
						)}
					</GlassPaper>
				</Box>
			</Fade>
		</Container>
	);
}

export default OnboardingPage;

