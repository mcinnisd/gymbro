// gymbro-frontend/src/pages/DashboardPage.js
import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { Box, Typography, Grid, Container, CircularProgress, Chip, LinearProgress, Button, Alert } from '@mui/material';
import GlassPaper from '../components/GlassPaper';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, LineChart, Line } from 'recharts';
import ActivitiesTable from '../components/ActivitiesTable';
import AnalyticsSummary from '../components/AnalyticsSummary';
import BaselineStats from '../components/BaselineStats';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ListIcon from '@mui/icons-material/List';
import SyncIcon from '@mui/icons-material/Sync';


function DashboardPage() {
  const navigate = useNavigate();
  const { authToken } = useContext(AuthContext);
  const [globalStats, setGlobalStats] = useState(null);
  const [dailyStats, setDailyStats] = useState([]);
  const [baselines, setBaselines] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState('summary');
  const [syncing, setSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);
  const [syncError, setSyncError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!authToken) return;

      try {
        // Fetch Global Stats
        const statsRes = await fetch(`${process.env.REACT_APP_API_BASE_URL}/activities/stats`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (statsRes.ok) setGlobalStats(await statsRes.json());

        // Fetch Baselines
        const baseRes = await fetch(`${process.env.REACT_APP_API_BASE_URL}/analytics/baselines`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (baseRes.ok) setBaselines(await baseRes.json());

        // Fetch Daily Stats
        const dailyRes = await fetch(`${process.env.REACT_APP_API_BASE_URL}/activities/daily_stats`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (dailyRes.ok) setDailyStats(await dailyRes.json());

      } catch (error) {
        console.error("Error fetching dashboard data:", error);
      }
    };

    fetchData();
  }, [authToken]);

  const handleForceSync = async () => {
    setSyncing(true);
    setSyncProgress(0);
    setSyncError(null);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/garmin/sync`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ force: true })
      });
      if (!response.ok) throw new Error('Failed to trigger sync');

      // Optionally poll for status
      const interval = setInterval(async () => {
        const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/garmin/status`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.garmin_sync_progress) {
            setSyncProgress(data.garmin_sync_progress);
          }

          if (data.garmin_sync_status === 'synced') {
            setSyncing(false);
            setSyncProgress(100);
            clearInterval(interval);
            window.location.reload(); // Refresh to show new data
          } else if (data.garmin_sync_status === 'error') {
            setSyncing(false);
            setSyncError(data.garmin_last_sync_error);
            clearInterval(interval);
          }
        }
      }, 2000); // Poll faster (2s) now that rate limit is fixed

    } catch (err) {
      setSyncError(err.message);
      setSyncing(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h4">
          Dashboard
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={syncing ? <CircularProgress size={20} /> : <SyncIcon />}
            onClick={handleForceSync}
            disabled={syncing}
          >
            {syncing ? `Syncing ${syncProgress}%` : 'Sync Now'}
          </Button>
          {syncing && (
            <Box sx={{ width: '150px' }}>
              <LinearProgress variant="determinate" value={syncProgress} />
            </Box>
          )}
        </Box>
      </Box>

      {syncError && (
        <Alert severity="error" sx={{ mb: 2, borderRadius: '12px' }}>
          Garmin Sync Error: {syncError}. Please check your credentials in Profile.
        </Alert>
      )}

      {/* Main View Toggles */}
      <Box sx={{ mb: 3, display: 'flex', gap: 1 }}>
        <Chip
          label="Summary"
          clickable
          color={selectedMetric === 'summary' ? 'primary' : 'default'}
          onClick={() => setSelectedMetric('summary')}
          icon={<TrendingUpIcon />}
        />
        <Chip
          label="Activities & Daily"
          clickable
          color={selectedMetric === 'activities' ? 'primary' : 'default'}
          onClick={() => setSelectedMetric('activities')}
          icon={<ListIcon />}
        />
      </Box>

      {/* Summary View */}
      {selectedMetric === 'summary' && (
        <AnalyticsSummary authToken={authToken} />
      )}

      {/* Activities View */}
      {selectedMetric === 'activities' && (
        <>
          {/* Fitness Baselines */}
          {baselines && (
            <Box mb={3}>
              <BaselineStats baselines={baselines} />
            </Box>
          )}

          {/* Global Stats Cards */}
          {globalStats && (
            <Grid container spacing={3} sx={{ mb: 4 }}>
              <Grid item xs={12} sm={6} md={3}>
                <GlassPaper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140 }}>
                  <Typography component="h2" variant="h6" color="primary" gutterBottom>
                    Total Distance
                  </Typography>
                  <Typography component="p" variant="h4">
                    {globalStats.total_distance_km} km
                  </Typography>
                  <Typography color="text.secondary" sx={{ flex: 1 }}>
                    All time
                  </Typography>
                </GlassPaper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <GlassPaper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140 }}>
                  <Typography component="h2" variant="h6" color="primary" gutterBottom>
                    Total Activities
                  </Typography>
                  <Typography component="p" variant="h4">
                    {globalStats.total_activities}
                  </Typography>
                </GlassPaper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <GlassPaper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140 }}>
                  <Typography component="h2" variant="h6" color="primary" gutterBottom>
                    Avg Distance
                  </Typography>
                  <Typography component="p" variant="h4">
                    {globalStats.avg_distance_km} km
                  </Typography>
                </GlassPaper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <GlassPaper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 140 }}>
                  <Typography component="h2" variant="h6" color="primary" gutterBottom>
                    Avg Duration
                  </Typography>
                  <Typography component="p" variant="h4">
                    {globalStats.avg_duration_min} min
                  </Typography>
                </GlassPaper>
              </Grid>
            </Grid>
          )}

          {/* Daily Charts */}
          <GlassPaper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>Daily Metrics</Typography>
            {/* We can reuse the metric toggle logic here if we want, or just show all/stacked. 
                    For simplicity, let's keep the charts but maybe simplify the toggle or just show Steps by default.
                    Actually, let's keep the internal toggle for charts if user wants to see daily details.
                */}
            <DailyCharts dailyStats={dailyStats} navigate={navigate} />
          </GlassPaper>

          <ActivitiesTable />
        </>
      )}
    </Container>
  );
}

