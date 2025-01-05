// src/components/ActivitiesTable.js
import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Typography } from '@mui/material';

function ActivitiesTable() {
  const [activities, setActivities] = useState([]);
  const { authToken } = useContext(AuthContext);

  useEffect(() => {
    const fetchActivities = async () => {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/activities/list`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        alert('Failed to fetch activities');
        return;
      }

      const data = await response.json();
      setActivities(data.activities);
    };

    fetchActivities();
  }, [authToken]);

  return (
    <TableContainer component={Paper} sx={{ marginTop: 4 }}>
      <Typography variant="h6" gutterBottom sx={{ padding: 2 }}>
        Your Activities
      </Typography>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Date</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Duration (mins)</TableCell>
            <TableCell>Calories Burned</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {activities.map((activity) => (
            <TableRow key={activity.id}>
              <TableCell>{new Date(activity.date).toLocaleDateString()}</TableCell>
              <TableCell>{activity.type}</TableCell>
              <TableCell>{activity.duration}</TableCell>
              <TableCell>{activity.calories}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default ActivitiesTable;