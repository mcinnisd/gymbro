import React from 'react';
import { Box, Container } from '@mui/material';
import Navbar from './Navbar';

const Layout = ({ children }) => {
	return (
		<Box
			sx={{
				display: 'flex',
				flexDirection: 'column',
				minHeight: '100vh',
				bgcolor: 'background.default',
				color: 'text.primary'
			}}
		>
			<Navbar />
			<Box component="main" sx={{ flexGrow: 1, py: 4 }}>
				{/* Pages verify their own container width usually, but we could enforce it here if we wanted strictly uniform width. 
            For flexibility (Dashboard vs Chat), we'll let children define their Container but provide the spacer here. */}
				{children}
			</Box>

			{/* Optional Simple Footer */}
			<Box sx={{ py: 3, textAlign: 'center', color: 'text.secondary', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
				<Container maxWidth="lg">
					<span style={{ fontSize: '0.85rem', opacity: 0.6 }}>© 2025 GymBro AI</span>
				</Container>
			</Box>
		</Box>
	);
};

export default Layout;
