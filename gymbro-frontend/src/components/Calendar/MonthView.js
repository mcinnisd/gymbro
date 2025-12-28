import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const MonthView = ({ currentDate, events, onSelectDate }) => {
	const year = currentDate.getFullYear();
	const month = currentDate.getMonth();

	const firstDay = new Date(year, month, 1);
	const lastDay = new Date(year, month + 1, 0);
	const daysInMonth = lastDay.getDate();
	const startDayOfWeek = firstDay.getDay(); // 0 = Sunday

	const days = [];
	// Padding for previous month
	for (let i = 0; i < startDayOfWeek; i++) {
		days.push(null);
	}
	// Days of current month
	for (let i = 1; i <= daysInMonth; i++) {
		days.push(new Date(year, month, i));
	}

	const getEventsForDay = (date) => {
		if (!date) return [];
		const dateStr = date.toISOString().split('T')[0];
		return events.filter(e => e.date === dateStr);
	};

	return (
		<Box>
			<Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', mb: 2, textAlign: 'center' }}>
				{['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
					<Typography key={day} variant="caption" sx={{ color: 'text.secondary', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: 1 }}>{day}</Typography>
				))}
			</Box>
			<Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px', bgcolor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
				{days.map((date, idx) => {
					const dayEvents = getEventsForDay(date);
					const isToday = date && date.getDate() === new Date().getDate() && date.getMonth() === new Date().getMonth();

					return (
						<Box
							key={idx}
							sx={{
								minHeight: 120,
								p: 1,
								bgcolor: date ? 'background.paper' : 'rgba(0,0,0,0.2)', // Grid pattern
								cursor: date ? 'pointer' : 'default',
								position: 'relative',
								transition: 'all 0.2s',
								'&:hover': date ? { bgcolor: 'rgba(108, 99, 255, 0.08)' } : {},
								borderRight: '1px solid rgba(255,255,255,0.02)',
								borderBottom: '1px solid rgba(255,255,255,0.02)'
							}}
							onClick={() => date && onSelectDate(date)}
						>
							{date && (
								<>
									<Box sx={{ display: 'flex', justifyContent: isToday ? 'space-between' : 'flex-end', alignItems: 'center', mb: 0.5 }}>
										{isToday && (
											<Typography variant="caption" sx={{ color: 'secondary.main', fontWeight: 'bold' }}>TODAY</Typography>
										)}
										<Typography
											variant="body2"
											sx={{
												color: isToday ? 'secondary.main' : 'text.secondary',
												fontWeight: isToday ? 'bold' : 'normal',
												width: 24,
												height: 24,
												display: 'flex',
												alignItems: 'center',
												justifyContent: 'center',
												borderRadius: '50%',
												bgcolor: isToday ? 'rgba(0, 229, 255, 0.1)' : 'transparent'
											}}
										>
											{date.getDate()}
										</Typography>
									</Box>
									<Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
										{dayEvents.map(ev => (
											<Box
												key={ev.id}
												sx={{
													fontSize: '0.7rem',
													py: 0.5,
													px: 1,
													borderRadius: 1,
													...getEventStyle(ev.event_type),
													whiteSpace: 'nowrap',
													overflow: 'hidden',
													textOverflow: 'ellipsis',
													boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
												}}
											>
												{ev.title}
											</Box>
										))}
									</Box>
								</>
							)}
						</Box>
					);
				})}
			</Box>
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

export default MonthView;
