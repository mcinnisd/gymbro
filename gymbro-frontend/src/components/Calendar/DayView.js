import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button, Paper, Chip, Container } from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import AddIcon from '@mui/icons-material/Add';

const DayView = ({ currentDate, events, onAddClick }) => {
	const navigate = useNavigate();
	const dateStr = currentDate.toISOString().split('T')[0];
	const dayEvents = events.filter(e => e.date === dateStr);

	const handleTalkToCoach = (event) => {
		navigate('/chats', { state: { initialMessage: `I want to discuss my ${event.title} on ${event.date}` } });
	};

	return (
		<Container maxWidth="md">
			<Box sx={{ textAlign: 'center', mb: 4 }}>
				<Typography variant="h4" color="text.primary">
					{currentDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
				</Typography>
			</Box>

			<Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
				{dayEvents.length === 0 ? (
					<Typography align="center" color="text.secondary" sx={{ py: 5 }}>
						No events scheduled for this day.
					</Typography>
				) : (
					dayEvents.map(ev => (
						<Paper
							key={ev.id}
							sx={{
								p: 3,
								borderLeft: 6,
								borderColor: getEventColor(ev.event_type),
								bgcolor: 'background.paper'
							}}
						>
							<Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
								<Box>
									<Typography variant="h5" gutterBottom>{ev.title}</Typography>
									<Typography variant="overline" display="block" color="text.secondary" sx={{ lineHeight: 1 }}>
										{ev.event_type}
									</Typography>
									<Typography variant="body1" color="text.secondary" sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
										{ev.description || "No description provided."}
									</Typography>
								</Box>
								<Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, alignItems: 'flex-end' }}>
									<Chip
										label={ev.status}
										color={getStatusColor(ev.status)}
										size="small"
										sx={{ textTransform: 'uppercase', fontWeight: 'bold' }}
									/>
									<Button
										variant="outlined"
										size="small"
										startIcon={<ChatIcon />}
										onClick={() => handleTalkToCoach(ev)}
										sx={{ mt: 1 }}
									>
										Talk to Coach
									</Button>
								</Box>
							</Box>
						</Paper>
					))
				)}
			</Box>

			<Box sx={{ mt: 4, textAlign: 'center' }}>
				<Button
					variant="contained"
					size="large"
					startIcon={<AddIcon />}
					onClick={onAddClick}
				>
					Add Workout
				</Button>
			</Box>
		</Container>
	);
};

const getEventColor = (type) => {
	switch (type) {
		case 'run': return 'primary.main';
		case 'strength': return 'error.main';
		case 'rest': return 'success.main';
		case 'race': return 'warning.main';
		default: return 'grey.500';
	}
};

const getStatusColor = (status) => {
	switch (status) {
		case 'completed': return 'success';
		case 'skipped': return 'error';
		default: return 'default';
	}
};

export default DayView;
