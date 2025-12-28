import React from 'react';
import { Paper } from '@mui/material';

const GlassPaper = React.forwardRef(({ children, sx = {}, ...props }, ref) => {
	return (
		<Paper
			ref={ref}
			elevation={0}
			sx={(theme) => ({
				p: 3,
				borderRadius: 3,
				background: theme.palette.mode === 'dark'
					? 'linear-gradient(135deg, rgba(17, 22, 37, 0.7) 0%, rgba(26, 32, 44, 0.7) 100%)'
					: 'linear-gradient(135deg, rgba(255, 255, 255, 0.8) 0%, rgba(240, 242, 245, 0.8) 100%)',
				backdropFilter: 'blur(10px)',
				border: theme.palette.mode === 'dark'
					? '1px solid rgba(255,255,255,0.08)'
					: '1px solid rgba(255, 255, 255, 0.4)',
				boxShadow: theme.palette.mode === 'dark'
					? '0 8px 32px 0 rgba(0, 0, 0, 0.2)'
					: '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
				...sx
			})}
			{...props}
		>
			{children}
		</Paper>
	);
});

export default GlassPaper;
