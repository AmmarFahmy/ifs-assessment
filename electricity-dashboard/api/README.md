# Electricity Dashboard API

This is a Flask-based API for the Electricity Dashboard that provides:
- Real-time forecasting using trained ML models
- Anomaly detection in electricity load data

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Start the Flask server:

```bash
python app.py
```

The server will run on http://localhost:5000 by default.

## API Endpoints

### Forecast Endpoint
- URL: `/api/forecast`
- Method: `POST`
- Description: Generates electricity load forecasts using trained models
- Request Body:
  ```json
  {
    "historicalData": [...],  // Array of historical data points
    "model_type": "gradient_boosting",  // Optional: model to use
    "horizon": 24  // Optional: number of hours to forecast
  }
  ```
- Response:
  ```json
  {
    "status": "success",
    "data": [...]  // Array containing historical and forecast data
  }
  ```

### Anomalies Endpoint
- URL: `/api/anomalies`
- Method: `POST`
- Description: Detects anomalies in historical electricity load data
- Request Body:
  ```json
  {
    "historicalData": [...]  // Array of historical data points
  }
  ```
- Response:
  ```json
  {
    "status": "success",
    "data": [...]  // Array of detected anomalies
  }
  ```

## Models

The API uses pre-trained models stored in the `../models` directory. The following models are supported:

- `gradient_boosting`: Gradient Boosting Regressor
- `xgboost`: XGBoost Regressor
- `random_forest`: Random Forest Regressor 
- `linear_regression`: Linear Regression
- `svr`: Support Vector Regressor 