import React from 'react';
import { Card, CardContent, Typography, Button, Box, Chip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

function ProposalCard({ proposal, onApprove, onDeny }) {
	const { action, data, reasoning } = proposal;

	const getActionLabel = () => {
		switch (action) {
			case 'create_event': return 'Create Event';
			case 'update_event': return 'Update Event';
			case 'delete_event': return 'Delete Event';
			default: return 'Unknown Action';
		}
	};

	const renderDetails = () => {
		if (action === 'create_event' || action === 'update_event') {
			return (
				<Box mt={1} mb={1}>
					{data.date && <Typography variant="body2"><strong>Date:</strong> {data.date}</Typography>}
					{data.title && <Typography variant="body2"><strong>Title:</strong> {data.title}</Typography>}
					{data.event_type && <Typography variant="body2"><strong>Type:</strong> {data.event_type}</Typography>}
					{data.description && <Typography variant="body2"><strong>Desc:</strong> {data.description}</Typography>}
				</Box>
			);
		} else if (action === 'delete_event') {
			return (
				<Box mt={1} mb={1}>
					<Typography variant="body2"><strong>Event ID:</strong> {data.event_id}</Typography>
				</Box>
			);
		}
		return null;
	};

	return (
		<Card
			sx={{
				mt: 2,
				mb: 2,
				background: 'linear-gradient(145deg, rgba(26, 32, 44, 0.6) 0%, rgba(17, 22, 37, 0.8) 100%)',
				backdropFilter: 'blur(5px)',
				border: '1px solid rgba(108, 99, 255, 0.3)',
				borderRadius: 3,
				color: 'text.primary'
			}}
		>
			<CardContent>
				<Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
					<Typography variant="subtitle1" sx={{ color: '#6C63FF', fontWeight: 700 }}>
						{getActionLabel()}
					</Typography>
					<Chip
						label="Proposal"
						size="small"
						sx={{
							borderColor: '#6C63FF',
							color: '#6C63FF',
							fontWeight: 'bold',
							borderRadius: '6px'
						}}
						variant="outlined"
					/>
				</Box>

				<Box sx={{ bg: 'rgba(0,0,0,0.2)', p: 1.5, borderRadius: 2, mb: 2 }}>
					{renderDetails()}
				</Box>

				<Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', mb: 3 }}>
					"{reasoning}"
				</Typography>

				<Box display="flex" gap={2}>
					<Button
						variant="contained"
						sx={{
							flex: 1,
							background: 'linear-gradient(45deg, #00E5FF 30%, #00B0FF 90%)',
							color: '#000',
							fontWeight: 'bold'
						}}
						startIcon={<CheckCircleIcon />}
						onClick={() => onApprove(proposal)}
					>
						Approve
					</Button>
					<Button
						variant="outlined"
						color="error"
						sx={{ flex: 1, borderWidth: 2 }}
						startIcon={<CancelIcon />}
						onClick={onDeny}
					>
						Deny
					</Button>
				</Box>
			</CardContent>
		</Card>
	);
}

export default ProposalCard;
