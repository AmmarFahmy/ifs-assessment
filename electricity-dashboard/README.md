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

# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
