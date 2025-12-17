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

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

export default function AnalyticsSummary({ authToken }) {
	const { units, toggleUnits } = useContext(SettingsContext);
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
				const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/analytics/summary`, {
					headers: { 'Authorization': `Bearer ${authToken}` }
				});
				if (res.ok) {
					const json = await res.json();
					setData(json);
				} else {
					const text = await res.text();
					console.error("Analytics Error:", text);
					setError(`Failed to load analytics summary: ${res.status}`);
				}
			} catch (e) {
				console.error(e);
				setError("Error loading analytics");
			} finally {
				setLoading(false);
			}
		};
		fetchAnalytics();
	}, [authToken]);

	if (loading) return <CircularProgress />;
	if (error) return <Alert severity="error">{error}</Alert>;
	if (!data) return null;

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
		.map(([week, val]) => ({
			week: week.split('-')[1],
			distance: convertDist(val.distance).toFixed(1),
			duration: (val.duration / 3600).toFixed(1)
		}));

	// 3. Efficiency Trend
	const efficiencyData = data.performance.running.efficiency_trend.map(d => ({
		date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
		efficiency: d.efficiency.toFixed(2),
		speed: (isMetric ? (d.speed * 3.6) : (d.speed * 2.23694)).toFixed(1), // km/h or mph
		hr: d.hr
	}));

	// 4. Health Trends
	const vo2Data = data.health_trends.vo2_max.map(d => ({
		date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
		vo2: d.value
	}));

	const recoveryData = data.health_trends.recovery.map(d => ({
		date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
		rhr: d.rhr,
		hrv: d.hrv
	}));

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
										<Chip size="small" label={`Avg Pace: ${(data.performance.running.avg_pace_sec_km / 60).toFixed(2)} min/${distUnit}`} color="info" variant="outlined" />
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
										{convertElev(data.performance.hiking.total_elevation_gain).toFixed(0)} {elevUnit}
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
									<Bar dataKey="distance" fill="#8884d8" name={`Distance (${distUnit})`} />
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
								<LineChart data={efficiencyData}>
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
								<LineChart data={vo2Data}>
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
								<LineChart data={recoveryData}>
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
