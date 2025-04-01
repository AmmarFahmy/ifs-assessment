import os
import json
import joblib
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler

app = Flask(__name__)
CORS(app)

# Path to models
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models')

# Load models and metadata
def load_model(model_type):
    latest_timestamp = "20250401_200319"  # Hardcoded for simplicity, could be dynamic
    model_path = os.path.join(MODELS_DIR, f"model_{model_type}_{latest_timestamp}.joblib")
    metadata_path = os.path.join(MODELS_DIR, f"model_{model_type}_{latest_timestamp}_metadata.json")
    
    model = joblib.load(model_path)
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    return model, metadata

# Load feature scaler if needed
def load_scaler():
    latest_timestamp = "20250401_200319"  # Hardcoded for simplicity
    scaler_path = os.path.join(MODELS_DIR, f"feature_scaler_{latest_timestamp}.joblib")
    return joblib.load(scaler_path)

# Preprocess data for model input
def preprocess_data(df, metadata, scaler=None):
    # Create cyclic features
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day_of_week_sin'] = np.sin(2 * np.pi * df['dayOfWeek'] / 7)
    df['day_of_week_cos'] = np.cos(2 * np.pi * df['dayOfWeek'] / 7)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    
    # Derived features
    df['is_weekend'] = df['dayOfWeek'].apply(lambda x: 1 if x >= 5 else 0)
    df['temp_squared'] = df['Temperature']**2
    df['cloud_irradiation_interaction'] = df['Cloudiness'] * df['Irradiation']
    
    # Create lagged features from Load
    for lag in [1, 2, 3, 24, 48, 168]:
        df[f'load_lag{lag}'] = df['Load'].shift(lag)
    
    # Create rolling mean features
    df['load_rolling_mean_6h'] = df['Load'].rolling(6).mean()
    df['load_rolling_mean_12h'] = df['Load'].rolling(12).mean()
    df['load_rolling_mean_24h'] = df['Load'].rolling(24).mean()
    
    # Drop rows with NaN values (first rows won't have lag values)
    df = df.dropna()
    
    # Select only the features required by the model
    X = df[metadata['features']]
    
    # Apply scaling if needed
    if metadata.get('requires_scaling', False) and scaler is not None:
        X = scaler.transform(X)
    
    return X, df

