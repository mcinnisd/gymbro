import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import {
	LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const ChartMessage = ({ chartData }) => {
	if (!chartData || !chartData.data) return null;

	const { title, type, data, options } = chartData;
	const labels = data.labels || [];
	const dataset = data.datasets && data.datasets[0]; // Support single dataset for now

	if (!dataset) return null;

	// Transform Chart.js format to Recharts format
	// From: labels: ['A', 'B'], data: [10, 20]
	// To: [{label: 'A', value: 10}, {label: 'B', value: 20}]
	const rechartsData = labels.map((label, index) => ({
		name: label,
		value: dataset.data[index]
	}));

	const renderChart = () => {
		if (type === 'line') {
			return (
				<LineChart data={rechartsData}>
					<CartesianGrid strokeDasharray="3 3" />
					<XAxis dataKey="name" />
					<YAxis reversed={options?.scales?.y?.reverse} />
					<Tooltip />
					<Legend />
					<Line
						type="monotone"
						dataKey="value"
						name={dataset.label}
						stroke={dataset.borderColor || "#8884d8"}
						strokeWidth={2}
						dot={{ r: 3 }}
						activeDot={{ r: 5 }}
					/>
				</LineChart>
			);
		} else if (type === 'bar') {
			return (
				<BarChart data={rechartsData}>
					<CartesianGrid strokeDasharray="3 3" />
					<XAxis dataKey="name" />
					<YAxis />
					<Tooltip />
					<Legend />
					<Bar
						dataKey="value"
						name={dataset.label}
						fill={dataset.backgroundColor || "#82ca9d"}
					/>
				</BarChart>
			);
		}
		return null;
	};

	return (
		<Paper elevation={0} variant="outlined" sx={{ p: 2, mt: 1, mb: 1, width: '100%' }}>
			<Typography variant="subtitle2" align="center" gutterBottom>
				{title}
			</Typography>
			<Box sx={{ width: '100%', height: 300 }}>
				<ResponsiveContainer>
					{renderChart()}
				</ResponsiveContainer>
			</Box>
		</Paper>
	);
};

export default ChartMessage;
