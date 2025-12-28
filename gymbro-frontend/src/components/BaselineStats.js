import React from 'react';
import { Card, CardContent, Typography, Grid, Chip, Box } from '@mui/material';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import TimelineIcon from '@mui/icons-material/Timeline';

function BaselineStats({ baselines }) {
	if (!baselines || !baselines.pbs) {
		return (
			<Card sx={{ height: '100%' }}>
				<CardContent>
					<Typography variant="h6" gutterBottom>
						Fitness Level
					</Typography>
					<Typography variant="body2" color="textSecondary">
						Sync more Garmin data to unlock calculated fitness baselines and Personal Bests.
					</Typography>
				</CardContent>
			</Card>
		);
	}

	const { pbs, volume } = baselines;

	return (
		<Card sx={{ height: '100%' }}>
			<CardContent>
				<Typography variant="h6" gutterBottom display="flex" alignItems="center">
					<DirectionsRunIcon sx={{ mr: 1 }} /> Fitness Baselines
				</Typography>

				<Grid container spacing={2}>
					<Grid item xs={12} md={6}>
						<Typography variant="subtitle2" color="primary" gutterBottom>
							Est. Personal Bests
						</Typography>
						<Box display="flex" flexWrap="wrap" gap={1}>
							{Object.entries(pbs).map(([dist, data]) => (
								<Chip
									key={dist}
									label={`${dist}: ${data.formatted_time}`}
									color="success"
									variant="outlined"
									size="small"
									title={`Date: ${data.date}`}
								/>
							))}
							{Object.keys(pbs).length === 0 && <Typography variant="caption">No PBs detected yet.</Typography>}
						</Box>

						{baselines.longest_run && (
							<Box mt={2}>
								<Typography variant="subtitle2" color="secondary" gutterBottom>
									Longest Run
								</Typography>
								<Chip
									label={`${baselines.longest_run.distance_km} km in ${baselines.longest_run.formatted_time}`}
									color="secondary"
									variant="outlined"
									size="small"
									title={`Date: ${baselines.longest_run.date}`}
								/>
							</Box>
						)}
					</Grid>

					<Grid item xs={12} md={6}>
						<Typography variant="subtitle2" color="primary" gutterBottom>
							Training Consistency
						</Typography>
						<Typography variant="body2">
							<strong>Avg Dist (4w):</strong> {volume?.avg_weekly_dist_4w} km/wk
						</Typography>
						<Typography variant="body2">
							<strong>Streak:</strong> {volume?.current_streak_weeks} weeks
						</Typography>
					</Grid>
				</Grid>

				<Box mt={2}>
					<Typography variant="caption" color="textSecondary">
						<TimelineIcon fontSize="inherit" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
						Calculated from {baselines.dataset_size} activities. Last processed: {new Date(baselines.last_processed_date).toLocaleDateString()}
					</Typography>
				</Box>

			</CardContent>
		</Card>
	);
}

export default BaselineStats;
