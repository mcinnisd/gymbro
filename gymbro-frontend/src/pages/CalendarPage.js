import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import MonthView from '../components/Calendar/MonthView';
import WeekView from '../components/Calendar/WeekView';
import DayView from '../components/Calendar/DayView';
import {
	Box, Container, Typography, Button, ButtonGroup,
	Paper, IconButton, Dialog, DialogTitle, DialogContent,
	DialogActions, TextField, MenuItem, Select, FormControl, InputLabel
} from '@mui/material';
import ArrowBackIosIcon from '@mui/icons-material/ArrowBackIos';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import AddIcon from '@mui/icons-material/Add';
import GlassPaper from '../components/GlassPaper';

const CalendarPage = () => {
	const { authToken } = useContext(AuthContext); // Fixed: token -> authToken
	const [currentDate, setCurrentDate] = useState(new Date());
	const [view, setView] = useState('month'); // 'month', 'week', 'day'
	const [events, setEvents] = useState([]);
	const [loading, setLoading] = useState(false);

	// Add Event Dialog State
	const [openAddDialog, setOpenAddDialog] = useState(false);
	const [newEvent, setNewEvent] = useState({
		title: '',
		date: new Date().toISOString().split('T')[0],
		event_type: 'run',
		description: ''
	});

	useEffect(() => {
		fetchEvents();
	}, [currentDate, view, authToken]);

	const fetchEvents = async () => {
		if (!authToken) return;
		setLoading(true);
		try {
			// Calculate start/end dates based on view
			let start = new Date(currentDate);
			let end = new Date(currentDate);

			if (view === 'month') {
				start.setDate(1);
				end.setMonth(end.getMonth() + 1);
				end.setDate(0);
			} else if (view === 'week') {
				const day = start.getDay();
				const diff = start.getDate() - day + (day === 0 ? -6 : 1);
				start.setDate(diff);
				end.setDate(start.getDate() + 6);
			} else {
				start.setDate(1);
				end.setMonth(end.getMonth() + 1);
				end.setDate(0);
			}

			const startStr = start.toISOString().split('T')[0];
			const endStr = end.toISOString().split('T')[0];

			const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/calendar/events?start_date=${startStr}&end_date=${endStr}`, {
				headers: { Authorization: `Bearer ${authToken}` }
			});
			const data = await res.json();
			if (data.events) {
				setEvents(data.events);
			}
		} catch (err) {
			console.error("Error fetching events:", err);
		} finally {
			setLoading(false);
		}
	};

	const handlePrev = () => {
		const newDate = new Date(currentDate);
		if (view === 'month') newDate.setMonth(newDate.getMonth() - 1);
		else if (view === 'week') newDate.setDate(newDate.getDate() - 7);
		else newDate.setDate(newDate.getDate() - 1);
		setCurrentDate(newDate);
	};

	const handleNext = () => {
		const newDate = new Date(currentDate);
		if (view === 'month') newDate.setMonth(newDate.getMonth() + 1);
		else if (view === 'week') newDate.setDate(newDate.getDate() + 7);
		else newDate.setDate(newDate.getDate() + 1);
		setCurrentDate(newDate);
	};

	const handleToday = () => {
		setCurrentDate(new Date());
	};

	const handleAddEvent = async () => {
		try {
			const res = await fetch(`${process.env.REACT_APP_API_BASE_URL}/calendar/events`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${authToken}`
				},
				body: JSON.stringify(newEvent)
			});

			if (res.ok) {
				setOpenAddDialog(false);
				fetchEvents(); // Refresh
				setNewEvent({
					title: '',
					date: new Date().toISOString().split('T')[0],
					event_type: 'run',
					description: ''
				});
			} else {
				alert("Failed to create event");
			}
		} catch (err) {
			console.error(err);
		}
	};

	return (
		<Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
			<GlassPaper
				sx={{
					p: 3,
					mb: 3,
				}}
			>
				{/* Header Section */}
				<Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, justifyContent: 'space-between', alignItems: 'center', mb: 4, gap: 2 }}>
					<Box>
						<Typography variant="h4" sx={{ fontWeight: 700, background: 'linear-gradient(45deg, #6C63FF, #00E5FF)', backgroundClip: 'text', textFillColor: 'transparent', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
							Training Calendar
						</Typography>
						<Typography variant="body1" color="text.secondary">
							Manage your upcoming workouts and goals
						</Typography>
					</Box>

					<Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
						<ButtonGroup variant="contained" sx={{ boxShadow: '0 4px 14px 0 rgba(0,0,0,0.3)' }}>
							<Button onClick={() => setView('month')} color={view === 'month' ? 'primary' : 'inherit'}>Month</Button>
							<Button onClick={() => setView('week')} color={view === 'week' ? 'primary' : 'inherit'}>Week</Button>
							<Button onClick={() => setView('day')} color={view === 'day' ? 'primary' : 'inherit'}>Day</Button>
						</ButtonGroup>

						<Button
							variant="contained"
							startIcon={<AddIcon />}
							onClick={() => setOpenAddDialog(true)}
							sx={{ background: 'linear-gradient(45deg, #00E5FF 30%, #00B0FF 90%)', color: '#000', fontWeight: 'bold' }}
						>
							Add Event
						</Button>
					</Box>
				</Box>

				{/* Navigation & Calendar */}
				<Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
					<IconButton onClick={handlePrev} size="large" sx={{ border: '1px solid rgba(255,255,255,0.1)' }}><ArrowBackIosIcon fontSize="small" /></IconButton>
					<Typography variant="h5" sx={{ minWidth: 200, textAlign: 'center', fontWeight: 600 }}>
						{currentDate.toLocaleDateString('default', { month: 'long', year: 'numeric' })}
					</Typography>
					<IconButton onClick={handleNext} size="large" sx={{ border: '1px solid rgba(255,255,255,0.1)' }}><ArrowForwardIosIcon fontSize="small" /></IconButton>
					<Button onClick={handleToday} variant="text" size="small" sx={{ position: 'absolute', right: 40, display: { xs: 'none', md: 'block' } }}>Jump to Today</Button>
				</Box>

				<Box sx={{ minHeight: 600, mt: 3 }}>
					{loading ? (
						<Typography align="center" sx={{ mt: 10, color: 'text.secondary' }}>Loading calendar...</Typography>
					) : (
						<>
							{view === 'month' && <MonthView currentDate={currentDate} events={events} onSelectDate={(d) => { setCurrentDate(d); setView('day'); }} />}
							{view === 'week' && <WeekView currentDate={currentDate} events={events} />}
							{view === 'day' && <DayView currentDate={currentDate} events={events} onAddClick={() => setOpenAddDialog(true)} />}
						</>
					)}
				</Box>
			</GlassPaper>

			{/* Add Event Dialog */}
			<Dialog
				open={openAddDialog}
				onClose={() => setOpenAddDialog(false)}
				PaperProps={{
					sx: {
						borderRadius: 3,
						background: '#1A202C',
						border: '1px solid #2D3748'
					}
				}}
			>
				<DialogTitle sx={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>Add Training Event</DialogTitle>
				<DialogContent sx={{ mt: 2 }}>
					<Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1, minWidth: 350 }}>
						<TextField
							label="Event Title"
							fullWidth
							variant="outlined"
							value={newEvent.title}
							onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
						/>
						<Box sx={{ display: 'flex', gap: 2 }}>
							<TextField
								label="Date"
								type="date"
								fullWidth
								InputLabelProps={{ shrink: true }}
								value={newEvent.date}
								onChange={(e) => setNewEvent({ ...newEvent, date: e.target.value })}
							/>
							<FormControl fullWidth>
								<InputLabel>Type</InputLabel>
								<Select
									value={newEvent.event_type}
									label="Type"
									onChange={(e) => setNewEvent({ ...newEvent, event_type: e.target.value })}
								>
									<MenuItem value="run">Run</MenuItem>
									<MenuItem value="strength">Strength</MenuItem>
									<MenuItem value="rest">Rest</MenuItem>
									<MenuItem value="race">Race</MenuItem>
									<MenuItem value="other">Other</MenuItem>
								</Select>
							</FormControl>
						</Box>
						<TextField
							label="Description / Notes"
							fullWidth
							multiline
							rows={4}
							value={newEvent.description}
							onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
							placeholder="e.g. 5km at easy pace, focus on form..."
						/>
					</Box>
				</DialogContent>
				<DialogActions sx={{ p: 3, pt: 0 }}>
					<Button onClick={() => setOpenAddDialog(false)} size="large">Cancel</Button>
					<Button onClick={handleAddEvent} variant="contained" size="large" sx={{ px: 4 }}>Add Event</Button>
				</DialogActions>
			</Dialog>
		</Container>
	);
};

export default CalendarPage;
