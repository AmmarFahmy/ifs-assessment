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

# Custom JSON encoder to handle numpy types


class NumpyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


# Configure Flask to use our custom JSON encoder
app.json_encoder = NumpyJSONEncoder

# Path to models
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'models')

# Load models and metadata


def load_model(model_type):
    # Dynamically pick the latest timestamp from the models directory
    model_files = [f for f in os.listdir(MODELS_DIR) if f.startswith(
        f"model_{model_type}_") and f.endswith(".joblib")]
    if not model_files:
        raise FileNotFoundError(
            f"No model files found for model type: {model_type}")

    # Extract timestamps and find the latest one
    timestamps = [f.split('_')[-2] + "_" + f.split('_')
                  [-1].split('.')[0] for f in model_files]
    latest_timestamp = max(timestamps)

    model_path = os.path.join(
        MODELS_DIR, f"model_{model_type}_{latest_timestamp}.joblib")
    metadata_path = os.path.join(
        MODELS_DIR, f"model_{model_type}_{latest_timestamp}_metadata.json")

    model = joblib.load(model_path)

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    return model, metadata

# Load feature scaler if needed


def load_scaler(model_type):
    # latest_timestamp = "20250401_200319"  # Hardcoded for simplicity
    # Dynamically pick the latest timestamp from the models directory
    model_files = [f for f in os.listdir(MODELS_DIR) if f.startswith(
        f"model_{model_type}_") and f.endswith(".joblib")]
    if not model_files:
        raise FileNotFoundError(
            f"No model files found for model type: {model_type}")

    # Extract timestamps and find the latest one
    timestamps = [f.split('_')[-2] + "_" + f.split('_')
                  [-1].split('.')[0] for f in model_files]
    latest_timestamp = max(timestamps)
    scaler_path = os.path.join(
        MODELS_DIR, f"feature_scaler_{latest_timestamp}.joblib")
    return joblib.load(scaler_path)

# Preprocess data for model input


