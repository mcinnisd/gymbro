import React, { createContext, useState, useEffect } from 'react';

export const SettingsContext = createContext();

export const SettingsProvider = ({ children }) => {
	// Default to 'metric'
	const [units, setUnits] = useState(() => {
		return localStorage.getItem('gymbro_units') || 'metric';
	});

	useEffect(() => {
		localStorage.setItem('gymbro_units', units);
	}, [units]);

	const toggleUnits = () => {
		setUnits(prev => prev === 'metric' ? 'imperial' : 'metric');
	};

	return (
		<SettingsContext.Provider value={{ units, toggleUnits, setUnits }}>
			{children}
		</SettingsContext.Provider>
	);
};
