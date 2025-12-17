import React, { useState, useEffect, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { Box, Typography, Container, Paper, Grid, CircularProgress, Button, FormControlLabel, Checkbox } from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, ReferenceArea } from 'recharts';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

function SleepDetailsPage() {
	const { date } = useParams();
	const navigate = useNavigate();
	const { authToken } = useContext(AuthContext);
	const [sleepData, setSleepData] = useState(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchSleep = async () => {
			try {
				// We can reuse the daily_stats endpoint or fetch specific sleep data.
				// For now, let's fetch daily_stats and filter by date, or create a specific endpoint.
				// To be cleaner, let's assume we'll add a specific endpoint or just filter client side if we fetched all.
				// But fetching all is inefficient. Let's add a specific endpoint in the backend next.
				// For now, I'll fetch the daily_stats (last 7 days) and find the date, 
				// OR I can quickly add a /sleep/:date endpoint. 
				// Let's try to fetch from daily_stats first as it's already there, if the date is recent.
				// Actually, the user might click an old date. Let's add the endpoint.
				const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/activities/sleep/${date}`, {
					headers: { 'Authorization': `Bearer ${authToken}` }
				});
				if (res.ok) {
					const data = await res.json();
					setSleepData(data);
				}
			} catch (error) {
				console.error("Error fetching sleep data:", error);
			} finally {
				setLoading(false);
			}
		};
		fetchSleep();
	}, [date, authToken]);

	// Overlay Toggles
	const [showHR, setShowHR] = useState(true);
	const [showHRV, setShowHRV] = useState(false);
	const [showStress, setShowStress] = useState(false);

	if (loading) return <Container sx={{ mt: 4, textAlign: 'center' }}><CircularProgress /></Container>;
	if (!sleepData) return <Container sx={{ mt: 4 }}><Typography>Sleep data not found for {date}.</Typography></Container>;

	const dto = sleepData.sleep_data?.dailySleepDTO || {};

	const stagesData = [
		{ name: 'Deep', value: (dto.deepSleepSeconds || 0) / 3600, color: '#1976d2' },
		{ name: 'Light', value: (dto.lightSleepSeconds || 0) / 3600, color: '#42a5f5' },
		{ name: 'REM', value: (dto.remSleepSeconds || 0) / 3600, color: '#9c27b0' },
		{ name: 'Awake', value: (dto.awakeSleepSeconds || 0) / 3600, color: '#e0e0e0' },
	].filter(d => d.value > 0);

	const totalSleep = (dto.sleepTimeSeconds || 0) / 3600;

	// Prepare Overlaid Chart Data
	// We need to merge HR, HRV, Stress by timestamp. 
	// They might have different timestamps, so we'll need to align them or just plot them on the same X-axis if they are close enough.
	// A simpler approach for Recharts with different timestamps is to just pass them as separate data arrays to separate Lines? 
	// No, Recharts needs a single data array for the X-axis to align perfectly if we want a shared tooltip.
	// However, if we just want to visually overlay, we can try to merge.
	// Given the complexity of merging different sampling rates in JS, and the user's request "if there isnt data alignment... only plot parts where we do have data",
	// let's try to map everything to a common time bucket (e.g. every minute) or just use the HR timestamps as the base and find nearest neighbors.
	// OR, simpler: Just use the HR data as the "master" list and lookup others?
	// Let's look at the data structure again. 
	// HR, HRV, Stress are lists of { startGMT, value }.

	// Let's create a combined dataset.
	const processTimeSeries = (data, key) => (data || []).map(d => ({
		timestamp: new Date(d.startGMT).getTime(),
		[key]: d.value
	}));

	const hrData = processTimeSeries(sleepData.sleep_data?.sleepHeartRate, 'heartRate');
	const hrvData = processTimeSeries(sleepData.sleep_data?.hrvData, 'hrv');
	const stressData = processTimeSeries(sleepData.sleep_data?.sleepStress, 'stress');

	// Merge all into one array sorted by timestamp
	const allPoints = [...hrData, ...hrvData, ...stressData].sort((a, b) => a.timestamp - b.timestamp);

	// Deduplicate/Merge by timestamp (simple version)
	const mergedData = [];
	if (allPoints.length > 0) {
		let current = { timestamp: allPoints[0].timestamp };
		allPoints.forEach(p => {
			if (Math.abs(p.timestamp - current.timestamp) < 60000) { // 1 minute window
				Object.assign(current, p);
			} else {
				mergedData.push(current);
				current = { ...p };
			}
		});
		mergedData.push(current);
	}

	return (
		<Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
			<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/dashboard')} sx={{ mb: 2 }}>
				Back to Dashboard
			</Button>

			<Paper sx={{ p: 3, mb: 3 }}>
				<Typography variant="h4" gutterBottom>Sleep Details: {date}</Typography>
				<Typography variant="h2" color="primary">{totalSleep.toFixed(1)} hrs</Typography>
				<Typography variant="subtitle1" color="text.secondary">Total Sleep</Typography>
			</Paper>

			<Grid container spacing={3}>
				{/* Sleep Stages Chart */}
				<Grid item xs={12} md={6}>
					<Paper sx={{ p: 3, height: 400 }}>
						<Typography variant="h6" gutterBottom>Sleep Stages (Hours)</Typography>
						<ResponsiveContainer width="100%" height="100%">
							<BarChart data={stagesData} layout="vertical">
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis type="number" />
								<YAxis dataKey="name" type="category" />
								<Tooltip />
								<Bar dataKey="value" fill="#8884d8">
									{stagesData.map((entry, index) => (
										<Cell key={`cell-${index}`} fill={entry.color} />
									))}
								</Bar>
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>

				{/* Distribution Pie Chart */}
				<Grid item xs={12} md={6}>
					<Paper sx={{ p: 3, height: 400 }}>
						<Typography variant="h6" gutterBottom>Distribution</Typography>
						<ResponsiveContainer width="100%" height="100%">
							<PieChart>
								<Pie
									data={stagesData}
									cx="50%"
									cy="50%"
									outerRadius={100}
									fill="#8884d8"
									dataKey="value"
									label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
								>
									{stagesData.map((entry, index) => (
										<Cell key={`cell-${index}`} fill={entry.color} />
									))}
								</Pie>
								<Tooltip />
							</PieChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>

				{/* Additional Metrics */}
				<Grid item xs={12} md={4}>
					<Paper sx={{ p: 3, textAlign: 'center' }}>
						<Typography variant="h6">Respiration</Typography>
						<Typography variant="h4" color="primary">
							{dto.averageRespirationValue ? `${Math.round(dto.averageRespirationValue)} brpm` : 'N/A'}
						</Typography>
						<Typography variant="body2" color="text.secondary">
							Min: {dto.lowestRespirationValue || '-'} | Max: {dto.highestRespirationValue || '-'}
						</Typography>
					</Paper>
				</Grid>

				<Grid item xs={12} md={4}>
					<Paper sx={{ p: 3, textAlign: 'center' }}>
						<Typography variant="h6">Sleep Score</Typography>
						<Typography variant="h4" color={dto.sleepScore > 80 ? "success.main" : "primary"}>
							{dto.sleepScore || 'N/A'}
						</Typography>
						<Typography variant="body2" color="text.secondary">
							Quality: {dto.sleepQualityTypePK || '-'}
						</Typography>
					</Paper>
				</Grid>

				<Grid item xs={12} md={4}>
					<Paper sx={{ p: 3, textAlign: 'center' }}>
						<Typography variant="h6">REM Sleep</Typography>
						<Typography variant="h4" color="#9c27b0">
							{((dto.remSleepSeconds || 0) / 3600).toFixed(1)} hrs
						</Typography>
					</Paper>
				</Grid>

				{/* Overlaid Metrics Chart */}
				<Grid item xs={12}>
					<Paper sx={{ p: 2, mb: 3, display: 'flex', gap: 3 }}>
						<Typography variant="h6" sx={{ mr: 2 }}>Chart Overlays:</Typography>
						<FormControlLabel control={<Checkbox checked={showHR} onChange={(e) => setShowHR(e.target.checked)} />} label="Heart Rate" />
						<FormControlLabel control={<Checkbox checked={showHRV} onChange={(e) => setShowHRV(e.target.checked)} />} label="HRV" />
						<FormControlLabel control={<Checkbox checked={showStress} onChange={(e) => setShowStress(e.target.checked)} />} label="Stress" />
					</Paper>

					<Paper sx={{ p: 3, height: 400 }}>
						<Typography variant="h6" gutterBottom>Sleep Metrics Overlay</Typography>
						<ResponsiveContainer width="100%" height="100%">
							<LineChart data={mergedData}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis
									dataKey="timestamp"
									type="number"
									domain={['auto', 'auto']}
									tickFormatter={(tick) => new Date(tick).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
								/>
								<YAxis yAxisId="left" domain={['auto', 'auto']} />
								<YAxis yAxisId="right" orientation="right" domain={[0, 100]} />
								<Tooltip labelFormatter={(label) => new Date(label).toLocaleString()} />
								<Legend />

								{/* Sleep Stage Highlights */}
								{/* We need start/end times for stages. The current data is aggregated. 
								    If we want to highlight stages on the timeline, we need the raw 'sleepLevels' or similar time-series data for stages.
								    The current 'stagesData' is just total duration.
								    Let's check if 'sleepLevels' is available in the DTO.
								    If not, we can't do precise highlighting.
								    Assuming we might have it or can get it.
								    For now, let's just add the ReferenceAreas if we had the data.
								    But wait, the user asked for "highlighted portions... for what sleep modes we were in".
								    This implies time-series stage data.
								    The 'dailySleepDTO' usually has 'sleepLevels' list.
								    Let's check the DTO structure in the logs or assume it's there.
								*/}
								{sleepData.sleep_data?.sleepLevels?.map((level, index) => {
									const startTime = new Date(level.startGMT).getTime();
									const endTime = new Date(level.endGMT).getTime();
									// Map numeric activityLevel to colors
									// 0: Unknown, 1: Deep, 2: Light, 3: REM, 4: Awake
									let color = '#e0e0e0';
									switch (level.activityLevel) {
										case 1: color = '#1976d2'; break; // Deep (Blue)
										case 2: color = '#4caf50'; break; // Light (Green)
										case 3: color = '#9c27b0'; break; // REM (Purple)
										case 0:
										case 4: color = '#ff9800'; break; // Awake (Orange)
										default: color = '#e0e0e0';
									}

									return (
										<ReferenceArea
											key={index}
											x1={startTime}
											x2={endTime}
											yAxisId="left"
											fill={color}
											fillOpacity={0.3}
										/>
									);
								})}

								{showHR && <Line yAxisId="left" type="monotone" dataKey="heartRate" stroke="#d32f2f" dot={false} name="Heart Rate (BPM)" connectNulls />}
								{showHRV && <Line yAxisId="left" type="monotone" dataKey="hrv" stroke="#9c27b0" dot={false} name="HRV (ms)" connectNulls />}
								{showStress && <Line yAxisId="right" type="monotone" dataKey="stress" stroke="#ff9800" dot={false} name="Stress (0-100)" connectNulls />}
							</LineChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>
		</Container>
	);
}

export default SleepDetailsPage;
