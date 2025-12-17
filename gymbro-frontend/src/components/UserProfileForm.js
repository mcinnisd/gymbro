import React, { useState, useEffect } from 'react';
import {
	TextField, Button, Container, Typography, Box,
	FormControl, InputLabel, Select, MenuItem, Alert
} from '@mui/material';

const UserProfileForm = () => {
	const [formData, setFormData] = useState({
		age: '',
		weight: '',
		height: '',
		sport_history: '',
		running_experience: '',
		past_injuries: '',
		lifestyle: '',
		weekly_availability: '',
		terrain_preference: '',
		equipment: '',
		next_race_date: '',
		next_race_name: ''
	});
	const [message, setMessage] = useState('');
	const [error, setError] = useState('');

	useEffect(() => {
		// Fetch existing profile
		const fetchProfile = async () => {
			const token = localStorage.getItem('token');
			if (!token) return;

			try {
				const response = await fetch('http://127.0.0.1:5000/auth/profile', {
					headers: {
						'Authorization': `Bearer ${token}`
					}
				});
				if (response.ok) {
					const data = await response.json();
					const p = data.profile;
					setFormData({
						age: p.age || '',
						weight: p.weight || '',
						height: p.height || '',
						sport_history: p.sport_history || '',
						running_experience: p.running_experience || '',
						past_injuries: p.past_injuries || '',
						lifestyle: p.lifestyle || '',
						weekly_availability: p.weekly_availability || '',
						terrain_preference: p.terrain_preference || '',
						equipment: p.equipment || '',
						next_race_date: p.goals?.next_race_date || '',
						next_race_name: p.goals?.next_race_name || ''
					});
				}
			} catch (err) {
				console.error("Failed to fetch profile", err);
			}
		};
		fetchProfile();
	}, []);

	const handleChange = (e) => {
		setFormData({ ...formData, [e.target.name]: e.target.value });
	};

	const handleSubmit = async (e) => {
		e.preventDefault();
		setMessage('');
		setError('');
		const token = localStorage.getItem('token');

		try {
			const response = await fetch('http://127.0.0.1:5000/auth/profile', {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${token}`
				},
				body: JSON.stringify(formData)
			});

			if (response.ok) {
				setMessage('Profile updated successfully!');
			} else {
				const data = await response.json();
				setError(data.error || 'Failed to update profile.');
			}
		} catch (err) {
			setError('An error occurred.');
		}
	};

	return (
		<Container maxWidth="md">
			<Box sx={{ mt: 4, mb: 4 }}>
				<Typography variant="h4" gutterBottom>
					Coach Setup: Your Profile
				</Typography>
				<Typography variant="body1" gutterBottom>
					Help your coach understand your background to build the best plan for you.
				</Typography>

				{message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
				{error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

				<form onSubmit={handleSubmit}>
					<Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: '1fr 1fr' }}>
						<TextField label="Age" name="age" type="number" value={formData.age} onChange={handleChange} required />
						<TextField label="Weight (kg)" name="weight" type="number" value={formData.weight} onChange={handleChange} required />
						<TextField label="Height (cm)" name="height" type="number" value={formData.height} onChange={handleChange} required />

						<FormControl fullWidth>
							<InputLabel>Terrain Preference</InputLabel>
							<Select name="terrain_preference" value={formData.terrain_preference} label="Terrain Preference" onChange={handleChange}>
								<MenuItem value="Road">Road</MenuItem>
								<MenuItem value="Trail">Trail</MenuItem>
								<MenuItem value="Mix">Mix</MenuItem>
							</Select>
						</FormControl>
					</Box>

					<TextField fullWidth margin="normal" label="Sport History" name="sport_history" multiline rows={2} value={formData.sport_history} onChange={handleChange} placeholder="e.g. Basketball, Cycling..." />
					<TextField fullWidth margin="normal" label="Running Experience" name="running_experience" multiline rows={2} value={formData.running_experience} onChange={handleChange} placeholder="Years running, recent races, PBs..." />
					<TextField fullWidth margin="normal" label="Past Injuries" name="past_injuries" multiline rows={2} value={formData.past_injuries} onChange={handleChange} placeholder="List injuries and current limitations..." />
					<TextField fullWidth margin="normal" label="Work & Lifestyle" name="lifestyle" value={formData.lifestyle} onChange={handleChange} placeholder="e.g. 9-5 desk job, active job..." />
					<TextField fullWidth margin="normal" label="Weekly Availability" name="weekly_availability" value={formData.weekly_availability} onChange={handleChange} placeholder="e.g. 5-6 days/week, 60-90 min sessions" />
					<TextField fullWidth margin="normal" label="Equipment Available" name="equipment" value={formData.equipment} onChange={handleChange} placeholder="Gym, home weights, etc." />

					<Typography variant="h6" sx={{ mt: 2 }}>Next Goal</Typography>
					<Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: '1fr 1fr', mt: 1 }}>
						<TextField label="Race Name" name="next_race_name" value={formData.next_race_name} onChange={handleChange} />
						<TextField label="Race Date" name="next_race_date" type="date" InputLabelProps={{ shrink: true }} value={formData.next_race_date} onChange={handleChange} />
					</Box>

					<Button type="submit" variant="contained" color="primary" size="large" sx={{ mt: 4 }}>
						Save Profile
					</Button>
				</form>
			</Box>
		</Container>
	);
};

export default UserProfileForm;
