import React, { useState, useEffect, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { Box, Typography, Container, Paper, Grid, CircularProgress, Button, FormControlLabel, Checkbox } from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

function ActivityDetailsPage() {
	const { activityId } = useParams();
	const navigate = useNavigate();
	const { authToken } = useContext(AuthContext);
	const [activity, setActivity] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const [isSyncing, setIsSyncing] = useState(false);

	// Overlay Toggles
	const [showHR, setShowHR] = useState(true);
	const [showElevation, setShowElevation] = useState(false);
	const [showSpeed, setShowSpeed] = useState(false);

	useEffect(() => {
		const fetchActivity = async () => {
			try {
				const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/activities/${activityId}`, {
					headers: { 'Authorization': `Bearer ${authToken}` }
				});
				if (res.ok) {
					const data = await res.json();
					setActivity(data);

					// Auto-sync if details are missing
					if (!data.details || !data.details.metricDescriptors) {
						console.log("Details missing, triggering auto-sync...");
						setIsSyncing(true);
						syncDetails();
					}
				} else {
					setError("Failed to load activity.");
				}
			} catch (err) {
				console.error(err);
				setError("Error loading activity.");
			} finally {
				setLoading(false);
			}
		};

		const syncDetails = async () => {
			try {
				const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/activities/${activityId}/sync`, {
					method: 'POST',
					headers: { 'Authorization': `Bearer ${authToken}` }
				});
				if (res.ok) {
					console.log("Auto-sync successful, reloading activity...");
					// Re-fetch activity data after a short delay to allow DB update
					setTimeout(async () => {
						const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/activities/${activityId}`, {
							headers: { 'Authorization': `Bearer ${authToken}` }
						});
						if (res.ok) {
							const data = await res.json();
							setActivity(data);
						}
						setIsSyncing(false);
					}, 2000); // Increased delay slightly
				} else {
					console.error("Auto-sync failed");
					setIsSyncing(false);
				}
			} catch (e) {
				console.error("Error auto-syncing:", e);
				setIsSyncing(false);
			}
		};

		fetchActivity();
	}, [activityId, authToken]);

	if (loading) return <Container sx={{ mt: 4, textAlign: 'center' }}><CircularProgress /></Container>;
	if (error) return <Container sx={{ mt: 4 }}><Typography color="error">{error}</Typography></Container>;
	if (!activity) return <Container sx={{ mt: 4 }}><Typography>Activity not found.</Typography></Container>;

	// Parse metrics from 'details' if available
	const details = activity.details;
	console.log("Activity Details Object:", details); // DEBUG
	const metricsList = details?.activityDetailMetrics || [];
	const descriptors = details?.metricDescriptors || [];

	// Create a map of key -> index
	const keyMap = {};
	descriptors.forEach(d => {
		if (d.key && d.metricsIndex !== undefined) {
			keyMap[d.key] = d.metricsIndex;
		}
	});

	console.log("KeyMap:", keyMap); // DEBUG

	const chartData = metricsList.map((m, index) => {
		const values = m.metrics || [];
		// Timestamp is usually in ms or similar. If it's relative, we might need to add to start time.
		// directTimestamp seems to be a large number (1765017752000.0), likely epoch ms.
		const timestamp = values[keyMap['directTimestamp']];

		return {
			time: timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : index,
			heartRate: values[keyMap['directHeartRate']],
			elevation: values[keyMap['directElevation']],
			speed: values[keyMap['directSpeed']],
		};
	});

	console.log("ChartData Sample:", chartData.slice(0, 5)); // DEBUG

	return (
		<Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
			<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/dashboard')} sx={{ mb: 2 }}>
				Back to Dashboard
			</Button>

			<Paper sx={{ p: 3, mb: 3 }}>
				<Typography variant="h4" gutterBottom>{activity.activity_name}</Typography>
				<Typography variant="subtitle1" color="text.secondary">
					{new Date(activity.start_time_local).toLocaleString()}
				</Typography>

				<Grid container spacing={3} sx={{ mt: 2 }}>
					<Grid item xs={6} md={3}>
						<Typography variant="h6">{(activity.distance / 1000).toFixed(2)} km</Typography>
						<Typography variant="body2" color="text.secondary">Distance</Typography>
					</Grid>
					<Grid item xs={6} md={3}>
						<Typography variant="h6">{Math.round(activity.duration / 60)} min</Typography>
						<Typography variant="body2" color="text.secondary">Duration</Typography>
					</Grid>
					<Grid item xs={6} md={3}>
						<Typography variant="h6">{activity.calories}</Typography>
						<Typography variant="body2" color="text.secondary">Calories</Typography>
					</Grid>
					<Grid item xs={6} md={3}>
						<Typography variant="h6">{activity.activity_type}</Typography>
						<Typography variant="body2" color="text.secondary">Type</Typography>
					</Grid>
				</Grid>
			</Paper>

			{/* Chart Controls */}
			<Paper sx={{ p: 2, mb: 3, display: 'flex', gap: 3 }}>
				<Typography variant="h6" sx={{ mr: 2 }}>Chart Overlays:</Typography>
				<FormControlLabel control={<Checkbox checked={showHR} onChange={(e) => setShowHR(e.target.checked)} />} label="Heart Rate" />
				<FormControlLabel control={<Checkbox checked={showElevation} onChange={(e) => setShowElevation(e.target.checked)} />} label="Elevation" />
				<FormControlLabel control={<Checkbox checked={showSpeed} onChange={(e) => setShowSpeed(e.target.checked)} />} label="Speed" />
			</Paper>

			{/* Main Chart */}
			{chartData.length > 0 ? (
				<Paper sx={{ p: 3 }}>
					<ResponsiveContainer width="100%" height={400}>
						<LineChart data={chartData}>
							<CartesianGrid strokeDasharray="3 3" />
							<XAxis dataKey="time" label={{ value: 'Time (samples)', position: 'insideBottomRight', offset: -5 }} />
							<YAxis yAxisId="left" />
							<YAxis yAxisId="right" orientation="right" />
							<Tooltip />
							<Legend />

							{showHR && <Line yAxisId="left" type="monotone" dataKey="heartRate" stroke="#d32f2f" dot={false} name="Heart Rate" />}
							{showElevation && <Line yAxisId="right" type="monotone" dataKey="elevation" stroke="#1976d2" dot={false} name="Elevation" />}
							{showSpeed && <Line yAxisId="right" type="monotone" dataKey="speed" stroke="#388e3c" dot={false} name="Speed" />}
						</LineChart>
					</ResponsiveContainer>
				</Paper>
			) : (
				<Paper sx={{ p: 3, textAlign: 'center' }}>
					{isSyncing ? (
						<Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
							<CircularProgress size={24} />
							<Typography>Syncing detailed data from Garmin...</Typography>
							<Typography variant="body2" color="text.secondary">This may take a few seconds.</Typography>
						</Box>
					) : (
						<Box>
							<Typography gutterBottom>No detailed chart data available for this activity.</Typography>
							<Typography variant="body2" color="text.secondary">
								Attempting to fetch data...
							</Typography>
						</Box>
					)}
				</Paper>
			)}
		</Container>
	);
}

export default ActivityDetailsPage;