// Helper component for Daily Charts to keep main component clean
function DailyCharts({ dailyStats, navigate }) {
  const [metric, setMetric] = useState('Steps');

  return (
    <>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        {['Steps', 'Heart Rate', 'Sleep'].map((m) => (
          <Chip
            key={m}
            label={m}
            onClick={() => setMetric(m)}
            color={metric === m ? 'primary' : 'default'}
            variant={metric === m ? 'filled' : 'outlined'}
            clickable
          />
        ))}
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        {metric === 'Steps' && (
          <BarChart width={800} height={300} data={dailyStats}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="steps" fill="#82ca9d" name="Steps" />
          </BarChart>
        )}

        {metric === 'Heart Rate' && (
          <LineChart width={800} height={300} data={dailyStats}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis domain={['dataMin - 5', 'dataMax + 5']} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="resting_hr" stroke="#8884d8" name="Resting HR" />
            <Line type="monotone" dataKey="min_hr" stroke="#82ca9d" name="Min HR" />
            <Line type="monotone" dataKey="max_hr" stroke="#ff7300" name="Max HR" />
          </LineChart>
        )}

        {metric === 'Sleep' && (
          <BarChart
            width={800}
            height={300}
            data={dailyStats}
            onClick={(data) => {
              if (data && data.activePayload && data.activePayload.length > 0) {
                const date = data.activePayload[0].payload.date;
                navigate(`/sleep/${date}`);
              }
            }}
            style={{ cursor: 'pointer' }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis label={{ value: 'Hours', angle: -90, position: 'insideLeft' }} />
            <Tooltip cursor={{ fill: 'transparent' }} />
            <Legend />
            <Bar dataKey="sleep_hours" fill="#8884d8" name="Sleep Duration (Hours)" />
          </BarChart>
        )}
      </Box>
    </>
  );
}

export default DashboardPage;