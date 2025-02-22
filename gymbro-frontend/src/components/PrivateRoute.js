// src/components/PrivateRoute.js
import React, { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

const PrivateRoute = ({ children }) => {
  const { authToken } = useContext(AuthContext);
  console.log('PrivateRoute: authToken:', authToken);

  return authToken ? children : <Navigate to="/" />;
};

export default PrivateRoute;