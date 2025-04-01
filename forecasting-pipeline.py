import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import statsmodels.api as sm
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
import logging
import os
import warnings
import logging.handlers
import joblib
import json
from pathlib import Path
warnings.filterwarnings('ignore')

# Configure logging
def setup_logger():
    """Set up and configure logger for the application."""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configure logger
    logger = logging.getLogger('energy_forecasting')
    
    # Only set up handlers if they don't exist already
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create handlers
        # Use RotatingFileHandler for better log management
        file_handler = logging.handlers.RotatingFileHandler(
            'logs/energy_forecasting.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        console_handler = logging.StreamHandler()
        
        # Create formatter and add it to handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logger.info("Logger initialized")
    
    return logger

# Initialize logger
logger = setup_logger()

# Set matplotlib style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette('viridis')

# Define a class for the energy forecasting pipeline


class EnergyForecastingPipeline:
    def __init__(self, data_path):
        """Initialize the energy forecasting pipeline with data path."""
        logger.info(f"Initializing EnergyForecastingPipeline with data path: {data_path}")
        self.data_path = data_path
        self.df = None
        self.models = {}
        self.model_metrics = {}
        self.best_model = None
        self.forecast_hours = 24  # Default forecast horizon
        logger.info("Pipeline initialized successfully")

    def load_data(self):
        """Load and prepare the dataset."""
        logger.info(f"Loading data from: {self.data_path}")
        
        try:
            self.df = pd.read_csv(self.data_path)
            logger.info(f"Successfully loaded data with shape: {self.df.shape}")
            
            # Convert Date column to datetime
            logger.info("Converting Date column to datetime format")
            self.df['Date'] = pd.to_datetime(self.df['Date'])

            # Set Date as index
            self.df.set_index('Date', inplace=True)

            # Sort by date
            self.df.sort_index(inplace=True)
            logger.info(f"Data timespan: {self.df.index.min()} to {self.df.index.max()}")

            # Check for duplicates
            duplicate_count = self.df.index.duplicated().sum()
            if duplicate_count > 0:
                logger.warning(
                    f"Found {duplicate_count} duplicate timestamps. Removing duplicates.")
                self.df = self.df[~self.df.index.duplicated()]

            # Check for missing values
            missing_values = self.df.isnull().sum()
            if missing_values.sum() > 0:
                logger.warning(f"Found missing values:\n{missing_values}")
                # For now, forward fill missing values
                self.df.fillna(method='ffill', inplace=True)
                logger.info("Missing values filled using forward fill method")
            else:
                logger.info("No missing values found in the dataset")
                
            logger.info(f"Data preparation completed. Final shape: {self.df.shape}")
            return self.df
            
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            raise

    def explore_data(self, save_plots=True):
        """
        Perform exploratory data analysis on the dataset.

        Args:
            save_plots (bool): Whether to save the plots to disk
        """
        if self.df is None:
            self.load_data()

        # Create directory for plots
        if save_plots:
            if not os.path.exists('plots'):
                os.makedirs('plots')

        # Basic statistics
        logger.info("Basic Statistics:")
        logger.info(self.df.describe())

        # Time series visualization
        plt.figure(figsize=(14, 6))
        plt.plot(self.df.index, self.df['Load'])
        plt.title('Energy Load Over Time')
        plt.xlabel('Date')
        plt.ylabel('Load (MWh)')
        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/load_time_series.png')
        plt.show()

        # Seasonal decomposition
        decomposition = seasonal_decompose(
            self.df['Load'], model='additive', period=24)
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 12))
        decomposition.observed.plot(ax=ax1)
        ax1.set_title('Observed')
        decomposition.trend.plot(ax=ax2)
        ax2.set_title('Trend')
        decomposition.seasonal.plot(ax=ax3)
        ax3.set_title('Seasonality')
        decomposition.resid.plot(ax=ax4)
        ax4.set_title('Residuals')
        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/seasonal_decomposition.png')
        plt.show()

        # Add time features for better visualization
        temp_df = self.df.copy()
        temp_df['hour'] = temp_df.index.hour
        temp_df['day_of_week'] = temp_df.index.dayofweek
        temp_df['month'] = temp_df.index.month
        temp_df['is_weekend'] = temp_df.index.dayofweek.isin(
            [5, 6]).astype(int)

        # Hourly patterns
        plt.figure(figsize=(12, 6))
        sns.boxplot(x='hour', y='Load', data=temp_df)
        plt.title('Load Distribution by Hour of Day')
        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/load_by_hour.png')
        plt.show()

        # Daily patterns
        plt.figure(figsize=(10, 6))
        sns.boxplot(x='day_of_week', y='Load', data=temp_df)
        plt.title('Load Distribution by Day of Week')
        plt.xticks(range(7), ['Monday', 'Tuesday', 'Wednesday',
                   'Thursday', 'Friday', 'Saturday', 'Sunday'])
        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/load_by_day.png')
        plt.show()

        # Monthly patterns
        plt.figure(figsize=(12, 6))
        sns.boxplot(x='month', y='Load', data=temp_df)
        plt.title('Load Distribution by Month')
        plt.xticks(range(12), ['Jan', 'Feb', 'Mar', 'Apr', 'May',
                   'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/load_by_month.png')
        plt.show()

        # Correlation heatmap
        plt.figure(figsize=(10, 8))
        correlation_matrix = self.df.corr()
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt='.2f')
        plt.title('Correlation Matrix')
        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/correlation_heatmap.png')
        plt.show()

        # Scatter plots for relationships
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # Load vs Temperature
        sns.scatterplot(x='Temperature', y='Load',
                        data=self.df, ax=axes[0, 0], alpha=0.5)
        axes[0, 0].set_title('Load vs Temperature')

        # Load vs Cloudiness
        sns.scatterplot(x='Cloudiness', y='Load',
                        data=self.df, ax=axes[0, 1], alpha=0.5)
        axes[0, 1].set_title('Load vs Cloudiness')

        # Load vs Irradiation
        sns.scatterplot(x='Irradiation', y='Load',
                        data=self.df, ax=axes[1, 0], alpha=0.5)
        axes[1, 0].set_title('Load vs Irradiation')

        # Load vs PublicHolidays
        sns.boxplot(x='PublicHolidays', y='Load', data=self.df, ax=axes[1, 1])
        axes[1, 1].set_title('Load Distribution by Public Holiday Status')
        axes[1, 1].set_xticklabels(['Regular Day', 'Public Holiday'])

        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/load_vs_features.png')
        plt.show()

        # Temperature relationship by season
        temp_df['season'] = temp_df.index.month.map({
            1: 'Winter', 2: 'Winter', 3: 'Spring', 4: 'Spring',
            5: 'Spring', 6: 'Summer', 7: 'Summer', 8: 'Summer',
            9: 'Fall', 10: 'Fall', 11: 'Fall', 12: 'Winter'
        })

        plt.figure(figsize=(16, 10))
        for i, season in enumerate(['Winter', 'Spring', 'Summer', 'Fall']):
            season_data = temp_df[temp_df['season'] == season]
            plt.subplot(2, 2, i+1)
            sns.scatterplot(x='Temperature', y='Load',
                            data=season_data, alpha=0.5)

            # Add regression line
            x = season_data['Temperature']
            y = season_data['Load']
            coefficients = np.polyfit(x, y, 1)
            polynomial = np.poly1d(coefficients)
            xs = np.linspace(x.min(), x.max(), 100)
            ys = polynomial(xs)
            plt.plot(xs, ys, color='red')

            plt.title(f'Load vs Temperature in {season}')

        plt.tight_layout()
        if save_plots:
            plt.savefig('plots/load_temp_by_season.png')
        plt.show()

        # Return to original dataframe
        return self.df

    def feature_engineering(self):
        """
        Create additional features for model training.

        Returns:
            pd.DataFrame: The dataframe with engineered features
        """
        logger.info("Starting feature engineering process")
        
        if self.df is None:
            logger.info("No data found. Loading dataset first")
            self.load_data()

        # Create a copy of the dataframe
        df_features = self.df.copy()
        
        # Track number of features before
        num_features_before = len(df_features.columns)
        logger.info(f"Initial number of features: {num_features_before}")

        # Add time-based features
        logger.info("Adding time-based features")
        df_features['hour'] = df_features.index.hour
        df_features['day_of_week'] = df_features.index.dayofweek
        df_features['month'] = df_features.index.month
        df_features['year'] = df_features.index.year
        df_features['day_of_year'] = df_features.index.dayofyear
        df_features['week_of_year'] = df_features.index.isocalendar().week
        df_features['is_weekend'] = df_features.index.dayofweek.isin([
                                                                     5, 6]).astype(int)

        # Create cyclical features for time variables
        logger.info("Adding cyclical encodings for time features")
        df_features['hour_sin'] = np.sin(2 * np.pi * df_features['hour']/24)
        df_features['hour_cos'] = np.cos(2 * np.pi * df_features['hour']/24)
        df_features['day_of_week_sin'] = np.sin(
            2 * np.pi * df_features['day_of_week']/7)
        df_features['day_of_week_cos'] = np.cos(
            2 * np.pi * df_features['day_of_week']/7)
        df_features['month_sin'] = np.sin(2 * np.pi * df_features['month']/12)
        df_features['month_cos'] = np.cos(2 * np.pi * df_features['month']/12)

        # Add lagged features
        logger.info("Adding lagged features for temporal patterns")
        df_features['load_lag1'] = df_features['Load'].shift(1)
        df_features['load_lag2'] = df_features['Load'].shift(2)
        df_features['load_lag3'] = df_features['Load'].shift(3)
        df_features['load_lag24'] = df_features['Load'].shift(
            24)  # Same hour yesterday
        df_features['load_lag48'] = df_features['Load'].shift(
            48)  # Same hour two days ago
        df_features['load_lag168'] = df_features['Load'].shift(
            168)  # Same hour last week

        # Create rolling average features
        logger.info("Adding rolling statistics")
        df_features['load_rolling_mean_6h'] = df_features['Load'].rolling(
            window=6).mean().shift(1)
        df_features['load_rolling_mean_12h'] = df_features['Load'].rolling(
            window=12).mean().shift(1)
        df_features['load_rolling_mean_24h'] = df_features['Load'].rolling(
            window=24).mean().shift(1)

        # Create temperature-based features
        logger.info("Adding temperature-derived features")
        # Non-linear relationship with load
        df_features['temp_squared'] = df_features['Temperature'] ** 2
        df_features['temp_lag1'] = df_features['Temperature'].shift(1)
        df_features['temp_lag24'] = df_features['Temperature'].shift(24)

        # Interaction features
        logger.info("Adding interaction features")
        df_features['temp_hour_interaction'] = df_features['Temperature'] * \
            df_features['hour']
        df_features['cloud_irradiation_interaction'] = df_features['Cloudiness'] * \
            df_features['Irradiation']

        # Remove NaN values created by lagged features
        null_count_before = df_features.isnull().sum().sum()
        df_features.dropna(inplace=True)
        rows_removed = null_count_before - df_features.isnull().sum().sum()
        logger.info(f"Removed {rows_removed} rows with NaN values")

        # Save the feature engineered data
        self.df_features = df_features
        
        # Track number of features after
        num_features_after = len(df_features.columns)
        logger.info(f"Feature engineering completed. Added {num_features_after - num_features_before} new features")
        logger.info(f"Final dataset shape: {df_features.shape}")
        
        return df_features

    def detect_anomalies(self, contamination=0.02, visualize=True):
        """
        Detect anomalies in the load data.

        Args:
            contamination (float): Expected proportion of anomalies
            visualize (bool): Whether to visualize the anomalies

        Returns:
            pd.DataFrame: DataFrame with anomaly labels
        """
        logger.info(f"Starting anomaly detection with contamination={contamination}")
        
        if not hasattr(self, 'df_features'):
            logger.info("Feature-engineered data not found. Running feature engineering first")
            self.feature_engineering()

        # Select features for anomaly detection
        features = [
            'Load', 'Temperature', 'Cloudiness', 'Irradiation',
            'hour', 'day_of_week', 'is_weekend', 'load_lag1',
            'load_lag24', 'load_rolling_mean_24h'
        ]
        
        logger.info(f"Using {len(features)} features for anomaly detection: {', '.join(features)}")

        X = self.df_features[features].copy()

        # Scale the data
        logger.info("Scaling features for anomaly detection")
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Use Isolation Forest for anomaly detection
        logger.info("Applying Isolation Forest algorithm")
        model = IsolationForest(contamination=contamination, random_state=42)
        anomaly_labels = model.fit_predict(X_scaled)

        # -1 for anomalies, 1 for normal points - let's convert to 0 and 1
        anomaly_df = self.df_features.copy()
        anomaly_df['anomaly'] = (anomaly_labels == -1).astype(int)
        isolation_forest_anomalies = anomaly_df['anomaly'].sum()
        logger.info(f"Isolation Forest identified {isolation_forest_anomalies} anomalies")

        # Calculate Z-scores for load
        logger.info("Calculating Z-scores for load values")
        load_mean = anomaly_df['Load'].mean()
        load_std = anomaly_df['Load'].std()
        anomaly_df['load_zscore'] = (anomaly_df['Load'] - load_mean) / load_std

        # Mark points with high Z-scores as potential anomalies as well
        zscore_threshold = 3.0
        anomaly_df['zscore_anomaly'] = (
            abs(anomaly_df['load_zscore']) > zscore_threshold).astype(int)
        zscore_anomalies = anomaly_df['zscore_anomaly'].sum()
        logger.info(f"Z-score method identified {zscore_anomalies} anomalies with threshold {zscore_threshold}")

        # Combine both anomaly detection methods
        anomaly_df['combined_anomaly'] = ((anomaly_df['anomaly'] == 1) |
                                          (anomaly_df['zscore_anomaly'] == 1)).astype(int)

        # Count anomalies
        anomaly_count = anomaly_df['combined_anomaly'].sum()
        logger.info(
            f"Combined approach detected {anomaly_count} anomalies ({anomaly_count/len(anomaly_df)*100:.2f}% of data)")
            
        # Log distribution of anomalies by month
        try:
            # Create a Series with month names for better readability
            month_names = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }
            
            # Filter anomalies first, then group by month
            anomalies_only = anomaly_df[anomaly_df['combined_anomaly'] == 1]
            monthly_counts = anomalies_only.groupby(anomalies_only.index.month).size()
            
            # Convert to a more readable format with month names
            monthly_anomalies = {month_names[month]: count for month, count in monthly_counts.items()}
            
            logger.info(f"Monthly distribution of anomalies: {monthly_anomalies}")
        except Exception as e:
            logger.warning(f"Could not calculate monthly anomaly distribution: {str(e)}")

        if visualize:
            logger.info("Generating anomaly visualization")
            plt.figure(figsize=(14, 8))
            plt.scatter(anomaly_df.index, anomaly_df['Load'],
                        c=anomaly_df['combined_anomaly'], cmap='coolwarm', alpha=0.7)
            plt.colorbar(label='Anomaly')
            plt.title('Detected Anomalies in Load Data')
            plt.xlabel('Date')
            plt.ylabel('Load (MWh)')
            plt.tight_layout()
            plt.savefig('plots/detected_anomalies.png')
            plt.show()

            # Show detailed view of anomalies
            anomaly_points = anomaly_df[anomaly_df['combined_anomaly'] == 1]

            logger.info("\nTop 10 anomalies by Z-score magnitude:")
            top_anomalies = anomaly_points.sort_values(by='load_zscore', ascending=False)[
                ['Load', 'Temperature', 'PublicHolidays',
                    'hour', 'day_of_week', 'load_zscore']
            ].head(10)
            logger.info(top_anomalies)

        self.anomaly_df = anomaly_df
        return anomaly_df

    def prepare_train_test_data(self, test_size=0.2, features=None):
        """
        Prepare data for model training and testing.

        Args:
            test_size (float): Proportion of data to use for testing
            features (list): List of features to use (if None, use default feature list)

        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        logger.info(f"Preparing training and test data with test_size={test_size}")
        
        if not hasattr(self, 'df_features'):
            logger.info("Feature-engineered data not found. Running feature engineering first")
            self.feature_engineering()

        # Validate test_size is in proper range
        if test_size <= 0 or test_size >= 1:
            logger.warning(f"Invalid test_size {test_size}, using default of 0.2")
            test_size = 0.2

        # Default feature list if none provided
        if features is None:
            features = [
                # Time features
                'hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos',
                'month_sin', 'month_cos', 'is_weekend',

                # Weather features
                'Temperature', 'temp_squared', 'Cloudiness', 'Irradiation',
                'cloud_irradiation_interaction',

                # Lag features
                'load_lag1', 'load_lag2', 'load_lag3', 'load_lag24',
                'load_lag48', 'load_lag168',

                # Rolling stats
                'load_rolling_mean_6h', 'load_rolling_mean_12h', 'load_rolling_mean_24h',

                # Special days
                'PublicHolidays'
            ]
            logger.info(f"Using default feature list with {len(features)} features")
        else:
            logger.info(f"Using provided feature list with {len(features)} features")
            
        # Validate all features exist in dataframe
        missing_features = [f for f in features if f not in self.df_features.columns]
        if missing_features:
            logger.error(f"The following features are missing from the dataframe: {missing_features}")
            raise ValueError(f"Missing features: {missing_features}")

        # Prepare X and y
        X = self.df_features[features]
        y = self.df_features['Load']
        
        logger.info(f"Data shape: X={X.shape}, y={y.shape}")

        # Check for missing values
        X_null_count = X.isnull().sum().sum()
        y_null_count = y.isnull().sum()
        
        if X_null_count > 0 or y_null_count > 0:
            logger.warning(f"Found missing values: X={X_null_count}, y={y_null_count}")
            logger.info("Dropping rows with missing values")
            valid_indices = ~(X.isnull().any(axis=1) | y.isnull())
            X = X[valid_indices]
            y = y[valid_indices]
            logger.info(f"After dropping missing values: X={X.shape}, y={y.shape}")

        # Use time-based split instead of random split
        train_end_idx = int(len(X) * (1 - test_size))
        
        if train_end_idx <= 0 or train_end_idx >= len(X):
            logger.error(f"Invalid train_end_idx {train_end_idx} for data of length {len(X)}")
            raise ValueError(f"Invalid split point: {train_end_idx}")

        X_train = X.iloc[:train_end_idx]
        X_test = X.iloc[train_end_idx:]
        y_train = y.iloc[:train_end_idx]
        y_test = y.iloc[train_end_idx:]
        
        logger.info(f"Train-test split: train={X_train.shape}, test={X_test.shape}")

        # Scale features
        logger.info("Scaling features")
        try:
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Check if scaling produced any NaN values
            if np.isnan(X_train_scaled).any() or np.isnan(X_test_scaled).any():
                logger.error("Scaling produced NaN values. Check your data for extreme values")
                raise ValueError("Scaling produced NaN values")
                
            logger.info("Scaling completed successfully")
        except Exception as e:
            logger.error(f"Error during feature scaling: {str(e)}")
            raise

        # Store the scaler for later use
        self.feature_scaler = scaler
        self.selected_features = features

        # Return both scaled and unscaled data
        self.train_test_data = {
            'X_train': X_train,
            'X_test': X_test,
            'y_train': y_train,
            'y_test': y_test,
            'X_train_scaled': X_train_scaled,
            'X_test_scaled': X_test_scaled
        }
        
        logger.info("Train-test data preparation completed")
        return self.train_test_data

    def train_models(self, include_models=None):
        """
        Train multiple models for comparison.

        Args:
            include_models (list): List of model names to include

        Returns:
            dict: Dictionary of trained models
        """
        if not hasattr(self, 'train_test_data'):
            logger.info("Training data not prepared. Preparing train/test split first")
            self.prepare_train_test_data()

        # Get training data
        X_train = self.train_test_data['X_train']
        y_train = self.train_test_data['y_train']
        X_train_scaled = self.train_test_data['X_train_scaled']
        
        logger.info(f"Training set size: {X_train.shape[0]} samples, {X_train.shape[1]} features")

        # Define models to train
        all_models = {
            'linear_regression': LinearRegression(),
            'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'gradient_boosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'xgboost': XGBRegressor(n_estimators=100, random_state=42),
            'svr': SVR(kernel='rbf')
        }

        # Filter models if specified
        if include_models is not None:
            models_to_train = {k: v for k,
                               v in all_models.items() if k in include_models}
            logger.info(f"Training requested models: {', '.join(include_models)}")
        else:
            models_to_train = all_models
            logger.info(f"Training all models: {', '.join(all_models.keys())}")

        logger.info(f"Training {len(models_to_train)} models...")

        # Train each model
        trained_models = {}
        for name, model in models_to_train.items():
            logger.info(f"Training {name} model...")
            start_time = datetime.now()

            # SVR and some other models may work better with scaled features
            if name in ['svr']:
                model.fit(X_train_scaled, y_train)
                trained_models[name] = {
                    'model': model, 'requires_scaling': True}
            else:
                model.fit(X_train, y_train)
                trained_models[name] = {
                    'model': model, 'requires_scaling': False}

            training_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Finished training {name} in {training_time:.2f} seconds")
            
            # Log feature importance if available
            if hasattr(model, 'feature_importances_'):
                feature_importance = pd.DataFrame({
                    'feature': X_train.columns,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False).head(10)
                logger.info(f"Top 10 features for {name}:\n{feature_importance.to_string()}")

        self.models = trained_models
        
        # Save the trained models
        self.save_models()
        
        return trained_models

    def save_models(self):
        """
        Save trained models to disk in models directory.
        
        Returns:
            list: Paths of saved model files
        """
        logger.info("Saving trained models to disk")
        
        # Make sure models directory exists
        if not os.path.exists('models'):
            os.makedirs('models')
            logger.info("Created models directory")
        
        saved_model_paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save each model
        for name, model_info in self.models.items():
            model = model_info['model']
            requires_scaling = model_info['requires_scaling']
            
            # Create filename
            model_filename = f"models/model_{name}_{timestamp}.joblib"
            
            # Save model
            try:
                joblib.dump(model, model_filename)
                saved_model_paths.append(model_filename)
                logger.info(f"Model {name} saved to {model_filename}")
                
                # Save metadata
                metadata_filename = f"models/model_{name}_{timestamp}_metadata.json"
                metadata = {
                    'model_type': name,
                    'timestamp': timestamp,
                    'requires_scaling': requires_scaling,
                    'features': self.selected_features,
                    'training_samples': len(self.train_test_data['X_train'])
                }
                
                with open(metadata_filename, 'w') as f:
                    json.dump(metadata, f, indent=4)
                logger.info(f"Model metadata saved to {metadata_filename}")
                
            except Exception as e:
                logger.error(f"Error saving model {name}: {str(e)}")
        
        # Also save the scaler if we have it
        if hasattr(self, 'feature_scaler'):
            scaler_filename = f"models/feature_scaler_{timestamp}.joblib"
            try:
                joblib.dump(self.feature_scaler, scaler_filename)
                saved_model_paths.append(scaler_filename)
                logger.info(f"Feature scaler saved to {scaler_filename}")
            except Exception as e:
                logger.error(f"Error saving feature scaler: {str(e)}")
        
        logger.info(f"Successfully saved {len(saved_model_paths)} model files")
        return saved_model_paths

    def evaluate_models(self, plot_predictions=True):
        """
        Evaluate trained models on test data.

        Args:
            plot_predictions (bool): Whether to plot actual vs predicted values

        Returns:
            dict: Dictionary with evaluation metrics
        """
        logger.info("Evaluating model performance on test data")
        
        if not hasattr(self, 'models'):
            logger.info("No trained models found. Training models first")
            self.train_models()

        # Get test data
        X_test = self.train_test_data['X_test']
        y_test = self.train_test_data['y_test']
        X_test_scaled = self.train_test_data['X_test_scaled']
        
        logger.info(f"Test set size: {X_test.shape[0]} samples")

        # Evaluate each model
        metrics = {}
        predictions = {}

        for name, model_info in self.models.items():
            logger.info(f"Evaluating {name} model...")
            model = model_info['model']
            requires_scaling = model_info['requires_scaling']

            # Make predictions
            if requires_scaling:
                y_pred = model.predict(X_test_scaled)
            else:
                y_pred = model.predict(X_test)

            # Store predictions
            predictions[name] = y_pred

            # Calculate metrics
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100

            metrics[name] = {
                'MSE': mse,
                'RMSE': rmse,
                'MAE': mae,
                'R²': r2,
                'MAPE': mape
            }

            logger.info(f"\nPerformance metrics for {name}:")
            logger.info(f"  RMSE: {rmse:.2f}")
            logger.info(f"  MAE: {mae:.2f}")
            logger.info(f"  R²: {r2:.4f}")
            logger.info(f"  MAPE: {mape:.2f}%")

        # Find the best model based on RMSE
        best_model = min(metrics.items(), key=lambda x: x[1]['RMSE'])
        logger.info(
            f"\nBest performing model: {best_model[0]} with RMSE: {best_model[1]['RMSE']:.2f}")
        self.best_model_name = best_model[0]

        # Plot predictions for each model
        if plot_predictions:
            logger.info("Generating prediction plots")
            # Create date range for test data
            test_dates = X_test.index

            # Plot predictions vs actual for each model
            plt.figure(figsize=(15, 10))
            plt.plot(test_dates, y_test, label='Actual',
                     color='black', linewidth=2)

            colors = ['blue', 'green', 'red', 'purple', 'orange']
            for i, (name, y_pred) in enumerate(predictions.items()):
                plt.plot(test_dates, y_pred, label=f'Predicted ({name})',
                         color=colors[i % len(colors)], alpha=0.7)

            plt.title('Actual vs Predicted Load')
            plt.xlabel('Date')
            plt.ylabel('Load (MWh)')
            plt.legend()
            plt.tight_layout()
            plt.savefig('plots/model_predictions.png')
            plt.show()

            # Plot a shorter time period for clarity (last 2 weeks)
            last_days = 14
            plt.figure(figsize=(15, 8))

            last_dates = test_dates[-24*last_days:]
            plt.plot(last_dates, y_test[-24*last_days:],
                     label='Actual', color='black', linewidth=2)

            for i, (name, y_pred) in enumerate(predictions.items()):
                plt.plot(last_dates, y_pred[-24*last_days:], label=f'Predicted ({name})',
                         color=colors[i % len(colors)], alpha=0.7)

            plt.title(f'Actual vs Predicted Load (Last {last_days} Days)')
            plt.xlabel('Date')
            plt.ylabel('Load (MWh)')
            plt.legend()
            plt.tight_layout()
            plt.savefig('plots/model_predictions_last_days.png')
            plt.show()

        self.model_metrics = metrics
        self.predictions = predictions
        
        # Save evaluation results
        self.save_evaluation(metrics, predictions, X_test, y_test)
        
        return metrics

    def save_evaluation(self, metrics, predictions, X_test, y_test):
        """
        Save model evaluation results to the evaluation directory.
        
        Args:
            metrics (dict): Dictionary with evaluation metrics
            predictions (dict): Dictionary with model predictions
            X_test (DataFrame): Test features
            y_test (Series): Test target values
            
        Returns:
            dict: Paths to saved evaluation files
        """
        logger.info("Saving model evaluation results to disk")
        
        # Make sure evaluation directory exists
        if not os.path.exists('evaluation'):
            os.makedirs('evaluation')
            logger.info("Created evaluation directory")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = {}
        
        # Save metrics to JSON
        metrics_filename = f"evaluation/metrics_{timestamp}.json"
        try:
            # Convert non-serializable values to strings or floats
            serializable_metrics = {}
            for model_name, model_metrics in metrics.items():
                serializable_metrics[model_name] = {
                    metric_name: float(metric_value) 
                    for metric_name, metric_value in model_metrics.items()
                }
            
            with open(metrics_filename, 'w') as f:
                json.dump(serializable_metrics, f, indent=4)
            saved_files['metrics'] = metrics_filename
            logger.info(f"Evaluation metrics saved to {metrics_filename}")
        except Exception as e:
            logger.error(f"Error saving evaluation metrics: {str(e)}")
        
        # Save predictions to CSV
        test_dates = X_test.index
        for model_name, y_pred in predictions.items():
            pred_filename = f"evaluation/predictions_{model_name}_{timestamp}.csv"
            try:
                # Create DataFrame with actual and predicted values
                pred_df = pd.DataFrame({
                    'date': test_dates,
                    'actual': y_test,
                    'predicted': y_pred,
                    'error': y_test - y_pred,
                    'abs_error': np.abs(y_test - y_pred),
                    'pct_error': (np.abs(y_test - y_pred) / y_test) * 100
                })
                pred_df.to_csv(pred_filename, index=False)
                saved_files[f'pred_{model_name}'] = pred_filename
                logger.info(f"Predictions for {model_name} saved to {pred_filename}")
            except Exception as e:
                logger.error(f"Error saving predictions for {model_name}: {str(e)}")
        
        # Save summary report
        report_filename = f"evaluation/summary_report_{timestamp}.txt"
        try:
            with open(report_filename, 'w') as f:
                f.write(f"MODEL EVALUATION SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
                
                # Write best model information
                best_model = min(metrics.items(), key=lambda x: x[1]['RMSE'])
                f.write(f"BEST MODEL: {best_model[0]}\n")
                f.write(f"RMSE: {best_model[1]['RMSE']:.4f}\n")
                f.write(f"R²: {best_model[1]['R²']:.4f}\n\n")
                
                # Write comparison table
                f.write("MODEL COMPARISON\n")
                f.write("-"*80 + "\n")
                f.write(f"{'Model':<20} {'RMSE':<10} {'MAE':<10} {'R²':<10} {'MAPE (%)':<10}\n")
                f.write("-"*80 + "\n")
                
                for model_name, model_metrics in metrics.items():
                    f.write(f"{model_name:<20} {model_metrics['RMSE']:<10.4f} {model_metrics['MAE']:<10.4f} {model_metrics['R²']:<10.4f} {model_metrics['MAPE']:<10.4f}\n")
                    
                f.write("\n\nTest set information:\n")
                f.write(f"Test samples: {len(y_test)}\n")
                f.write(f"Time period: {min(test_dates)} to {max(test_dates)}\n")
                
            saved_files['report'] = report_filename
            logger.info(f"Evaluation summary report saved to {report_filename}")
        except Exception as e:
            logger.error(f"Error saving evaluation summary report: {str(e)}")
        
        logger.info(f"Successfully saved {len(saved_files)} evaluation files")
        return saved_files

    def forecast_future(self, n_hours=24, plot_forecast=True):
        """
        Generate forecasts for future hours.

        Args:
            n_hours (int): Number of hours to forecast
            plot_forecast (bool): Whether to plot the forecast

        Returns:
            pd.DataFrame: DataFrame with forecast values
        """
        logger.info(f"Generating forecast for next {n_hours} hours")
        
        if not hasattr(self, 'models') or not hasattr(self, 'best_model_name'):
            logger.info("Models not trained or evaluated. Training and evaluating models first")
            self.train_models()
            self.evaluate_models(plot_predictions=False)

        # Set forecast horizon
        self.forecast_hours = n_hours

        # Get the best model
        best_model_info = self.models[self.best_model_name]
        best_model = best_model_info['model']
        requires_scaling = best_model_info['requires_scaling']
        
        logger.info(f"Using {self.best_model_name} model for forecasting")

        # Get the last known data point
        last_data = self.df_features.iloc[-1]
        logger.info(f"Last known timestamp: {self.df_features.index[-1]}")

        # Prepare dataframe for forecasts
        forecast_dates = [self.df_features.index[-1] +
                          timedelta(hours=i+1) for i in range(n_hours)]
        forecast_df = pd.DataFrame(index=forecast_dates)
        
        logger.info("Generating time features for forecast period")

        # Initialize first forecast row with time features
        for date in forecast_dates:
            forecast_df.loc[date, 'hour'] = date.hour
            forecast_df.loc[date, 'day_of_week'] = date.dayofweek
            forecast_df.loc[date, 'month'] = date.month
            forecast_df.loc[date, 'year'] = date.year
            forecast_df.loc[date, 'day_of_year'] = date.dayofyear
            forecast_df.loc[date, 'week_of_year'] = date.isocalendar()[1]
            forecast_df.loc[date, 'is_weekend'] = int(date.dayofweek in [5, 6])

            # Cyclical encoding
            forecast_df.loc[date, 'hour_sin'] = np.sin(
                2 * np.pi * date.hour/24)
            forecast_df.loc[date, 'hour_cos'] = np.cos(
                2 * np.pi * date.hour/24)
            forecast_df.loc[date, 'day_of_week_sin'] = np.sin(
                2 * np.pi * date.dayofweek/7)
            forecast_df.loc[date, 'day_of_week_cos'] = np.cos(
                2 * np.pi * date.dayofweek/7)
            forecast_df.loc[date, 'month_sin'] = np.sin(
                2 * np.pi * date.month/12)
            forecast_df.loc[date, 'month_cos'] = np.cos(
                2 * np.pi * date.month/12)

        # We need to simulate forecasting by iteratively predicting and updating lagged values
        # For simplicity, we'll assume weather variables and holidays are known
        # In a real scenario, these would need to be forecasted separately or provided

        logger.info("Generating weather feature approximations for forecast period")
        # Simplified approach: copy last day's weather pattern and repeat
        for i, date in enumerate(forecast_dates):
            hour_of_day = date.hour

            # Find recent similar hours for weather conditions (simplistic approach)
            similar_hours = self.df_features[
                (self.df_features.index.hour == hour_of_day) &
                (self.df_features.index.dayofweek == date.dayofweek)
            ].iloc[-4:]  # Last 4 similar hours

            # Use average of similar hours for weather variables
            forecast_df.loc[date,
                            'Temperature'] = similar_hours['Temperature'].mean()
            forecast_df.loc[date,
                            'Cloudiness'] = similar_hours['Cloudiness'].mean()
            forecast_df.loc[date,
                            'Irradiation'] = similar_hours['Irradiation'].mean()

            # Check for public holidays (simplistic approach)
            # In real scenarios, this would come from a calendar of holidays
            if date.month == 1 and date.day == 1:  # New Year
                forecast_df.loc[date, 'PublicHolidays'] = 1
                logger.info(f"Detected public holiday at {date}")
            else:
                forecast_df.loc[date, 'PublicHolidays'] = 0

            # Derived weather features
            forecast_df.loc[date,
                            'temp_squared'] = forecast_df.loc[date, 'Temperature'] ** 2

            # Interaction features
            forecast_df.loc[date, 'temp_hour_interaction'] = forecast_df.loc[date,
                                                                             'Temperature'] * forecast_df.loc[date, 'hour']
            forecast_df.loc[date, 'cloud_irradiation_interaction'] = forecast_df.loc[date,
                                                                                     'Cloudiness'] * forecast_df.loc[date, 'Irradiation']

        logger.info("Starting recursive forecasting process")
        # Now we'll forecast one hour at a time and update lagged values
        for i in range(n_hours):
            current_date = forecast_dates[i]
            
            if i % 6 == 0:  # Log progress every 6 hours
                logger.info(f"Forecasting hour {i+1}/{n_hours} - {current_date}")

            if i == 0:
                # For the first prediction, use known values for lags
                logger.info("Using historical data for initial lag features")
                forecast_df.loc[current_date,
                                'load_lag1'] = self.df_features['Load'].iloc[-1]
                forecast_df.loc[current_date,
                                'load_lag2'] = self.df_features['Load'].iloc[-2]
                forecast_df.loc[current_date,
                                'load_lag3'] = self.df_features['Load'].iloc[-3]

                # For day and week lags, use actual past values
                hours_in_day = 24
                hours_in_week = 168

                if len(self.df_features) > hours_in_day:
                    forecast_df.loc[current_date,
                                    'load_lag24'] = self.df_features['Load'].iloc[-hours_in_day]
                else:
                    forecast_df.loc[current_date,
                                    'load_lag24'] = self.df_features['Load'].mean()

                if len(self.df_features) > hours_in_day * 2:
                    forecast_df.loc[current_date,
                                    'load_lag48'] = self.df_features['Load'].iloc[-hours_in_day*2]
                else:
                    forecast_df.loc[current_date,
                                    'load_lag48'] = self.df_features['Load'].mean()

                if len(self.df_features) > hours_in_week:
                    forecast_df.loc[current_date,
                                    'load_lag168'] = self.df_features['Load'].iloc[-hours_in_week]
                else:
                    forecast_df.loc[current_date,
                                    'load_lag168'] = self.df_features['Load'].mean()

                # Rolling means
                forecast_df.loc[current_date,
                                'load_rolling_mean_6h'] = self.df_features['Load'].iloc[-6:].mean()
                forecast_df.loc[current_date,
                                'load_rolling_mean_12h'] = self.df_features['Load'].iloc[-12:].mean()
                forecast_df.loc[current_date,
                                'load_rolling_mean_24h'] = self.df_features['Load'].iloc[-24:].mean()

                # Temperature lags
                forecast_df.loc[current_date,
                                'temp_lag1'] = self.df_features['Temperature'].iloc[-1]
                forecast_df.loc[current_date, 'temp_lag24'] = self.df_features['Temperature'].iloc[-hours_in_day] if len(
                    self.df_features) > hours_in_day else self.df_features['Temperature'].mean()

            else:
                # For subsequent predictions, use previous predictions
                prev_date = forecast_dates[i-1]
                
                logger.debug(f"Updating lag features for hour {i+1} based on previous predictions")
                # Load lags
                if i >= 1:
                    forecast_df.loc[current_date,
                                    'load_lag1'] = forecast_df.loc[forecast_dates[i-1], 'Load']
                if i >= 2:
                    forecast_df.loc[current_date,
                                    'load_lag2'] = forecast_df.loc[forecast_dates[i-2], 'Load']
                if i >= 3:
                    forecast_df.loc[current_date,
                                    'load_lag3'] = forecast_df.loc[forecast_dates[i-3], 'Load']
                else:
                    # Use values from historical data for missing lags
                    missing_lags = 3 - i
                    for lag in range(missing_lags):
                        lag_idx = lag + 1
                        if lag_idx <= 3:  # Only set missing lags
                            forecast_df.loc[current_date,
                                            f'load_lag{lag_idx}'] = self.df_features['Load'].iloc[-(lag+1)]

                # Day lags
                hours_in_day = 24
                if i >= hours_in_day:
                    forecast_df.loc[current_date,
                                    'load_lag24'] = forecast_df.loc[forecast_dates[i-hours_in_day], 'Load']
                else:
                    forecast_df.loc[current_date,
                                    'load_lag24'] = self.df_features['Load'].iloc[-hours_in_day+i]

                if i >= hours_in_day*2:
                    forecast_df.loc[current_date,
                                    'load_lag48'] = forecast_df.loc[forecast_dates[i-hours_in_day*2], 'Load']
                else:
                    forecast_df.loc[current_date, 'load_lag48'] = self.df_features['Load'].iloc[-hours_in_day*2+i] if (
                        i < len(self.df_features)) else self.df_features['Load'].mean()

                # Week lags
                hours_in_week = 168
                if i >= hours_in_week:
                    forecast_df.loc[current_date,
                                    'load_lag168'] = forecast_df.loc[forecast_dates[i-hours_in_week], 'Load']
                else:
                    forecast_df.loc[current_date, 'load_lag168'] = self.df_features['Load'].iloc[-hours_in_week +
                                                                                                 i] if (-hours_in_week+i > -len(self.df_features)) else self.df_features['Load'].mean()

                # Rolling means - we need to calculate these based on the latest predictions
                if i >= 6:
                    forecast_df.loc[current_date,
                                    'load_rolling_mean_6h'] = forecast_df.loc[forecast_dates[i-6:i], 'Load'].mean()
                else:
                    # Mix of historical and predicted values
                    historical_count = min(6-i, len(self.df_features))
                    historical_mean = self.df_features['Load'].iloc[-historical_count:].mean(
                    ) if historical_count > 0 else 0
                    forecast_mean = forecast_df.loc[forecast_dates[:i], 'Load'].mean(
                    ) if i > 0 else 0

                    if historical_count == 0:
                        forecast_df.loc[current_date,
                                        'load_rolling_mean_6h'] = forecast_mean
                    elif i == 0:
                        forecast_df.loc[current_date,
                                        'load_rolling_mean_6h'] = historical_mean
                    else:
                        forecast_df.loc[current_date, 'load_rolling_mean_6h'] = (
                            historical_mean * historical_count + forecast_mean * i) / 6

                # Similar approach for 12h and 24h rolling means
                if i >= 12:
                    forecast_df.loc[current_date,
                                    'load_rolling_mean_12h'] = forecast_df.loc[forecast_dates[i-12:i], 'Load'].mean()
                else:
                    historical_count = min(12-i, len(self.df_features))
                    historical_mean = self.df_features['Load'].iloc[-historical_count:].mean(
                    ) if historical_count > 0 else 0
                    forecast_mean = forecast_df.loc[forecast_dates[:i], 'Load'].mean(
                    ) if i > 0 else 0

                    if historical_count == 0:
                        forecast_df.loc[current_date,
                                        'load_rolling_mean_12h'] = forecast_mean
                    elif i == 0:
                        forecast_df.loc[current_date,
                                        'load_rolling_mean_12h'] = historical_mean
                    else:
                        forecast_df.loc[current_date, 'load_rolling_mean_12h'] = (
                            historical_mean * historical_count + forecast_mean * i) / 12

                if i >= 24:
                    forecast_df.loc[current_date,
                                    'load_rolling_mean_24h'] = forecast_df.loc[forecast_dates[i-24:i], 'Load'].mean()
                else:
                    historical_count = min(24-i, len(self.df_features))
                    historical_mean = self.df_features['Load'].iloc[-historical_count:].mean(
                    ) if historical_count > 0 else 0
                    forecast_mean = forecast_df.loc[forecast_dates[:i], 'Load'].mean(
                    ) if i > 0 else 0

                    if historical_count == 0:
                        forecast_df.loc[current_date,
                                        'load_rolling_mean_24h'] = forecast_mean
                    elif i == 0:
                        forecast_df.loc[current_date,
                                        'load_rolling_mean_24h'] = historical_mean
                    else:
                        forecast_df.loc[current_date, 'load_rolling_mean_24h'] = (
                            historical_mean * historical_count + forecast_mean * i) / 24

                # Temperature lags
                if i >= 1:
                    forecast_df.loc[current_date,
                                    'temp_lag1'] = forecast_df.loc[forecast_dates[i-1], 'Temperature']
                else:
                    forecast_df.loc[current_date,
                                    'temp_lag1'] = self.df_features['Temperature'].iloc[-1]

                if i >= 24:
                    forecast_df.loc[current_date,
                                    'temp_lag24'] = forecast_df.loc[forecast_dates[i-24], 'Temperature']
                else:
                    forecast_df.loc[current_date, 'temp_lag24'] = self.df_features['Temperature'].iloc[-24 +
                                                                                                       i] if (-24+i > -len(self.df_features)) else self.df_features['Temperature'].mean()

            # Now make the prediction for this hour
            X_i = forecast_df.loc[current_date:current_date,
                                  self.selected_features]

            if requires_scaling:
                X_i_scaled = self.feature_scaler.transform(X_i)
                pred = best_model.predict(X_i_scaled)[0]
            else:
                pred = best_model.predict(X_i)[0]

            # Store prediction
            forecast_df.loc[current_date, 'Load'] = pred
            
            if i == 0:
                logger.info(f"First hour prediction: {pred:.2f} MWh for {current_date}")

        logger.info("Forecast generation completed")
        
        # Add confidence intervals (simplified approach)
        logger.info("Calculating confidence intervals for forecasts")
        rmse = self.model_metrics[self.best_model_name]['RMSE']
        forecast_df['Load_Lower'] = forecast_df['Load'] - 1.96 * rmse
        forecast_df['Load_Upper'] = forecast_df['Load'] + 1.96 * rmse
        
        # Log forecast summary
        forecast_summary = {
            'mean': forecast_df['Load'].mean(),
            'min': forecast_df['Load'].min(),
            'max': forecast_df['Load'].max(),
            'first_hour': forecast_df['Load'].iloc[0],
            'last_hour': forecast_df['Load'].iloc[-1],
            'confidence_width': 3.92 * rmse  # 2 * 1.96 * RMSE
        }
        logger.info(f"Forecast summary: Mean={forecast_summary['mean']:.2f}, Min={forecast_summary['min']:.2f}, Max={forecast_summary['max']:.2f} MWh")
        logger.info(f"95% confidence interval width: ±{forecast_summary['confidence_width']/2:.2f} MWh")

        # Plot the forecast
        if plot_forecast:
            logger.info("Generating forecast visualization")
            # Plot historical data + forecast
            plt.figure(figsize=(14, 8))

            # Plot historical data (last 7 days)
            hist_days = 7
            hist_data = self.df_features.iloc[-24*hist_days:]
            plt.plot(hist_data.index,
                     hist_data['Load'], label='Historical', color='blue')

            # Plot forecast
            plt.plot(forecast_df.index,
                     forecast_df['Load'], label='Forecast', color='red')

            # Plot confidence intervals
            plt.fill_between(forecast_df.index,
                             forecast_df['Load_Lower'],
                             forecast_df['Load_Upper'],
                             color='red', alpha=0.2, label='95% Confidence Interval')

            plt.title(f'Load Forecast for Next {n_hours} Hours')
            plt.xlabel('Date')
            plt.ylabel('Load (MWh)')
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plt.savefig('plots/load_forecast.png')
            logger.info("Forecast plot saved to plots/load_forecast.png")
            plt.show()

        self.forecast_df = forecast_df
        return forecast_df

    def run_pipeline(self, forecast_hours=24):
        """
        Run the complete pipeline from data loading to forecasting.

        Args:
            forecast_hours (int): Number of hours to forecast

        Returns:
            tuple: (forecast_df, anomaly_df, model_metrics)
        """
        start_time = datetime.now()
        logger.info(f"=== Starting Energy Forecasting Pipeline at {start_time} ===")
        logger.info(f"Forecast horizon: {forecast_hours} hours")
        
        # Initialize result containers
        anomaly_df = None
        forecast_df = None
        
        # Step 1: Load data
        logger.info("1. Loading data...")
        try:
            self.load_data()
            logger.info(f"Data loaded successfully: {self.df.shape[0]} records from {self.df.index.min()} to {self.df.index.max()}")
        except Exception as e:
            logger.error(f"Error in data loading stage: {str(e)}", exc_info=True)
            logger.error("Pipeline cannot continue without data. Exiting...")
            raise

        # Step 2: Explore data (can continue without it if this fails)
        logger.info("\n2. Exploring data...")
        try:
            self.explore_data()
            logger.info("Data exploration completed")
        except Exception as e:
            logger.error(f"Error in data exploration stage: {str(e)}", exc_info=True)
            logger.warning("Continuing pipeline without data exploration...")

        # Step 3: Feature engineering
        logger.info("\n3. Feature engineering...")
        try:
            features_df = self.feature_engineering()
            logger.info(f"Feature engineering completed: {features_df.shape[1]} features created")
        except Exception as e:
            logger.error(f"Error in feature engineering stage: {str(e)}", exc_info=True)
            logger.error("Pipeline cannot continue without feature engineering. Exiting...")
            raise

        # Step 4: Anomaly detection (can continue if this fails)
        logger.info("\n4. Detecting anomalies...")
        try:
            anomaly_df = self.detect_anomalies(visualize=False)  # Disable visualization for batch processing
            anomaly_count = anomaly_df['combined_anomaly'].sum()
            logger.info(f"Anomaly detection completed: {anomaly_count} anomalies found ({anomaly_count/len(anomaly_df)*100:.2f}%)")
        except Exception as e:
            logger.error(f"Error in anomaly detection stage: {str(e)}", exc_info=True)
            logger.warning("Continuing pipeline without anomaly detection...")
            # Use the feature engineered data without anomaly detection
            anomaly_df = self.df_features.copy() if hasattr(self, 'df_features') else None

        # Step 5: Prepare training and test data
        logger.info("\n5. Preparing training and test data...")
        try:
            train_test_data = self.prepare_train_test_data()
            X_train = train_test_data['X_train']
            X_test = train_test_data['X_test']
            logger.info(f"Data preparation completed: {X_train.shape[0]} training samples, {X_test.shape[0]} test samples")
        except Exception as e:
            logger.error(f"Error in data preparation stage: {str(e)}", exc_info=True)
            logger.error("Pipeline cannot continue without data preparation. Exiting...")
            raise

        # Step 6: Train models
        logger.info("\n6. Training models...")
        try:
            models = self.train_models()
            logger.info(f"Model training completed: {len(models)} models trained")
        except Exception as e:
            logger.error(f"Error in model training stage: {str(e)}", exc_info=True)
            logger.error("Pipeline cannot continue without trained models. Exiting...")
            raise

        # Step 7: Evaluate models
        logger.info("\n7. Evaluating models...")
        try:
            metrics = self.evaluate_models(plot_predictions=False)  # Disable plotting for batch processing
            best_model = min(metrics.items(), key=lambda x: x[1]['RMSE'])
            logger.info(f"Model evaluation completed. Best model: {best_model[0]}, RMSE: {best_model[1]['RMSE']:.2f}")
        except Exception as e:
            logger.error(f"Error in model evaluation stage: {str(e)}", exc_info=True)
            logger.error("Pipeline cannot continue without model evaluation. Exiting...")
            raise

        # Step 8: Forecasting
        logger.info("\n8. Forecasting next hours...")
        try:
            forecast_df = self.forecast_future(n_hours=forecast_hours, plot_forecast=False)  # Disable plotting for batch processing
            logger.info(f"Forecasting completed: {len(forecast_df)} hours forecasted")
        except Exception as e:
            logger.error(f"Error in forecasting stage: {str(e)}", exc_info=True)
            logger.error("Pipeline cannot complete forecasting. Exiting...")
            raise
            
        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds()
        logger.info(f"=== Pipeline execution completed in {runtime:.2f} seconds ===")

        return forecast_df, anomaly_df, self.model_metrics


def main():
    """Main function to run the energy forecasting pipeline as a script."""
    logger.info("Starting energy consumption forecasting application")
    
    try:
        # Ensure required directories exist
        import os
        for directory in ['logs', 'plots', 'models', 'evaluation']:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Created {directory} directory")
        
        # Check if input file exists
        input_file = 'DS_ElectricityLoad.csv'
        if not os.path.exists(input_file):
            logger.error(f"Input file {input_file} not found!")
            raise FileNotFoundError(f"Required data file {input_file} not found")
        
        logger.info(f"Using input file: {input_file}")
        
        # Initialize the pipeline
        pipeline = EnergyForecastingPipeline(input_file)
        
        # Define forecast horizon
        forecast_hours = 24
        logger.info(f"Forecast horizon set to {forecast_hours} hours")

        # Run the complete pipeline with 24-hour forecast
        try:
            forecast, anomalies, metrics = pipeline.run_pipeline(forecast_hours=forecast_hours)
            
            # Log forecast results
            logger.info("\nForecast for the next 24 hours:")
            if forecast is not None:
                forecast_summary = forecast[['Load', 'Load_Lower', 'Load_Upper']].describe()
                logger.info(f"Forecast summary statistics:\n{forecast_summary}")
            else:
                logger.warning("No forecast data was generated")
            
            # Log model performance
            if metrics and hasattr(pipeline, 'best_model_name'):
                best_model = pipeline.best_model_name
                logger.info("\nBest model performance:")
                logger.info(f"Model: {best_model}")
                logger.info(f"RMSE: {metrics[best_model]['RMSE']:.2f}")
                logger.info(f"MAE: {metrics[best_model]['MAE']:.2f}")
                logger.info(f"R²: {metrics[best_model]['R²']:.4f}")
                logger.info(f"MAPE: {metrics[best_model]['MAPE']:.2f}%")
            else:
                logger.warning("No model metrics available")
                
            # Save forecast to CSV
            if forecast is not None:
                forecast_file = 'forecast_output.csv'
                forecast.to_csv(forecast_file)
                logger.info(f"Forecast saved to {forecast_file}")
            
            logger.info("Application completed successfully")
            return 0
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
            return 1
            
    except Exception as e:
        logger.error(f"Application failed with error: {str(e)}", exc_info=True)
        return 1


# Example usage
if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