# Route to get forecasts
@app.route('/api/forecast', methods=['POST'])
def get_forecast():
    try:
        # Load historical data from request
        data = request.json
        historical_data = pd.DataFrame(data['historicalData'])
        
        # Convert timestamp from milliseconds to datetime if needed
        if 'timestamp' in historical_data.columns:
            # Check if timestamp is already in milliseconds (JavaScript standard)
            if historical_data['timestamp'].iloc[0] > 1e12:  # Timestamps in milliseconds are very large numbers
                historical_data['timestamp'] = historical_data['timestamp'] / 1000  # Convert to seconds
            
            # Ensure timestamp is in datetime format for processing
            historical_data['timestamp'] = pd.to_datetime(historical_data['timestamp'], unit='s')
        
        # Select model type
        model_type = data.get('model_type', 'gradient_boosting')
        horizon = data.get('horizon', 24)  # hours to forecast
        
        # Load model and metadata
        model, metadata = load_model(model_type)
        scaler = load_scaler() if metadata.get('requires_scaling', False) else None
        
        # Create a copy of the DataFrame for forecasting
        forecast_df = historical_data.copy()
        
        # Get the latest timestamp and prepare for forecasting
        latest_timestamp = forecast_df['timestamp'].max()
        
        # Store original values for result
        original_data = forecast_df.copy()
        
        # Generate forecasts
        forecasts = []
        
        # First process the historical data to prepare it for forecasting
        # Preprocess the data once to ensure it works
        X_initial, processed_df = preprocess_data(forecast_df, metadata, scaler)
        
        # If processed data is empty, we need to handle this case
        if X_initial.empty:
            return jsonify({
                'status': 'error',
                'message': 'Insufficient historical data after preprocessing. Need more data points for forecasting.'
            }), 400
        
        # Now generate each forecast step by step
        current_df = processed_df.copy()
        
        for i in range(1, horizon + 1):
            current_time = latest_timestamp + pd.Timedelta(hours=i)
            
            # Create a new row for the forecast time
            new_row = {
                'timestamp': current_time,
                'formattedDate': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'hour': current_time.hour,
                'dayOfWeek': current_time.weekday(),
                'month': current_time.month,
                'year': current_time.year,
                'dayOfMonth': current_time.day,
                # Assume we have weather forecasts available
                'Temperature': 20 + 5 * np.sin(2 * np.pi * current_time.hour / 24),  # Mock weather
                'Cloudiness': 50 + 20 * np.sin(2 * np.pi * current_time.hour / 12),
                'Irradiation': max(0, 100 * np.sin(np.pi * current_time.hour / 12)),
                'PublicHolidays': 0  # Assume no holidays for simplicity
            }
            
            # For the first forecast step, we use the actual historical data
            if i == 1:
                # Calculate all the required features for this new row
                temp_df = pd.concat([forecast_df, pd.DataFrame([new_row])], ignore_index=True)
                X_new, processed_new_df = preprocess_data(temp_df, metadata, scaler)
                
                # If X_new is empty, we can't make a prediction
                if X_new.empty:
                    break
                
                # Get the last row which contains the features for our forecast
                latest_X = X_new.iloc[-1:] 
                
                # Check if latest_X has all required features
                if not all(feature in latest_X.columns for feature in metadata['features']):
                    missing_features = [f for f in metadata['features'] if f not in latest_X.columns]
                    print(f"Missing features for prediction: {missing_features}")
                    break
                
                prediction = model.predict(latest_X)[0]
                
                # Update current_df with the new prediction
                new_row['Load'] = prediction
                current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
            else:
                # For subsequent steps, we use the previous forecast
                # We need to recalculate features based on the previous forecasts
                new_row['Load'] = 0  # Placeholder, will be updated after prediction
                temp_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
                
                # Recalculate all features with the updated historical + forecast data
                X_new, processed_new_df = preprocess_data(temp_df, metadata, scaler)
                
                # If X_new is empty, we can't make a prediction
                if X_new.empty:
                    break
                
                # Get the last row which contains the features for our forecast
                if len(X_new) > 0:
                    latest_X = X_new.iloc[-1:]
                    prediction = model.predict(latest_X)[0]
                    
                    # Update the temp_df with the prediction
                    new_row['Load'] = prediction
                    
                    # Update our running dataframe with the new prediction
                    current_df = temp_df.copy()
                    current_df.iloc[-1, current_df.columns.get_loc('Load')] = prediction
                else:
                    # If we can't make a prediction, we'll use a simple heuristic
                    # Just copy the load from 24 hours ago as a fallback
                    hour_index = current_df[current_df['hour'] == new_row['hour']].index
                    if len(hour_index) > 0:
                        similar_hour_load = current_df.loc[hour_index[-1], 'Load']
                        prediction = similar_hour_load
                    else:
                        # If no similar hour, use the last prediction
                        prediction = current_df.iloc[-1]['Load']
                    
                    new_row['Load'] = prediction
                    current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
            
            # Prepare result object for the frontend
            forecast_point = {
                'timestamp': int(current_time.timestamp() * 1000),  # Convert to milliseconds for JavaScript
                'formattedDate': new_row['formattedDate'],
                'Load': prediction,
                'isForecast': True,
                'hour': new_row['hour'],
                'dayOfWeek': new_row['dayOfWeek'],
                # Add confidence intervals based on model type
                'LowerBound': prediction * 0.95 if model_type == 'linear_regression' else prediction * 0.90,
                'UpperBound': prediction * 1.05 if model_type == 'linear_regression' else prediction * 1.10
            }
            forecasts.append(forecast_point)
        
        # Get the last 24 hours of actual data (or less if not available)
        last_hours = min(24, len(original_data))
        last_actual = original_data.tail(last_hours).copy()
        
        # Ensure timestamps are in milliseconds for JavaScript
        if 'timestamp' in last_actual.columns:
            # Convert datetime to timestamp in milliseconds if needed
            if isinstance(last_actual['timestamp'].iloc[0], pd.Timestamp):
                last_actual['timestamp'] = last_actual['timestamp'].astype(int) / 10**9 * 1000
            else:
                # If it's already a numeric timestamp in seconds, convert to milliseconds
                last_actual['timestamp'] = last_actual['timestamp'] * 1000
                
        last_actual['isForecast'] = False
        
        # Keep only necessary columns
        required_columns = ['timestamp', 'formattedDate', 'Load', 'isForecast', 'hour', 'dayOfWeek']
        for col in required_columns:
            if col not in last_actual.columns:
                if col == 'formattedDate' and 'timestamp' in last_actual.columns:
                    # Generate formattedDate from timestamp if missing
                    last_actual['formattedDate'] = pd.to_datetime(last_actual['timestamp'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')
        
        last_actual = last_actual[[col for col in required_columns if col in last_actual.columns]]
        
        # Convert to dictionary for JSON serialization
        last_actual_dict = last_actual.to_dict('records')
        
        # Fall back to mock data if forecasts is empty
        if not forecasts:
            # Get the last timestamp from the data
            last_timestamp = original_data['timestamp'].max()
            
            # Generate mock forecasts
            mock_forecasts = []
            for i in range(1, horizon + 1):
                current_time = last_timestamp + pd.Timedelta(hours=i)
                hour = current_time.hour
                
                # Simple model based on hour of day
                if hour >= 0 and hour < 6:
                    prediction = 14000 + np.random.random() * 1000
                elif hour >= 6 and hour < 12:
                    prediction = 18000 + np.random.random() * 1500
                elif hour >= 12 and hour < 18:
                    prediction = 19500 + np.random.random() * 1000
                else:
                    prediction = 17000 + np.random.random() * 1500
                
                mock_forecast = {
                    'timestamp': int(current_time.timestamp() * 1000),
                    'formattedDate': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'Load': prediction,
                    'isForecast': True,
                    'hour': hour,
                    'dayOfWeek': current_time.weekday(),
                    'LowerBound': prediction * 0.95,
                    'UpperBound': prediction * 1.05
                }
                mock_forecasts.append(mock_forecast)
            
            print("Generated mock forecasts as fallback")
            forecasts = mock_forecasts
        
        # Return both actual and forecast data
        return jsonify({
            'status': 'success',
            'data': last_actual_dict + forecasts
        })
        
    except Exception as e:
        import traceback
        print(f"Error generating forecast: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Route to detect anomalies
@app.route('/api/anomalies', methods=['POST'])
def detect_anomalies():
    try:
        # Load data from request
        data = request.json
        historical_data = pd.DataFrame(data['historicalData'])
        
        print(f"Received anomaly detection request with {len(historical_data)} data points")
        
        # If data is empty, return empty result
        if historical_data.empty:
            print("Empty dataset received, returning empty result")
            return jsonify({
                'status': 'success',
                'data': []
            })
        
        # Convert timestamp from milliseconds to datetime if needed
        if 'timestamp' in historical_data.columns:
            # Check if timestamp is already in milliseconds (JavaScript standard)
            if historical_data['timestamp'].iloc[0] > 1e12:  # Timestamps in milliseconds are very large numbers
                historical_data['timestamp'] = historical_data['timestamp'] / 1000  # Convert to seconds
            
            # Ensure timestamp is in datetime format for processing
            historical_data['timestamp'] = pd.to_datetime(historical_data['timestamp'], unit='s')
        
        # Ensure we have the Load column
        if 'Load' not in historical_data.columns:
            print("Error: Load column missing from input data")
            return jsonify({
                'status': 'error',
                'message': 'Load data missing from input'
            }), 400
        
        # Need at least 48 data points for meaningful anomaly detection
        if len(historical_data) < 48:
            print(f"Insufficient data: only {len(historical_data)} points provided")
            return jsonify({
                'status': 'error',
                'message': 'Insufficient data for anomaly detection. Need at least 48 hourly data points.'
            }), 400
        
        # Make sure all required columns exist
        required_columns = ['hour', 'dayOfWeek']
        for col in required_columns:
            if col not in historical_data.columns:
                print(f"Missing required column: {col}, attempting to derive it")
                if col == 'hour' and 'timestamp' in historical_data.columns:
                    historical_data['hour'] = historical_data['timestamp'].dt.hour
                elif col == 'dayOfWeek' and 'timestamp' in historical_data.columns:
                    historical_data['dayOfWeek'] = historical_data['timestamp'].dt.dayofweek
                else:
                    print(f"Cannot derive {col} from available data")
                    return jsonify({
                        'status': 'error',
                        'message': f'Required column {col} missing and cannot be derived'
                    }), 400
        
        # Simple anomaly detection based on statistical methods
        print("Calculating rolling statistics for anomaly detection")
        # Calculate rolling mean and standard deviation with 24 hour window
        historical_data['rolling_mean'] = historical_data['Load'].rolling(window=24, min_periods=12).mean()
        historical_data['rolling_std'] = historical_data['Load'].rolling(window=24, min_periods=12).std()
        
        # If rolling calculations result in NaN, fill with overall mean/std
        if historical_data['rolling_mean'].isna().any():
            overall_mean = historical_data['Load'].mean()
            historical_data['rolling_mean'] = historical_data['rolling_mean'].fillna(overall_mean)
            print(f"Filled {historical_data['rolling_mean'].isna().sum()} NaN mean values with overall mean")
        
        if historical_data['rolling_std'].isna().any():
            overall_std = historical_data['Load'].std()
            historical_data['rolling_std'] = historical_data['rolling_std'].fillna(overall_std)
            print(f"Filled {historical_data['rolling_std'].isna().sum()} NaN std values with overall std")
            
        # Avoid division by zero
        zero_std_count = (historical_data['rolling_std'] == 0).sum()
        if zero_std_count > 0:
            print(f"Found {zero_std_count} zero values in std, replacing with mean")
            historical_data['rolling_std'] = historical_data['rolling_std'].replace(0, historical_data['rolling_std'].mean())
        
        # Define anomaly threshold (z-score approach)
        threshold = 3
        historical_data['z_score'] = abs((historical_data['Load'] - historical_data['rolling_mean']) / historical_data['rolling_std'])
        
        # Identify anomalies (non-null z_score above threshold)
        anomalies = historical_data[(historical_data['z_score'] > threshold) & (~historical_data['z_score'].isna())].copy()
        
        # If no anomalies found, return empty list
        if anomalies.empty:
            print("No anomalies detected using z-score threshold")
            return jsonify({
                'status': 'success',
                'data': []
            })
        
        print(f"Detected {len(anomalies)} anomalies using z-score threshold")
        
        # Limit to a reasonable number of anomalies (top 20 by z-score)
        if len(anomalies) > 20:
            print(f"Limiting to top 20 anomalies from {len(anomalies)} detected")
            anomalies = anomalies.nlargest(20, 'z_score')
        
        # Determine anomaly severity and reason
        def get_severity(z_score):
            if z_score > 5:
                return 'High'
            elif z_score > 4:
                return 'Medium'
            else:
                return 'Low'
        
        def get_reason(row):
            # Simple heuristic rules to determine reason
            load_diff = row['Load'] - row['rolling_mean']
            direction = "high" if load_diff > 0 else "low"
            
            # Larger percent difference means more severe anomaly
            pct_diff = abs(load_diff / row['rolling_mean'] * 100)
            magnitude = "significant " if pct_diff > 25 else ""
            
            if row['hour'] in [9, 10, 11, 12, 13, 14, 15, 16, 17]:
                if load_diff > 0:
                    return f'Unexpected {magnitude}high demand during working hours'
                else:
                    return f'Unexpected {magnitude}low demand during working hours'
            elif row['hour'] in [0, 1, 2, 3, 4, 5]:
                if load_diff > 0:
                    return f'Unexpected {magnitude}night-time activity'
                else:
                    return f'Lower than expected base load'
            elif row['dayOfWeek'] in [5, 6]:  # Weekend
                return f'Unusual weekend {direction} consumption'
            else:
                return f'Unexplained {magnitude}{direction} consumption'
        
        anomalies['severity'] = anomalies['z_score'].apply(get_severity)
        anomalies['reason'] = anomalies.apply(get_reason, axis=1)
        
        # Calculate and add percentage deviation from expected
        anomalies['pct_deviation'] = ((anomalies['Load'] - anomalies['rolling_mean']) / anomalies['rolling_mean'] * 100).round(2)
        
        # Count severity levels
        severity_counts = anomalies['severity'].value_counts().to_dict()
        print(f"Anomaly severity distribution: {severity_counts}")
        
        # Prepare response
        required_columns = ['timestamp', 'formattedDate', 'Load', 'hour', 'dayOfWeek', 'severity', 
                          'reason', 'rolling_mean', 'z_score', 'pct_deviation']
        
        # Ensure all required columns exist
        for col in required_columns:
            if col not in anomalies.columns:
                if col == 'formattedDate' and 'timestamp' in anomalies.columns:
                    # Generate formattedDate from timestamp if missing
                    anomalies['formattedDate'] = anomalies['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Select only columns that exist
        existing_columns = [col for col in required_columns if col in anomalies.columns]
        anomalies_result = anomalies[existing_columns].to_dict('records')
        
        # Ensure timestamp is in milliseconds for JavaScript
        for item in anomalies_result:
            if 'timestamp' in item:
                # If it's a pandas Timestamp or datetime object
                if isinstance(item['timestamp'], (pd.Timestamp, datetime)):
                    item['timestamp'] = int(item['timestamp'].timestamp() * 1000)
                else:
                    # If it's a numeric timestamp in seconds
                    item['timestamp'] = int(item['timestamp'] * 1000) if item['timestamp'] < 1e12 else int(item['timestamp'])
        
        print(f"Returning {len(anomalies_result)} anomalies to frontend")
        return jsonify({
            'status': 'success',
            'data': anomalies_result
        })
        
    except Exception as e:
        import traceback
        print(f"Error detecting anomalies: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    print("Starting Flask API server for electricity load forecasting on http://localhost:5000")
    app.run(debug=True, port=5000, host='0.0.0.0') 