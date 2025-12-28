import React, { useState, useContext, useEffect } from 'react';
import {
	Container, Typography, Button, Box, Paper,
	CircularProgress, Fade, Grow, useTheme, Card, CardContent, Alert
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import SportsScoreIcon from '@mui/icons-material/SportsScore';
import ChatIcon from '@mui/icons-material/Chat';
import AssignmentIcon from '@mui/icons-material/Assignment';
import GlassPaper from '../components/GlassPaper';

function CoachPage() {
	const { authToken } = useContext(AuthContext);
	const navigate = useNavigate();
	const theme = useTheme();
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');
	const [coachStatus, setCoachStatus] = useState('not_started');
	const [interviewChatId, setInterviewChatId] = useState(null);

	useEffect(() => {
		const fetchStatus = async () => {
			if (!authToken) return;
			try {
				const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/auth/profile`, {
					headers: { 'Authorization': `Bearer ${authToken}` }
				});
				if (response.ok) {
					const data = await response.json();
					// Fetch user status from profile or separate endpoint
					// For now, let's assume it's in the profile goals or a new field
					// Actually, I added coach_status to the users table.
					// I should update the /auth/profile route to include it.
					// But for now, let's just check if they have an interview_chat_id
					if (data.profile.coach_status) {
						setCoachStatus(data.profile.coach_status);
					}
					if (data.profile.interview_chat_id) {
						setInterviewChatId(data.profile.interview_chat_id);
					}
				}
			} catch (err) {
				console.error("Error fetching coach status:", err);
			} finally {
				setLoading(false);
			}
		};
		fetchStatus();
	}, [authToken]);

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
				console.log("Start interview success:", data);
				if (data.chat_id) {
					// Update local state to show "Continue Interview"
					setInterviewChatId(data.chat_id);
					setCoachStatus('interview_in_progress');

					// Open in a new tab
					const url = `/chats/${data.chat_id}`;
					window.open(url, '_blank');
				} else {
					setError('Server did not return a chat ID.');
				}
			} else {
				const errData = await response.json();
				setError(errData.error || 'Failed to start interview');
			}
		} catch (err) {
			setError('Network error. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handleGeneratePlan = async () => {
		setLoading(true);
		setError('');
		try {
			const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/coach/generate_plan`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${authToken}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ chat_id: interviewChatId })
			});

			if (response.ok) {
				const data = await response.json();
				setCoachStatus('plan_generated');
				alert("Training plan generated! Check your dashboard.");
			} else {
				const errData = await response.json();
				setError(errData.error || 'Failed to generate plan');
			}
		} catch (err) {
			setError('Network error. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	// Moved import to top


	if (loading && coachStatus === 'not_started') {
		return (
			<Box display="flex" justifyContent="center" alignItems="center" height="80vh">
				<CircularProgress />
			</Box>
		);
	}

	return (
		<Container maxWidth="md" sx={{ py: 8 }}>
			<Fade in timeout={800}>
				<GlassPaper sx={{ textAlign: 'center', p: 6 }}>
					<SportsScoreIcon sx={{ fontSize: 80, color: 'primary.main', mb: 3 }} />
					<Typography variant="h3" gutterBottom sx={{ fontWeight: 800 }}>
						AI Running Coach
					</Typography>

					<Typography variant="h6" color="text.secondary" paragraph sx={{ mb: 4, maxWidth: '600px', mx: 'auto' }}>
						{coachStatus === 'not_started' && "Ready to transform your running? Start your conversational interview to get a personalized plan."}
						{coachStatus === 'interview_in_progress' && "You have an interview in progress. Continue your conversation to finish your profile."}
						{coachStatus === 'interview_completed' && "Interview complete! We have everything we need to build your plan."}
						{coachStatus === 'plan_generated' && "Your personalized training plan is ready!"}
					</Typography>

					{error && <Alert severity="error" sx={{ mb: 3, borderRadius: '12px' }}>{error}</Alert>}

					<Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
						{coachStatus === 'not_started' && (
							<Button
								variant="contained"
								size="large"
								onClick={handleStartInterview}
								disabled={loading}
								sx={{ px: 6, py: 2, borderRadius: '40px', fontSize: '1.2rem', fontWeight: 700 }}
							>
								{loading ? <CircularProgress size={24} color="inherit" /> : "Start Interview"}
							</Button>
						)}

						{coachStatus === 'interview_in_progress' && (
							<Button
								variant="contained"
								size="large"
								startIcon={<ChatIcon />}
								onClick={() => window.open(`/chats/${interviewChatId}`, '_blank')}
								sx={{ px: 6, py: 2, borderRadius: '40px', fontSize: '1.2rem', fontWeight: 700 }}
							>
								Continue Interview
							</Button>
						)}

						{coachStatus === 'interview_completed' && (
							<Button
								variant="contained"
								size="large"
								color="success"
								startIcon={<AssignmentIcon />}
								onClick={handleGeneratePlan}
								disabled={loading}
								sx={{ px: 6, py: 2, borderRadius: '40px', fontSize: '1.2rem', fontWeight: 700 }}
							>
								{loading ? <CircularProgress size={24} color="inherit" /> : "Generate Training Plan"}
							</Button>
						)}

						{coachStatus === 'plan_generated' && (
							<Button
								variant="contained"
								size="large"
								onClick={() => navigate('/dashboard')}
								sx={{ px: 6, py: 2, borderRadius: '40px', fontSize: '1.2rem', fontWeight: 700 }}
							>
								View My Plan
							</Button>
						)}

						<Button
							variant="text"
							onClick={() => navigate('/onboarding')}
							sx={{ color: 'text.secondary' }}
						>
							Update Integrations & Profile
						</Button>
					</Box>
				</GlassPaper>
			</Fade>
		</Container>
	);
}

export default CoachPage;

