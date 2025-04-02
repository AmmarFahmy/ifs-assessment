# Electricity Load Dashboard

An interactive dashboard for visualizing and forecasting electricity load data, featuring real-time forecasting using trained machine learning models and anomaly detection.

## Features

- **Overview**: Visualize historical electricity load patterns with key statistics
- **Load Patterns**: Analyze hourly, daily, and monthly load patterns
- **Forecast**: Generate electricity load forecasts using multiple ML models
- **Anomalies**: Detect and analyze anomalies in electricity consumption

## Project Structure

- `/src`: React frontend code
- `/public`: Static assets and CSV data
- `/api`: Flask backend for ML model inference

## Setup and Running

### Backend (Flask API)

First, set up and run the Flask API to enable real-time forecasting and anomaly detection:

1. Navigate to the API directory:
   ```
   cd api
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Start the Flask server:
   ```
   python app.py
   ```

The API server will run on http://localhost:5000.

### Frontend (React App)

In a separate terminal, run the React app:

1. Install npm dependencies:
   ```
   npm install
   ```

2. Start the development server:
   ```
   npm start
   ```

The app will be available at http://localhost:3000.

## Available Models

The following ML models are available for load forecasting:

- Gradient Boosting Regressor
- XGBoost Regressor
- Random Forest Regressor
- Linear Regression
- Support Vector Regressor (SVR)

## Forecast Horizons

You can generate forecasts for different time horizons:

- 12 hours
- 24 hours
- 48 hours
- 72 hours

## Data Source

The application uses historical electricity load data from the `DS_ElectricityLoad.csv` file in the public directory.

## Technologies Used

- **Frontend**: React, Recharts, TailwindCSS
- **Backend**: Flask, Scikit-learn, XGBoost, Pandas
- **ML Models**: Gradient Boosting, Random Forest, XGBoost, Linear Regression, SVR