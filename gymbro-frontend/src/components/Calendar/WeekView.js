import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const WeekView = ({ currentDate, events, onSelectEvent }) => {
	// Calculate start of week (Sunday)
	const startOfWeek = new Date(currentDate);
	const day = startOfWeek.getDay();
	const diff = startOfWeek.getDate() - day;
	startOfWeek.setDate(diff);

	const days = [];
	for (let i = 0; i < 7; i++) {
		const d = new Date(startOfWeek);
		d.setDate(startOfWeek.getDate() + i);
		days.push(d);
	}

	const getEventsForDay = (date) => {
		const dateStr = date.toISOString().split('T')[0];
		return events.filter(e => e.date === dateStr);
	};

	return (
		<Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
			{days.map((date, idx) => {
				const dayEvents = getEventsForDay(date);
				const isToday = new Date().toDateString() === date.toDateString();

				return (
					<Paper
						key={idx}
						sx={{
							minHeight: 400,
							p: 2,
							bgcolor: isToday ? 'action.selected' : 'background.paper',
							border: isToday ? 1 : 0,
							borderColor: 'primary.main'
						}}
					>
						<Box sx={{ textAlign: 'center', mb: 2, borderBottom: 1, borderColor: 'divider', pb: 1 }}>
							<Typography variant="caption" color="text.secondary">
								{date.toLocaleDateString('en-US', { weekday: 'short' })}
							</Typography>
							<Typography variant="h6" color={isToday ? 'primary' : 'text.primary'}>
								{date.getDate()}
							</Typography>
						</Box>

						<Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
							{dayEvents.map(ev => (
								<Paper
									key={ev.id}
									sx={{
										p: 1,
										cursor: 'pointer',
										'&:hover': { opacity: 0.8 },
										...getEventStyle(ev.event_type)
									}}
									onClick={() => onSelectEvent(ev)}
								>
									<Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>{ev.title}</Typography>
									{ev.description && (
										<Typography variant="caption" sx={{ display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
											{ev.description}
										</Typography>
									)}
								</Paper>
							))}
						</Box>
					</Paper>
				);
			})}
		</Box>
	);
};

const getEventStyle = (type) => {
	switch (type) {
		case 'run': return { bgcolor: 'primary.main', color: 'primary.contrastText' };
		case 'strength': return { bgcolor: 'error.main', color: 'error.contrastText' };
		case 'rest': return { bgcolor: 'success.main', color: 'success.contrastText' };
		case 'race': return { bgcolor: 'warning.main', color: 'warning.contrastText' };
		default: return { bgcolor: 'grey.600', color: 'white' };
	}
};

export default WeekView;
