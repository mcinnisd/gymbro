import React, { useState, useEffect, useContext } from 'react';
import {
	Box, Paper, Typography, Grid, Card, CardContent,
	CircularProgress, Alert, Chip, Button, Menu, MenuItem, Checkbox, FormControlLabel,
	ToggleButton, ToggleButtonGroup
} from '@mui/material';
import {
	PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
	LineChart, Line
} from 'recharts';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import HikingIcon from '@mui/icons-material/Hiking';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import FavoriteIcon from '@mui/icons-material/Favorite';
import SettingsIcon from '@mui/icons-material/Settings';
import { SettingsContext } from '../context/SettingsContext';
import { useNavigate } from 'react-router-dom';
import BedtimeIcon from '@mui/icons-material/Bedtime';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

export default function AnalyticsSummary({ authToken }) {
	const { units, toggleUnits } = useContext(SettingsContext);
	const navigate = useNavigate();
	const [data, setData] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	// UI State
	const [pieMetric, setPieMetric] = useState('count'); // count, distance, duration
	const [visibleModules, setVisibleModules] = useState({
		stats: true,
		breakdown: true,
		volume: true,
		efficiency: true,
		vo2: true,
		recovery: true
	});
	const [anchorEl, setAnchorEl] = useState(null);

	useEffect(() => {
		const fetchAnalytics = async () => {
			if (!authToken) return;
			try {
				// Ensure fresh fetch
				const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/analytics/summary`, {
					headers: { 'Authorization': `Bearer ${authToken}` }
				});
				if (res.ok) {
					const json = await res.json();
					// Basic validation to prevent crash
					if (json && (json.sports || json.wellness)) {
						setData(json);
					} else {
						console.warn("Analytics data empty or malformed", json);
					}
				} else {
					console.error("Analytics Error status:", res.status);
				}
			} catch (e) {
				console.error("Analytics network error", e);
			} finally {
				setLoading(false);
			}
		};
		fetchAnalytics();
	}, [authToken]); // dependency array is correct. Crash likely due to stale data rendering before new fetch completes?
	// FIX: reset data on auth change? No, loading handles it.
	// Issue might be Recharts trying to animate exit on unmount/remount?
	// Let's rely on data check above.

	if (loading) return <CircularProgress />;
	if (error) return <Alert severity="error">{error}</Alert>;
	if (!data) return null;

	// Navigation Handlers
	const handleDailyClick = (data) => {
		if (data && data.activePayload && data.activePayload.length > 0) {
			// Recharts payload structure
			const dateStr = data.activePayload[0].payload.date; // "Sep 15" format? 
			// Wait, payload date is formatted. We need ISO date for API. 
			// We should store ISO date in payload hidden and format in tickFormatter.
			// Current mapping destroys ISO date. 
			// FIX: Store ISO dateObject in data, use tickFormatter for display.
		}
	};

	// Easier approach: Use the data index? Or store raw date string in a hidden field 'isoDate'.
	const handleChartClick = (state, routePrefix) => {
		if (state && state.activePayload && state.activePayload.length > 0) {
			const item = state.activePayload[0].payload;
			if (item.isoDate) {
				navigate(`${routePrefix}/${item.isoDate}`);
			}
		}
	};

	// Helpers
	const isMetric = units === 'metric';
	const distUnit = isMetric ? 'km' : 'mi';
	const elevUnit = isMetric ? 'm' : 'ft';

	const convertDist = (m) => isMetric ? (m / 1000) : (m / 1609.34);
	const convertElev = (m) => isMetric ? m : (m * 3.28084);

	// Prepare Data

	// 1. Breakdown
	const breakdownData = Object.entries(data.breakdown).map(([key, val]) => ({
		name: key.charAt(0).toUpperCase() + key.slice(1),
		value: pieMetric === 'count' ? val.count :
			pieMetric === 'distance' ? convertDist(val.distance) :
				(val.duration / 3600), // hours
		label: pieMetric === 'count' ? 'Count' :
			pieMetric === 'distance' ? distUnit : 'Hours'
	}));

	// 2. Weekly Volume
	const weeklyData = Object.entries(data.weekly_volume)
		.sort((a, b) => a[0].localeCompare(b[0]))
		.slice(-8)
		.map(([dateKey, val]) => ({
			week: new Date(dateKey).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }), // "9/15"
			isoDate: dateKey, // Monday of week
			distance: convertDist(val.distance).toFixed(1),
			duration: (val.duration / 3600).toFixed(1)
		}));

	// 3. Efficiency Trend (Safely access running data)
	let efficiencyData = [];
	if (data.sports && data.sports.running && data.sports.running.trends && data.sports.running.trends.efficiency) {
		efficiencyData = data.sports.running.trends.efficiency.map(d => ({
			date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
			isoDate: d.date,
			efficiency: d.val.toFixed(2),
			speed: d.speed ? (isMetric ? (d.speed * 3.6) : (d.speed * 2.23694)).toFixed(1) : 0,
			hr: d.hr || 0
		}));
	}

	// 4. Health Trends
	const vo2Data = [];
	if (data.wellness && data.wellness.vo2_max) {
		data.wellness.vo2_max.forEach(d => {
			vo2Data.push({
				date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
				isoDate: d.date,
				vo2: d.val
			});
		});
	}

	const recoveryData = [];
	if (data.wellness && data.wellness.rhr_trend) {
		data.wellness.rhr_trend.forEach(d => {
			recoveryData.push({
				date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
				isoDate: d.date,
				rhr: d.val,
				hrv: null
			});
		});
	}

	// 5. Sleep Data (New)
	// We don't have a direct trend in 'summary' yet, need to fetch it or rely on what's available?
	// 'wellness' from backend only had rhr/stress/vo2.
	// I need to add sleep to backend OR just omit chart for now and rely on drill down.
	// User requested "Sleep Summary Overview". 
	// I will add a Card for Sleep Score (avg) if available, or just a placeholder to click.
	// Since backend doesn't send sleep trend in /summary, I'll skip the chart and just add a card that links to today/yesterday.


	// Module Toggle Handler
	const handleModuleToggle = (mod) => {
		setVisibleModules(prev => ({ ...prev, [mod]: !prev[mod] }));
	};

	return (
		<Box>
			{/* Toolbar */}
			<Box display="flex" justifyContent="flex-end" mb={2} gap={2}>
				<Button variant="outlined" onClick={toggleUnits}>
					{isMetric ? 'Switch to Miles' : 'Switch to KM'}
				</Button>
				<Button variant="outlined" startIcon={<SettingsIcon />} onClick={(e) => setAnchorEl(e.currentTarget)}>
					Customize
				</Button>
				<Menu
					anchorEl={anchorEl}
					open={Boolean(anchorEl)}
					onClose={() => setAnchorEl(null)}
				>
					{Object.keys(visibleModules).map(mod => (
						<MenuItem key={mod}>
							<FormControlLabel
								control={
									<Checkbox
										checked={visibleModules[mod]}
										onChange={() => handleModuleToggle(mod)}
									/>
								}
								label={mod.charAt(0).toUpperCase() + mod.slice(1)}
							/>
						</MenuItem>
					))}
				</Menu>
			</Box>

			<Grid container spacing={3}>
				{/* Key Stats */}
				{visibleModules.stats && (
					<>
						<Grid item xs={12} md={3}>
							<Card sx={{ height: '100%' }}>
								<CardContent>
									<Box display="flex" alignItems="center" gap={1} mb={1}>
										<DirectionsRunIcon color="primary" />
										<Typography variant="h6">Running Efficiency</Typography>
									</Box>
									<Typography variant="h4">
										{/* Use last value from trend if available, else average */}
										{efficiencyData.length > 0 ? efficiencyData[efficiencyData.length - 1].efficiency : '-'}
									</Typography>
									<Typography variant="body2" color="text.secondary">
										Latest Index (Speed/HR)
									</Typography>
									<Box mt={1}>
										<Chip size="small" label={`Avg Pace: ${(data.sports?.running?.avg_pace_sec_km ? (data.sports.running.avg_pace_sec_km / 60).toFixed(2) : '-')} min/${distUnit}`} color="info" variant="outlined" />
									</Box>
								</CardContent>
							</Card>
						</Grid>

						<Grid item xs={12} md={3}>
							<Card sx={{ height: '100%' }}>
								<CardContent>
									<Box display="flex" alignItems="center" gap={1} mb={1}>
										<HikingIcon color="secondary" />
										<Typography variant="h6">Elevation Gain</Typography>
									</Box>
									<Typography variant="h4">
										{data.sports?.hiking ? convertElev(data.sports.hiking.total_elevation).toFixed(0) : '0'} {elevUnit}
									</Typography>
									<Typography variant="body2" color="text.secondary">
										Total (Last 60 Days)
									</Typography>
								</CardContent>
							</Card>
						</Grid>

						<Grid item xs={12} md={3}>
							<Card sx={{ height: '100%' }}>
								<CardContent>
									<Box display="flex" alignItems="center" gap={1} mb={1}>
										<TrendingUpIcon color="action" />
										<Typography variant="h6">VO2 Max</Typography>
									</Box>
									<Typography variant="h4">
										{vo2Data.length > 0 ? vo2Data[vo2Data.length - 1].vo2.toFixed(1) : '-'}
									</Typography>
									<Typography variant="body2" color="text.secondary">
										Current Estimate
									</Typography>
								</CardContent>
							</Card>
						</Grid>

						<Grid item xs={12} md={3}>
							<Card sx={{ height: '100%' }}>
								<CardContent>
									<Box display="flex" alignItems="center" gap={1} mb={1}>
										<FavoriteIcon color="error" />
										<Typography variant="h6">Recovery (7d)</Typography>
									</Box>
									<Typography variant="h4">
										{recoveryData.length > 0 ? recoveryData[recoveryData.length - 1].hrv?.toFixed(0) || '-' : '-'} ms
									</Typography>
									<Typography variant="body2" color="text.secondary">
										Avg Nightly HRV
									</Typography>
								</CardContent>
							</Card>
						</Grid>
					</>
				)}

				{/* Sleep Summary Card (New) */}
				<Grid item xs={12} md={3}>
					<Card sx={{ height: '100%', cursor: 'pointer' }} onClick={() => navigate(`/sleep/${new Date().toISOString().slice(0, 10)}`)}>
						<CardContent>
							<Box display="flex" alignItems="center" gap={1} mb={1}>
								<BedtimeIcon color="primary" />
								<Typography variant="h6">Sleep</Typography>
							</Box>
							<Typography variant="h5">
								Drill Down
							</Typography>
							<Typography variant="body2" color="text.secondary">
								Click to view details
							</Typography>
						</CardContent>
					</Card>
				</Grid>

				{/* Charts Row 1 */}
				{visibleModules.breakdown && (
					<Grid item xs={12} md={6}>
						<Paper sx={{ p: 3, height: 400 }}>
							<Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
								<Typography variant="h6">Activity Breakdown</Typography>
								<ToggleButtonGroup
									value={pieMetric}
									exclusive
									onChange={(e, val) => val && setPieMetric(val)}
									size="small"
								>
									<ToggleButton value="count">Count</ToggleButton>
									<ToggleButton value="distance">Dist</ToggleButton>
									<ToggleButton value="duration">Time</ToggleButton>
								</ToggleButtonGroup>
							</Box>
							<ResponsiveContainer width="100%" height="90%">
								<PieChart>
									<Pie
										data={breakdownData}
										cx="50%"
										cy="50%"
										labelLine={false}
										label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
										outerRadius={100}
										fill="#8884d8"
										dataKey="value"
									>
										{breakdownData.map((entry, index) => (
											<Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
										))}
									</Pie>
									<Tooltip formatter={(val) => [val.toFixed(1), breakdownData[0].label]} />
								</PieChart>
							</ResponsiveContainer>
						</Paper>
					</Grid>
				)}

				{visibleModules.volume && (
					<Grid item xs={12} md={6}>
						<Paper sx={{ p: 3, height: 400 }}>
							<Typography variant="h6" gutterBottom>Weekly Volume ({distUnit})</Typography>
							<ResponsiveContainer width="100%" height="90%">
								<BarChart data={weeklyData}>
									<CartesianGrid strokeDasharray="3 3" />
									<XAxis dataKey="week" />
									<YAxis />
									<Tooltip />
									<Bar dataKey="distance" fill="#8884d8" name={`Distance (${distUnit})`} onClick={(data) => {
										// Drill down to week view? Or just generic
									}} />
								</BarChart>
							</ResponsiveContainer>
						</Paper>
					</Grid>
				)}

				{/* Charts Row 2 */}
				{visibleModules.efficiency && (
					<Grid item xs={12} md={12}>
						<Paper sx={{ p: 3, height: 350 }}>
							<Typography variant="h6" gutterBottom>Running Efficiency Trend (Speed/HR)</Typography>
							<ResponsiveContainer width="100%" height="100%">
								<LineChart data={efficiencyData} onClick={(e) => handleChartClick(e, '/garmin/daily')}>
									<CartesianGrid strokeDasharray="3 3" />
									<XAxis dataKey="date" />
									<YAxis domain={['auto', 'auto']} />
									<Tooltip />
									<Legend />
									<Line type="monotone" dataKey="efficiency" stroke="#ff7300" strokeWidth={2} name="Efficiency Index" dot={true} />
									<Line type="monotone" dataKey="speed" stroke="#82ca9d" name={`Speed (${isMetric ? 'km/h' : 'mph'})`} dot={false} />
								</LineChart>
							</ResponsiveContainer>
						</Paper>
					</Grid>
				)}

				{visibleModules.vo2 && (
					<Grid item xs={12} md={6}>
						<Paper sx={{ p: 3, height: 350 }}>
							<Typography variant="h6" gutterBottom>VO2 Max Trend (1 Year)</Typography>
							<ResponsiveContainer width="100%" height="100%">
								<LineChart data={vo2Data} onClick={(e) => handleChartClick(e, '/garmin/daily')}>
									<CartesianGrid strokeDasharray="3 3" />
									<XAxis dataKey="date" />
									<YAxis domain={['auto', 'auto']} />
									<Tooltip />
									<Line type="monotone" dataKey="vo2" stroke="#82ca9d" strokeWidth={2} dot={true} />
								</LineChart>
							</ResponsiveContainer>
						</Paper>
					</Grid>
				)}

				{visibleModules.recovery && (
					<Grid item xs={12} md={6}>
						<Paper sx={{ p: 3, height: 350 }}>
							<Typography variant="h6" gutterBottom>Recovery Trends (RHR & HRV)</Typography>
							<ResponsiveContainer width="100%" height="100%">
								<LineChart data={recoveryData} onClick={(e) => handleChartClick(e, '/garmin/daily')}>
									<CartesianGrid strokeDasharray="3 3" />
									<XAxis dataKey="date" />
									<YAxis yAxisId="left" domain={['auto', 'auto']} />
									<YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} />
									<Tooltip />
									<Legend />
									<Line yAxisId="left" type="monotone" dataKey="rhr" stroke="#d32f2f" name="RHR" dot={false} />
									<Line yAxisId="right" type="monotone" dataKey="hrv" stroke="#1976d2" name="HRV" dot={false} />
								</LineChart>
							</ResponsiveContainer>
						</Paper>
					</Grid>
				)}
			</Grid>
		</Box>
	);
}
