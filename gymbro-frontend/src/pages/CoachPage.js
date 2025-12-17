import React, { useState, useContext } from 'react';
import { Container, Typography, Button, Box, Paper, CircularProgress } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import SportsScoreIcon from '@mui/icons-material/SportsScore';

function CoachPage() {
	const { authToken } = useContext(AuthContext);
	const navigate = useNavigate();
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState('');

	const handleStartInterview = async () => {
		setLoading(true);
		setError('');
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
				console.log("Interview started:", data);
				// Redirect to chats page, selecting the new chat
				// We might need to pass state or just let ChatsPage fetch latest
				navigate('/chats');
			} else {
				const errData = await response.json();
				setError(errData.error || 'Failed to start interview');
			}
		} catch (err) {
			console.error("Error starting interview:", err);
			setError('Network error. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	return (
		<Container maxWidth="md" sx={{ mt: 8 }}>
			<Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
				<SportsScoreIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
				<Typography variant="h4" gutterBottom>
					AI Running Coach
				</Typography>
				<Typography variant="body1" color="text.secondary" paragraph>
					Ready to take your training to the next level? Start an interview with your AI Coach to generate a personalized training plan based on your goals, history, and Garmin data.
				</Typography>

				{error && (
					<Typography color="error" sx={{ mb: 2 }}>
						{error}
					</Typography>
				)}

				<Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
					<Button
						variant="contained"
						size="large"
						onClick={handleStartInterview}
						disabled={loading}
						sx={{ minWidth: 200 }}
					>
						{loading ? <CircularProgress size={24} color="inherit" /> : "Start Interview"}
					</Button>

					<Button
						variant="outlined"
						size="medium"
						onClick={() => navigate('/onboarding')}
						sx={{ minWidth: 200 }}
					>
						Setup Integrations & Profile
					</Button>
				</Box>
			</Paper>
		</Container>
	);
}

export default CoachPage;
