// gymbro-frontend/src/pages/DashboardPage.js
import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { Box, Typography, Grid, Paper } from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, LineChart, Line } from 'recharts';
import ActivitiesTable from '../components/ActivitiesTable';

function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const { authToken } = useContext(AuthContext);

  useEffect(() => {
    const fetchSummary = async () => {
      const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';
      const response = await fetch(`${API_BASE_URL}/activities`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        alert('Failed to fetch summary data');
        return;
      }

      const data = await response.json();
      setSummary(data);
    };

    fetchSummary();
  }, [authToken]);

  if (!summary) {
    return <Typography>Loading...</Typography>;
  }

  // Example data for charts (replace with actual data)
  const workoutData = [
    { day: 'Mon', workouts: 1 },
    { day: 'Tue', workouts: 2 },
    { day: 'Wed', workouts: 1 },
    { day: 'Thu', workouts: 3 },
    { day: 'Fri', workouts: 2 },
    { day: 'Sat', workouts: 4 },
    { day: 'Sun', workouts: 0 },
  ];

  const caloriesData = [
    { day: 'Mon', calories: 500 },
    { day: 'Tue', calories: 700 },
    { day: 'Wed', calories: 600 },
    { day: 'Thu', calories: 800 },
    { day: 'Fri', calories: 650 },
    { day: 'Sat', calories: 900 },
    { day: 'Sun', calories: 400 },
  ];

  return (
    <Box sx={{ flexGrow: 1, padding: 3 }}>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={4}>
          <Paper elevation={3} sx={{ padding: 2 }}>
            <Typography variant="h6">Total Workouts</Typography>
            <Typography variant="h4">{summary.workouts}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper elevation={3} sx={{ padding: 2 }}>
            <Typography variant="h6">Calories Burned</Typography>
            <Typography variant="h4">{summary.calories_burned}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper elevation={3} sx={{ padding: 2 }}>
            <Typography variant="h6">Active Days</Typography>
            <Typography variant="h4">{summary.active_days}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper elevation={3} sx={{ padding: 2 }}>
            <Typography variant="h6" gutterBottom>
              Workouts per Day
            </Typography>
            <BarChart width={500} height={300} data={workoutData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="workouts" fill="#1976d2" />
            </BarChart>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper elevation={3} sx={{ padding: 2 }}>
            <Typography variant="h6" gutterBottom>
              Calories Burned per Day
            </Typography>
            <LineChart width={500} height={300} data={caloriesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="calories" stroke="#dc004e" />
            </LineChart>
          </Paper>
        </Grid>
      </Grid>
      <ActivitiesTable />
    </Box>
  );
}

export default DashboardPage;