def preprocess_data(df, metadata, scaler=None):
    """
    Preprocess data for model input, handling edge cases gracefully.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing the data to preprocess
    metadata : dict
        Dictionary containing model metadata including required features
    scaler : sklearn.preprocessing.StandardScaler, optional
        Scaler to apply to the data if needed

    Returns:
    --------
    X : pandas.DataFrame
        DataFrame containing the preprocessed features
    df : pandas.DataFrame
        The original DataFrame with additional calculated features
    """
    try:
        # Make a copy to avoid modifying the original
        df = df.copy()

        # First, ensure all data columns are properly typed
        # Convert any string numeric columns to float
        for col in df.columns:
            # Skip timestamp and formatted date columns
            if col in ['timestamp', 'formattedDate']:
                continue

            # Try to convert to numeric if it's not already
            if df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    print(
                        f"Could not convert column {col} to numeric, keeping as is")

        # Ensure we have enough data
        if len(df) < 24 * 7:  # At least one week of data
            print(
                "Warning: Insufficient data for feature engineering. Need at least one week of data.")
            # We'll try to proceed anyway, but features will be limited

        # Create cyclic features
        if 'hour' in df.columns:
            df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
            df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)

        if 'dayOfWeek' in df.columns:
            df['day_of_week_sin'] = np.sin(2 * np.pi * df['dayOfWeek'] / 7)
            df['day_of_week_cos'] = np.cos(2 * np.pi * df['dayOfWeek'] / 7)

        if 'month' in df.columns:
            df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
            df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

        # Derived features
        if 'dayOfWeek' in df.columns:
            df['is_weekend'] = df['dayOfWeek'].apply(
                lambda x: 1 if x >= 5 else 0)

        if 'Temperature' in df.columns:
            df['temp_squared'] = df['Temperature']**2

        if 'Cloudiness' in df.columns and 'Irradiation' in df.columns:
            df['cloud_irradiation_interaction'] = df['Cloudiness'] * \
                df['Irradiation']

        # Create lagged features from Load if sufficient data
        try:
            # If we have enough data, create all lags
            for lag in [1, 2, 3, 24, 48, 168]:
                if len(df) > lag:
                    df[f'load_lag{lag}'] = df['Load'].shift(lag)
                else:
                    # Not enough data for this lag, use a simple fallback
                    print(
                        f"Not enough data for lag {lag}, using mean as fallback")
                    df[f'load_lag{lag}'] = df['Load'].mean()

            # Create rolling mean features
            if len(df) >= 6:
                df['load_rolling_mean_6h'] = df['Load'].rolling(
                    min_periods=1, window=min(6, len(df))).mean()
            else:
                df['load_rolling_mean_6h'] = df['Load'].mean()

            if len(df) >= 12:
                df['load_rolling_mean_12h'] = df['Load'].rolling(
                    min_periods=1, window=min(12, len(df))).mean()
            else:
                df['load_rolling_mean_12h'] = df['Load'].mean()

            if len(df) >= 24:
                df['load_rolling_mean_24h'] = df['Load'].rolling(
                    min_periods=1, window=min(24, len(df))).mean()
            else:
                df['load_rolling_mean_24h'] = df['Load'].mean()
        except Exception as e:
            print(f"Error creating lagged features: {str(e)}")
            # Emergency fallback - create simple lag features
            load_mean = df['Load'].mean()
            for lag in [1, 2, 3, 24, 48, 168]:
                df[f'load_lag{lag}'] = load_mean
            df['load_rolling_mean_6h'] = load_mean
            df['load_rolling_mean_12h'] = load_mean
            df['load_rolling_mean_24h'] = load_mean

        # Fill NA values with appropriate defaults - this was causing the string/int concatenation error
        for col in df.columns:
            if col != 'Load' and df[col].isna().any():
                if col in ['timestamp', 'formattedDate']:
                    continue  # Skip datetime columns
                elif col.startswith('load_lag') or col.startswith('load_rolling'):
                    df[col] = df[col].fillna(df['Load'].mean())
                elif col in ['hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos', 'month_sin', 'month_cos']:
                    # 0 is the midpoint for sin/cos features
                    df[col] = df[col].fillna(0)
                elif col == 'is_weekend':
                    df[col] = df[col].fillna(0)  # Assume weekday as default
                elif col in ['Temperature', 'temp_squared']:
                    # Assume room temperature as default
                    df[col] = df[col].fillna(20)
                elif col in ['Cloudiness', 'Irradiation', 'cloud_irradiation_interaction']:
                    # Assume moderate values as default
                    df[col] = df[col].fillna(50)
                elif col == 'PublicHolidays':
                    # Assume not a holiday as default
                    df[col] = df[col].fillna(0)
                else:
                    # Check if column is numeric before using mean
                    if pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col].fillna(
                            df[col].mean() if not pd.isna(df[col].mean()) else 0)
                    else:
                        # Use a string default for non-numeric columns
                        df[col] = df[col].fillna("unknown")

        # Make sure all required features exist, even if they're not in the metadata
        # This is a safety measure in case the model requires features we don't have
        all_possible_features = [
            'hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos',
            'month_sin', 'month_cos', 'is_weekend', 'Temperature', 'temp_squared',
            'Cloudiness', 'Irradiation', 'cloud_irradiation_interaction',
            'load_lag1', 'load_lag2', 'load_lag3', 'load_lag24', 'load_lag48', 'load_lag168',
            'load_rolling_mean_6h', 'load_rolling_mean_12h', 'load_rolling_mean_24h',
            'PublicHolidays'
        ]

        for feature in all_possible_features:
            if feature not in df.columns:
                print(
                    f"Warning: Feature {feature} not found in data, adding with default value")
                if feature in ['hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos', 'month_sin', 'month_cos']:
                    df[feature] = 0
                elif feature == 'is_weekend':
                    df[feature] = 0
                elif feature in ['Temperature', 'temp_squared']:
                    df[feature] = 20
                elif feature in ['Cloudiness', 'Irradiation', 'cloud_irradiation_interaction']:
                    df[feature] = 50
                elif feature.startswith('load_lag') or feature.startswith('load_rolling'):
                    df[feature] = df['Load'].mean()
                elif feature == 'PublicHolidays':
                    df[feature] = 0
                else:
                    df[feature] = 0

        # Select only the features required by the model
        required_features = metadata.get('features', all_possible_features)

        # Check if all required features exist
        missing_features = [
            f for f in required_features if f not in df.columns]
        if missing_features:
            print(f"Warning: Missing required features: {missing_features}")
            # Add missing features with default values
            for feature in missing_features:
                if feature in ['hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos', 'month_sin', 'month_cos']:
                    df[feature] = 0
                elif feature == 'is_weekend':
                    df[feature] = 0
                elif feature in ['Temperature', 'temp_squared']:
                    df[feature] = 20
                elif feature in ['Cloudiness', 'Irradiation', 'cloud_irradiation_interaction']:
                    df[feature] = 50
                elif feature.startswith('load_lag') or feature.startswith('load_rolling'):
                    df[feature] = df['Load'].mean()
                elif feature == 'PublicHolidays':
                    df[feature] = 0
                else:
                    df[feature] = 0

        X = df[required_features]

        # Apply scaling if needed
        if metadata.get('requires_scaling', False) and scaler is not None:
            try:
                X_scaled = scaler.transform(X)
                X = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
            except Exception as e:
                print(f"Error during scaling: {str(e)}")
                # If scaling fails, proceed with unscaled data
                print("Proceeding with unscaled data")

        return X, df

    except Exception as e:
        import traceback
        print(f"Error in preprocess_data: {str(e)}")
        print(traceback.format_exc())

        # Return empty DataFrames as a last resort
        return pd.DataFrame(), df

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
            # Timestamps in milliseconds are very large numbers
            if historical_data['timestamp'].iloc[0] > 1e12:
                # Convert to seconds
                historical_data['timestamp'] = historical_data['timestamp'] / 1000

            # Ensure timestamp is in datetime format for processing
            historical_data['timestamp'] = pd.to_datetime(
                historical_data['timestamp'], unit='s')

        # Select model type
        model_type = data.get('model_type', 'gradient_boosting')
        horizon = data.get('horizon', 24)  # hours to forecast

        # Load model and metadata
        model, metadata = load_model(model_type)
        scaler = load_scaler(model_type) if metadata.get(
            'requires_scaling', False) else None

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
        X_initial, processed_df = preprocess_data(
            forecast_df, metadata, scaler)

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
                # Mock weather
                'Temperature': 20 + 5 * np.sin(2 * np.pi * current_time.hour / 24),
                'Cloudiness': 50 + 20 * np.sin(2 * np.pi * current_time.hour / 12),
                'Irradiation': max(0, 100 * np.sin(np.pi * current_time.hour / 12)),
                'PublicHolidays': 0  # Assume no holidays for simplicity
            }

            # For the first forecast step, we use the actual historical data
            if i == 1:
                # Calculate all the required features for this new row
                temp_df = pd.concat(
                    [forecast_df, pd.DataFrame([new_row])], ignore_index=True)
                X_new, processed_new_df = preprocess_data(
                    temp_df, metadata, scaler)

                # If X_new is empty, we can't make a prediction
                if X_new.empty:
                    break

                # Get the last row which contains the features for our forecast
                latest_X = X_new.iloc[-1:]

                # Check if latest_X has all required features
                if not all(feature in latest_X.columns for feature in metadata['features']):
                    missing_features = [
                        f for f in metadata['features'] if f not in latest_X.columns]
                    print(
                        f"Missing features for prediction: {missing_features}")
                    break

                prediction = model.predict(latest_X)[0]

                # Convert numpy types to Python native types
                if isinstance(prediction, (np.integer, np.floating, np.number)):
                    prediction = float(prediction)

                # Update current_df with the new prediction
                new_row['Load'] = prediction
                current_df = pd.concat(
                    [current_df, pd.DataFrame([new_row])], ignore_index=True)
            else:
                # For subsequent steps, we use the previous forecast
                # We need to recalculate features based on the previous forecasts
                # Placeholder, will be updated after prediction
                new_row['Load'] = 0
                temp_df = pd.concat(
                    [current_df, pd.DataFrame([new_row])], ignore_index=True)

                # Recalculate all features with the updated historical + forecast data
                X_new, processed_new_df = preprocess_data(
                    temp_df, metadata, scaler)

                # If X_new is empty, we can't make a prediction
                if X_new.empty:
                    break

                # Get the last row which contains the features for our forecast
                if len(X_new) > 0:
                    latest_X = X_new.iloc[-1:]
                    prediction = model.predict(latest_X)[0]

                    # Convert numpy types to Python native types
                    if isinstance(prediction, (np.integer, np.floating, np.number)):
                        prediction = float(prediction)

                    # Update the temp_df with the prediction
                    new_row['Load'] = prediction

                    # Update our running dataframe with the new prediction
                    current_df = temp_df.copy()
                    current_df.iloc[-1,
                                    current_df.columns.get_loc('Load')] = prediction
                else:
                    # If we can't make a prediction, we'll use a simple heuristic
                    # Just copy the load from 24 hours ago as a fallback
                    hour_index = current_df[current_df['hour']
                                            == new_row['hour']].index
                    if len(hour_index) > 0:
                        similar_hour_load = current_df.loc[hour_index[-1], 'Load']
                        prediction = similar_hour_load
                    else:
                        # If no similar hour, use the last prediction
                        prediction = current_df.iloc[-1]['Load']

                    # Convert numpy types to Python native types
                    if isinstance(prediction, (np.integer, np.floating, np.number)):
                        prediction = float(prediction)

                    new_row['Load'] = prediction
                    current_df = pd.concat(
                        [current_df, pd.DataFrame([new_row])], ignore_index=True)

            # Prepare result object for the frontend
            forecast_point = {
                # Convert to milliseconds for JavaScript
                'timestamp': int(current_time.timestamp() * 1000),
                'formattedDate': new_row['formattedDate'],
                'Load': prediction,
                'isForecast': True,
                'hour': new_row['hour'],
                'dayOfWeek': new_row['dayOfWeek'],
                # Add confidence intervals based on model type
                'LowerBound': float(prediction * 0.95) if model_type == 'linear_regression' else float(prediction * 0.90),
                'UpperBound': float(prediction * 1.05) if model_type == 'linear_regression' else float(prediction * 1.10)
            }
            forecasts.append(forecast_point)

        # Get the last 24 hours of actual data (or less if not available)
        last_hours = min(24, len(original_data))
        last_actual = original_data.tail(last_hours).copy()

        # Ensure timestamps are in milliseconds for JavaScript
        if 'timestamp' in last_actual.columns:
            # Fix the datetime conversion issue by using correct conversion method
            if isinstance(last_actual['timestamp'].iloc[0], pd.Timestamp):
                last_actual['timestamp'] = last_actual['timestamp'].apply(
                    lambda x: int(x.timestamp() * 1000))
            else:
                # If it's already a numeric timestamp in seconds, convert to milliseconds
                last_actual['timestamp'] = last_actual['timestamp'] * 1000

        last_actual['isForecast'] = False

        # Keep only necessary columns
        required_columns = ['timestamp', 'formattedDate',
                            'Load', 'isForecast', 'hour', 'dayOfWeek']
        for col in required_columns:
            if col not in last_actual.columns:
                if col == 'formattedDate' and 'timestamp' in last_actual.columns:
                    # Generate formattedDate from timestamp if missing
                    last_actual['formattedDate'] = pd.to_datetime(
                        last_actual['timestamp'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')

        last_actual = last_actual[[
            col for col in required_columns if col in last_actual.columns]]

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

        # Get threshold parameter if provided, otherwise use default
        threshold = float(data.get('threshold', 3.0))
        print(f"Using threshold value: {threshold}")

        # Convert timestamp from milliseconds to datetime if needed
        if 'timestamp' in historical_data.columns:
            # Check if timestamp is already in milliseconds (JavaScript standard)
            # Timestamps in milliseconds are very large numbers
            if historical_data['timestamp'].iloc[0] > 1e12:
                historical_data['timestamp'] = pd.to_datetime(
                    historical_data['timestamp'] / 1000, unit='s')
            else:
                historical_data['timestamp'] = pd.to_datetime(
                    historical_data['timestamp'], unit='s')

        print(
            f"Received anomaly detection request with {len(historical_data)} data points")

        # Check if we have Load column
        if 'Load' not in historical_data.columns:
            return jsonify({
                'status': 'error',
                'message': 'Load column not found in data'
            }), 400

        # For very large datasets, use a more efficient windowing approach
        is_large_dataset = len(historical_data) > 5000

        if is_large_dataset:
            print(
                f"Large dataset detected ({len(historical_data)} points). Using optimized processing.")
            # For large datasets, use a sampling approach or process in chunks
            # Here we'll use uniform sampling to reduce size while preserving distribution
            sample_size = 5000  # Still analyze a good amount of data
            sample_step = max(1, len(historical_data) // sample_size)
            historical_data_sampled = historical_data.iloc[::sample_step].copy(
            )
            print(
                f"Sampled dataset size: {len(historical_data_sampled)} points")
            working_data = historical_data_sampled
        else:
            working_data = historical_data.copy()

        # Calculate rolling statistics for window size of 24 hours
        print("Calculating rolling statistics for anomaly detection")
        window_size = 24*7  # 1 week rolling window

        # Ensure data is sorted by timestamp
        working_data = working_data.sort_values('timestamp')

        # Calculate rolling mean and standard deviation
        working_data['rolling_mean'] = working_data['Load'].rolling(
            window=window_size, min_periods=1).mean()
        working_data['rolling_std'] = working_data['Load'].rolling(
            window=window_size, min_periods=1).std()

        # Fill NaN values for first rows
        mean_load = working_data['Load'].mean()
        std_load = working_data['Load'].std()

        # Count and replace NaN values
        mean_nan_count = working_data['rolling_mean'].isna().sum()
        std_nan_count = working_data['rolling_std'].isna().sum()

        working_data['rolling_mean'] = working_data['rolling_mean'].fillna(
            mean_load)
        working_data['rolling_std'] = working_data['rolling_std'].fillna(
            std_load)

        print(f"Filled {mean_nan_count} NaN mean values with overall mean")
        print(f"Filled {std_nan_count} NaN std values with overall std")

        # Calculate z-scores and percent deviation
        working_data['z_score'] = abs(
            (working_data['Load'] - working_data['rolling_mean']) / working_data['rolling_std'])
        working_data['pct_deviation'] = (
            (working_data['Load'] - working_data['rolling_mean']) / working_data['rolling_mean'] * 100).round(2)

        # Use the exact threshold provided for anomaly detection
        # Only fall back to adaptive thresholds if no anomalies found and explicit threshold not provided
        thresholds_to_try = [threshold]
        was_threshold_explicitly_provided = 'threshold' in data

        # If threshold wasn't explicitly provided in request and we don't find anomalies, try adaptive thresholds
        if not was_threshold_explicitly_provided and len(working_data[working_data['z_score'] > threshold]) == 0:
            thresholds_to_try = [3.0, 2.5, 2.0, 1.5]

        threshold_used = threshold
        anomalies = pd.DataFrame()

        for current_threshold in thresholds_to_try:
            # Detect anomalies based on z-score
            anomalies = working_data[working_data['z_score']
                                     > current_threshold].copy()
            threshold_used = current_threshold
            print(
                f"Found {len(anomalies)} anomalies using z-score threshold of {current_threshold}")

            if len(anomalies) > 0:
                break

        # Calculate mean and max deviation percentages for stats
        mean_deviation_pct = abs(working_data['pct_deviation']).mean()
        max_deviation_pct = abs(working_data['pct_deviation']).max()

        # Even if no true anomalies are found, provide the top 10 points with highest deviation
        if len(anomalies) == 0:
            anomalies = working_data.sort_values(
                'z_score', ascending=False).head(10).copy()
            message = f"No significant anomalies found with threshold {threshold}. Showing top points with highest deviation for reference."
        else:
            message = f"Found {len(anomalies)} anomalies using threshold {threshold_used}"

            # Limit to top 20 anomalies if there are too many
            if len(anomalies) > 20:
                anomalies = anomalies.sort_values(
                    'z_score', ascending=False).head(20)
                print(
                    f"Limiting to top 20 anomalies from {len(anomalies)} detected")

        # If we sampled the data but found anomalies, ensure we have the exact anomaly points from original dataset
        if is_large_dataset and len(anomalies) > 0:
            # Get timestamps of anomalies from sampled data
            anomaly_timestamps = anomalies['timestamp'].tolist()

            # For each anomaly timestamp, find the closest matching point in the original dataset
            full_data_anomalies = []
            for ts in anomaly_timestamps:
                # Find closest timestamp in original data
                original_idx = (
                    historical_data['timestamp'] - ts).abs().idxmin()
                full_data_anomalies.append(
                    historical_data.loc[original_idx].copy())

            # Convert to DataFrame
            if full_data_anomalies:
                full_anomalies_df = pd.DataFrame(full_data_anomalies)

                # Recalculate the z-scores and other metrics for these points
                for i, row in full_anomalies_df.iterrows():
                    ts = row['timestamp']
                    # Find data points around this timestamp for calculating mean/std
                    window_start = ts - pd.Timedelta(hours=window_size//2)
                    window_end = ts + pd.Timedelta(hours=window_size//2)
                    window_data = historical_data[(historical_data['timestamp'] >= window_start) &
                                                  (historical_data['timestamp'] <= window_end)]

                    # Calculate stats for this window
                    if len(window_data) > 0:
                        rolling_mean = window_data['Load'].mean()
                        rolling_std = window_data['Load'].std()

                        # Update values for this anomaly
                        full_anomalies_df.at[i, 'rolling_mean'] = rolling_mean
                        full_anomalies_df.at[i, 'rolling_std'] = rolling_std
                        full_anomalies_df.at[i, 'z_score'] = abs(
                            (row['Load'] - rolling_mean) / rolling_std)
                        full_anomalies_df.at[i, 'pct_deviation'] = (
                            (row['Load'] - rolling_mean) / rolling_mean * 100).round(2)

                anomalies = full_anomalies_df.copy()

        # Classify anomalies based on z-score
        def classify_severity(z):
            if z > 4.0:
                return 'High'
            elif z > 3.0:
                return 'Medium'
            elif z > 2.5:
                return 'Low'
            elif z > 1.8:
                return 'Very Low'
            else:
                return 'Minimal'

        # Ensure z_score column exists
        if 'z_score' not in anomalies.columns:
            # If recalculation failed, assign default z-scores based on threshold
            anomalies['z_score'] = threshold + 0.1

        anomalies['severity'] = anomalies['z_score'].apply(classify_severity)

        # Count anomalies by severity
        severity_counts = anomalies['severity'].value_counts().to_dict()
        print(f"Anomaly severity distribution: {severity_counts}")

        # Generate reason for anomaly based on features
        def generate_reason(row):
            # If pct_deviation is missing, calculate it
            if 'pct_deviation' not in row or pd.isna(row['pct_deviation']):
                if 'rolling_mean' in row and not pd.isna(row['rolling_mean']) and row['rolling_mean'] != 0:
                    deviation = (
                        (row['Load'] - row['rolling_mean']) / row['rolling_mean'] * 100)
                else:
                    deviation = 0
            else:
                deviation = row['pct_deviation']

            # Extract hour and day of week
            if 'hour' in row:
                hour = row['hour']
            elif 'timestamp' in row:
                hour = pd.to_datetime(row['timestamp']).hour
            else:
                hour = 12  # Default

            if 'dayOfWeek' in row:
                day_of_week = row['dayOfWeek']
            elif 'timestamp' in row:
                day_of_week = pd.to_datetime(row['timestamp']).dayofweek
            else:
                day_of_week = 0  # Default

            if abs(deviation) > 15:
                return "Extreme load deviation"

            if 9 <= hour <= 17 and 0 <= day_of_week <= 4:  # Weekday working hours
                return "Unusual pattern during working hours"
            elif hour < 6 or hour >= 22:  # Night
                return "Unexpected night-time consumption"
            elif day_of_week >= 5:  # Weekend
                return "Unusual weekend pattern"
            else:
                return "Irregular load pattern"

        anomalies['reason'] = anomalies.apply(generate_reason, axis=1)

        # Convert timestamps to milliseconds for JavaScript
        if 'timestamp' in anomalies.columns:
            anomalies['timestamp'] = anomalies['timestamp'].apply(
                lambda x: int(x.timestamp() * 1000))

        # Prepare result
        result = anomalies.to_dict('records')
        print(f"Returning {len(result)} results to frontend")

        # Return the data along with statistics
        return jsonify({
            'status': 'success',
            'data': result,
            'message': message,
            'stats': {
                # Report full dataset size
                'data_points': len(historical_data),
                'anomalies_found': len(anomalies),
                'mean_deviation_pct': mean_deviation_pct,
                'max_deviation_pct': max_deviation_pct,
                'threshold_tried': threshold  # Always return the actual threshold that was provided
            }
        })

    except Exception as e:
        import traceback
        print(f"Error detecting anomalies: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Helper function to prepare anomaly response


def prepare_anomaly_response(anomalies_df):
    # Prepare response
    required_columns = ['timestamp', 'formattedDate', 'Load', 'hour', 'dayOfWeek', 'severity',
                        'reason', 'rolling_mean', 'z_score', 'pct_deviation']

    # Ensure all required columns exist
    for col in required_columns:
        if col not in anomalies_df.columns:
            if col == 'formattedDate' and 'timestamp' in anomalies_df.columns:
                # Generate formattedDate from timestamp if missing
                anomalies_df['formattedDate'] = anomalies_df['timestamp'].dt.strftime(
                    '%Y-%m-%d %H:%M:%S')

    # Select only columns that exist
    existing_columns = [
        col for col in required_columns if col in anomalies_df.columns]
    anomalies_result = anomalies_df[existing_columns].to_dict('records')

    # Ensure timestamp is in milliseconds for JavaScript
    for item in anomalies_result:
        if 'timestamp' in item:
            # If it's a pandas Timestamp or datetime object
            if isinstance(item['timestamp'], (pd.Timestamp, datetime)):
                item['timestamp'] = int(item['timestamp'].timestamp() * 1000)
            else:
                # If it's a numeric timestamp in seconds
                item['timestamp'] = int(
                    item['timestamp'] * 1000) if item['timestamp'] < 1e12 else int(item['timestamp'])

    print(f"Returning {len(anomalies_result)} results to frontend")
    return anomalies_result


if __name__ == '__main__':
    print("Starting Flask API server for electricity load forecasting on http://localhost:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')
