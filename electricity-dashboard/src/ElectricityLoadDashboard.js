import React, { useState, useEffect } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, ComposedChart, PieChart, Pie, Cell, Scatter } from 'recharts';
import _ from 'lodash';

const ElectricityLoadDashboard = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [forecastData, setForecastData] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [timeRange, setTimeRange] = useState('week'); // 'day', 'week', 'month', 'year'
  const [selectedTab, setSelectedTab] = useState('overview'); // 'overview', 'patterns', 'forecast', 'anomalies'
  const [selectedModel, setSelectedModel] = useState('gradient_boosting');
  const [forecastHorizon, setForecastHorizon] = useState(24);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [loadingAnomalies, setLoadingAnomalies] = useState(false);
  const [anomalyMessage, setAnomalyMessage] = useState('');
  const [anomalyStats, setAnomalyStats] = useState(null);
  const [forecastError, setForecastError] = useState('');
  const [anomalyThreshold, setAnomalyThreshold] = useState(2.0); // Default threshold value

  // Fetch historical data from CSV
  const fetchHistoricalData = async () => {
    try {
      // Load CSV data
      const response = await fetch('/DS_ElectricityLoad.csv');
      const csvText = await response.text();

      // Parse CSV
      const Papa = await import('papaparse');
      const parsed = Papa.default.parse(csvText, {
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true
      });
      
      // Process the data
      const processedData = parsed.data.map(row => {
        const date = new Date(row.Date);
        return {
          ...row,
          timestamp: date.getTime(),
          hour: date.getHours(),
          dayOfWeek: date.getDay(),
          month: date.getMonth(),
          year: date.getFullYear(),
          dayOfMonth: date.getDate(),
          formattedDate: date.toLocaleString()
        };
      });
      
      setData(processedData);
      return processedData;
    } catch (error) {
      console.error('Error loading historical data:', error);
      return [];
    }
  };

  // Effect hook to load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const historicalData = await fetchHistoricalData();
        if (historicalData.length > 0) {
          await fetchForecasts(historicalData, selectedModel, forecastHorizon);
          await fetchAnomalies(historicalData);
        }
        setLoading(false);
      } catch (error) {
        console.error('Error in initial data load:', error);
        setLoading(false);
      }
    };
    loadData();
  }, []); // No dependencies needed since this should only run once on mount
  
  // Fetch forecasts from API 
  const fetchForecasts = async (historicalData, modelType, horizon) => {
    try {
      setLoadingForecast(true);
      setForecastError('');
      
      // Get more context data for more accurate forecasting based on horizon
      // For longer horizons, we need more historical context
      const contextLength = Math.max(168, horizon * 2); // At least a week of data or 2x the horizon
      const contextData = historicalData.slice(-contextLength);  
      
      console.log(`Fetching forecast for model: ${modelType}, horizon: ${horizon} hours, using ${contextData.length} data points`);
      
      const response = await fetch('http://localhost:5000/api/forecast', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          historicalData: contextData,
          model_type: modelType,
          horizon: horizon
        }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Error ${response.status}: ${errorText}`);
        setForecastError(`Server error (${response.status}): ${errorText}`);
        generateMockForecastData(historicalData, horizon);
        setLoadingForecast(false);
        return;
      }
      
      const result = await response.json();
      
      if (result.status === 'success') {
        console.log(`Received ${result.data.length} data points, including forecast data.`);
        setForecastData(result.data);
      } else {
        console.error('Error fetching forecasts:', result.message);
        setForecastError(`Error: ${result.message}`);
        // Fall back to mock data for demo purposes
        generateMockForecastData(historicalData, horizon);
      }
      
      setLoadingForecast(false);
    } catch (error) {
      console.error('Error fetching forecasts:', error);
      setForecastError(`Error: ${error.message}`);
      // Fall back to mock data for demo purposes
      generateMockForecastData(historicalData, horizon);
      setLoadingForecast(false);
    }
  };
  
  // Fall back to mock forecast data if API fails
  const generateMockForecastData = (historicalData, horizon = 24) => {
    const lastTimestamp = historicalData[historicalData.length - 1].timestamp;
    const mockForecast = [];
        
        // Last 24 hours of actual data
    const lastDayData = historicalData.slice(-24);
    mockForecast.push(...lastDayData.map(item => ({...item, isForecast: false})));
        
    // Next N hours of forecasted data based on horizon
    for (let i = 1; i <= horizon; i++) {
          const lastDate = new Date(lastTimestamp + i * 60 * 60 * 1000);
          const hour = lastDate.getHours();
          
          let baseLoad;
          if (hour >= 0 && hour < 6) {
            baseLoad = 14000 + Math.random() * 1000;
          } else if (hour >= 6 && hour < 12) {
            baseLoad = 18000 + Math.random() * 1500;
          } else if (hour >= 12 && hour < 18) {
            baseLoad = 19500 + Math.random() * 1000;
          } else {
            baseLoad = 17000 + Math.random() * 1500;
          }
          
          mockForecast.push({
            timestamp: lastDate.getTime(),
            formattedDate: lastDate.toLocaleString(),
            Load: baseLoad,
            isForecast: true,
            hour: lastDate.getHours(),
            dayOfWeek: lastDate.getDay(),
            LowerBound: baseLoad - 1000,
            UpperBound: baseLoad + 1000
          });
        }
        
    setForecastData(mockForecast);
  };
  
  // Fetch anomalies from API
  const fetchAnomalies = async (historicalData, threshold = anomalyThreshold) => {
    try {
      setLoadingAnomalies(true);
      setAnomalyMessage('');
      setAnomalyStats(null);
      
      // Use all data points for analysis instead of limiting to 2000
      console.log(`Fetching anomalies with ${historicalData.length} data points, threshold: ${threshold}`);
      
      const response = await fetch('http://localhost:5000/api/anomalies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          historicalData: historicalData,
          threshold: threshold
        }),
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        console.log(`Received ${result.data.length} anomalies from API`);
        setAnomalies(result.data);
        
        // Set message if provided
        if (result.message) {
          setAnomalyMessage(result.message);
        }
        
        // Set stats if provided
        if (result.stats) {
          setAnomalyStats(result.stats);
        }
      } else {
        console.error('Error fetching anomalies:', result.message);
        setAnomalyMessage(`Error: ${result.message}`);
        // Fall back to mock anomalies for demo purposes
        generateMockAnomalies(historicalData);
      }
      
      setLoadingAnomalies(false);
    } catch (error) {
      console.error('Error fetching anomalies:', error);
      setAnomalyMessage(`Error: ${error.message}`);
      // Fall back to mock anomalies for demo purposes
      generateMockAnomalies(historicalData);
      setLoadingAnomalies(false);
    }
  };
  
  // Fall back to mock anomalies if API fails
  const generateMockAnomalies = (historicalData) => {
    console.log("Generating mock anomalies as fallback");
    const mockAnomalies = [];
    for (let i = 0; i < 5; i++) {
      const randomIndex = Math.floor(Math.random() * (historicalData.length - 24)) + 24;
      const anomalyPoint = { ...historicalData[randomIndex] };
      
      // Add derived fields for consistency with API
      const expectedLoad = anomalyPoint.Load * (Math.random() * 0.4 + 0.8); // Random expected load for demo
      anomalyPoint.rolling_mean = expectedLoad;
      anomalyPoint.pct_deviation = ((anomalyPoint.Load - expectedLoad) / expectedLoad * 100).toFixed(2);
      anomalyPoint.z_score = Math.abs((anomalyPoint.Load - expectedLoad) / (expectedLoad * 0.1));
      
      anomalyPoint.reason = ['Unexpected spike', 'Holiday effect', 'Weather anomaly', 'System error', 'Unknown factor'][i];
      anomalyPoint.severity = ['High', 'Medium', 'Low'][Math.floor(Math.random() * 3)];
      mockAnomalies.push(anomalyPoint);
    }
    setAnomalies(mockAnomalies);
  };
  
  // Update forecast when model or horizon changes
  useEffect(() => {
    if (data.length > 0 && selectedTab === 'forecast') {
      fetchForecasts(data, selectedModel, forecastHorizon);
    }
  }, [selectedModel, forecastHorizon, selectedTab, data]);
  
  // Filter data based on selected time range
  const getFilteredData = () => {
    if (!data.length) return [];
    
    const now = data[data.length - 1].timestamp;
    let cutoff;
    
    switch (timeRange) {
      case 'day':
        cutoff = now - 24 * 60 * 60 * 1000;
        break;
      case 'week':
        cutoff = now - 7 * 24 * 60 * 60 * 1000;
        break;
      case 'month':
        cutoff = now - 30 * 24 * 60 * 60 * 1000;
        break;
      case 'year':
        cutoff = now - 365 * 24 * 60 * 60 * 1000;
        break;
      default:
        cutoff = now - 7 * 24 * 60 * 60 * 1000;
    }
    
    return data.filter(item => item.timestamp >= cutoff);
  };
  
  // Calculate hourly pattern data
  const getHourlyPatternData = () => {
    if (!data.length) return [];
    
    const hourlyData = _.chain(data)
      .groupBy('hour')
      .map((items, hour) => ({
        hour: parseInt(hour),
        averageLoad: _.meanBy(items, 'Load'),
        minLoad: _.minBy(items, 'Load').Load,
        maxLoad: _.maxBy(items, 'Load').Load
      }))
      .sortBy('hour')
      .value();
    
    return hourlyData;
  };
  
  // Calculate daily pattern data
  const getDailyPatternData = () => {
    if (!data.length) return [];
    
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    
    const dailyData = _.chain(data)
      .groupBy('dayOfWeek')
      .map((items, day) => ({
        day: dayNames[parseInt(day)],
        dayIndex: parseInt(day),
        averageLoad: _.meanBy(items, 'Load'),
        minLoad: _.minBy(items, 'Load').Load,
        maxLoad: _.maxBy(items, 'Load').Load
      }))
      .sortBy('dayIndex')
      .value();
    
    return dailyData;
  };
  
  // Calculate monthly pattern data
  const getMonthlyPatternData = () => {
    if (!data.length) return [];
    
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    const monthlyData = _.chain(data)
      .groupBy('month')
      .map((items, month) => ({
        month: monthNames[parseInt(month)],
        monthIndex: parseInt(month),
        averageLoad: _.meanBy(items, 'Load'),
        minLoad: _.minBy(items, 'Load').Load,
        maxLoad: _.maxBy(items, 'Load').Load
      }))
      .sortBy('monthIndex')
      .value();
    
    return monthlyData;
  };
  
  // Summary statistics
  const getSummaryStats = () => {
    if (!data.length) return { avg: 0, min: 0, max: 0, current: 0 };
    
    const filteredData = getFilteredData();
    return {
      avg: _.meanBy(filteredData, 'Load').toFixed(2),
      min: _.minBy(filteredData, 'Load').Load.toFixed(2),
      max: _.maxBy(filteredData, 'Load').Load.toFixed(2),
      current: filteredData[filteredData.length - 1].Load.toFixed(2)
    };
  };
  
  // Find the AnomaliesTab or the section that renders the anomaly chart
  // Look for the LineChart or ComposedChart component that displays anomalies

  // Find where the custom tooltip for anomalies is defined
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      // Find if there's an anomaly at this timestamp
      const point = payload[0].payload;
      const anomalyAtThisPoint = anomalies.find(a => a.timestamp === point.timestamp);
      
      return (
        <div className="bg-white p-2 border rounded shadow-md">
          <p className="font-medium">{new Date(point.timestamp).toLocaleString()}</p>
          <p>Load: {point.Load.toLocaleString()} MWh</p>
          {anomalyAtThisPoint && (
            <>
              <p className="text-red-600 font-medium">Anomaly Detected</p>
              <p>Expected: {anomalyAtThisPoint.rolling_mean?.toLocaleString() || 'N/A'} MWh</p>
              <p>Deviation: {anomalyAtThisPoint.pct_deviation}%</p>
              {anomalyAtThisPoint.reason && <p>Possible reason: {anomalyAtThisPoint.reason}</p>}
              <p>Severity: {anomalyAtThisPoint.severity}</p>
            </>
          )}
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-600">Loading data...</div>
      </div>
    );
  }
  
  const filteredData = getFilteredData();
  const stats = getSummaryStats();
  const hourlyPatternData = getHourlyPatternData();
  const dailyPatternData = getDailyPatternData();
  const monthlyPatternData = getMonthlyPatternData();
  
  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-2">Electricity Load Forecasting Dashboard</h1>
        <div className="flex space-x-2">
          <button 
            className={`px-3 py-1 rounded ${selectedTab === 'overview' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}`}
            onClick={() => setSelectedTab('overview')}
          >
            Overview
          </button>
          <button 
            className={`px-3 py-1 rounded ${selectedTab === 'patterns' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}`}
            onClick={() => setSelectedTab('patterns')}
          >
            Load Patterns
          </button>
          <button 
            className={`px-3 py-1 rounded ${selectedTab === 'forecast' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}`}
            onClick={() => setSelectedTab('forecast')}
          >
            Forecast
          </button>
          <button 
            className={`px-3 py-1 rounded ${selectedTab === 'anomalies' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}`}
            onClick={() => setSelectedTab('anomalies')}
          >
            Anomalies
          </button>
        </div>
      </div>
      
      {selectedTab === 'overview' && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-500">Current Load</div>
              <div className="text-2xl font-bold">{stats.current} MWh</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-500">Average Load</div>
              <div className="text-2xl font-bold">{stats.avg} MWh</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-500">Min Load</div>
              <div className="text-2xl font-bold">{stats.min} MWh</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-500">Max Load</div>
              <div className="text-2xl font-bold">{stats.max} MWh</div>
            </div>
          </div>
          
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <h2 className="text-lg font-semibold">Load Trend</h2>
              <div className="flex space-x-2">
                <button 
                  className={`px-2 py-1 text-sm rounded ${timeRange === 'day' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                  onClick={() => setTimeRange('day')}
                >
                  Day
                </button>
                <button 
                  className={`px-2 py-1 text-sm rounded ${timeRange === 'week' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                  onClick={() => setTimeRange('week')}
                >
                  Week
                </button>
                <button 
                  className={`px-2 py-1 text-sm rounded ${timeRange === 'month' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                  onClick={() => setTimeRange('month')}
                >
                  Month
                </button>
                <button 
                  className={`px-2 py-1 text-sm rounded ${timeRange === 'year' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                  onClick={() => setTimeRange('year')}
                >
                  Year
                </button>
              </div>
            </div>
            
            <div className="bg-white p-4 rounded-lg shadow h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={filteredData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(timestamp) => {
                      const date = new Date(timestamp);
                      if (timeRange === 'day') return `${date.getHours()}:00`;
                      if (timeRange === 'week') return `${date.getMonth()+1}/${date.getDate()}`;
                      if (timeRange === 'month') return `${date.getMonth()+1}/${date.getDate()}`;
                      return `${date.getMonth()+1}/${date.getFullYear().toString().slice(2)}`;
                    }}
                    interval={timeRange === 'day' ? 2 : timeRange === 'week' ? 24 : timeRange === 'month' ? 72 : 720}
                  />
                  <YAxis />
                  <Tooltip 
                    labelFormatter={(timestamp) => new Date(timestamp).toLocaleString()}
                    formatter={(value) => [`${value.toFixed(2)} MWh`, 'Load']}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="Load" stroke="#3182ce" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-lg shadow">
              <h2 className="text-lg font-semibold mb-2">Hourly Pattern</h2>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={hourlyPatternData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="hour" />
                    <YAxis />
                    <Tooltip formatter={(value) => [`${value.toFixed(2)} MWh`, 'Load']} />
                    <Legend />
                    <Line type="monotone" dataKey="averageLoad" stroke="#3182ce" name="Avg Load" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div className="bg-white p-4 rounded-lg shadow">
              <h2 className="text-lg font-semibold mb-2">Daily Pattern</h2>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyPatternData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis />
                    <Tooltip formatter={(value) => [`${value.toFixed(2)} MWh`, 'Load']} />
                    <Legend />
                    <Bar dataKey="averageLoad" fill="#3182ce" name="Avg Load" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {selectedTab === 'patterns' && (
        <div>
          <div className="grid grid-cols-1 gap-6">
            <div className="bg-white p-4 rounded-lg shadow">
              <h2 className="text-lg font-semibold mb-2">Hourly Load Pattern</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={hourlyPatternData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="hour" label={{ value: 'Hour of Day', position: 'insideBottom', offset: -5 }} />
                    <YAxis label={{ value: 'Load (MWh)', angle: -90, position: 'insideLeft' }} />
                    <Tooltip formatter={(value) => [`${value.toFixed(2)} MWh`, 'Load']} />
                    <Legend />
                    <Area type="monotone" dataKey="minLoad" fill="#e3f2fd" stroke="#90caf9" name="Min Load" />
                    <Area type="monotone" dataKey="maxLoad" fill="#bbdefb" stroke="#42a5f5" name="Max Load" />
                    <Line type="monotone" dataKey="averageLoad" stroke="#1e88e5" name="Avg Load" strokeWidth={2} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                The chart shows clear daily patterns with lowest consumption during early morning hours (2-5 AM) 
                and peaks during business hours. Evening consumption remains high until around 9 PM.
              </p>
            </div>
            
            <div className="bg-white p-4 rounded-lg shadow">
              <h2 className="text-lg font-semibold mb-2">Daily Load Pattern</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={dailyPatternData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis />
                    <Tooltip formatter={(value) => [`${value.toFixed(2)} MWh`, 'Load']} />
                    <Legend />
                    <Bar dataKey="minLoad" fill="#e3f2fd" name="Min Load" />
                    <Bar dataKey="maxLoad" fill="#bbdefb" name="Max Load" />
                    <Line type="monotone" dataKey="averageLoad" stroke="#1e88e5" name="Avg Load" strokeWidth={2} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                Weekend days (Saturday and Sunday) show significantly lower consumption compared to weekdays.
                Weekday consumption is relatively consistent with slight variations.
              </p>
            </div>
            
            <div className="bg-white p-4 rounded-lg shadow">
              <h2 className="text-lg font-semibold mb-2">Monthly Load Pattern</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={monthlyPatternData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip formatter={(value) => [`${value.toFixed(2)} MWh`, 'Load']} />
                    <Legend />
                    <Area type="monotone" dataKey="minLoad" fill="#e3f2fd" stroke="#90caf9" name="Min Load" stackId="1" />
                    <Area type="monotone" dataKey="maxLoad" fill="#bbdefb" stroke="#42a5f5" name="Max Load" stackId="1" />
                    <Line type="monotone" dataKey="averageLoad" stroke="#1e88e5" name="Avg Load" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                Seasonal patterns are evident with higher consumption in winter months (December-February) 
                and lower consumption in summer months (May-August).
              </p>
            </div>
          </div>
        </div>
      )}
      
      {selectedTab === 'forecast' && (
        <div>
          <div className="bg-white p-4 rounded-lg shadow mb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Load Forecast</h2>
              <div className="flex items-center space-x-4">
                <div>
                  <label className="text-sm text-gray-600 mr-2">Model:</label>
                  <select 
                    className="border border-gray-300 rounded px-2 py-1 text-sm"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                  >
                    <option value="gradient_boosting">Gradient Boosting</option>
                    <option value="xgboost">XGBoost</option>
                    <option value="random_forest">Random Forest</option>
                    <option value="linear_regression">Linear Regression</option>
                    <option value="svr">SVR</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-gray-600 mr-2">Horizon:</label>
                  <select 
                    className="border border-gray-300 rounded px-2 py-1 text-sm"
                    value={forecastHorizon}
                    onChange={(e) => setForecastHorizon(parseInt(e.target.value))}
                  >
                    <option value="12">12 Hours</option>
                    <option value="24">24 Hours</option>
                    <option value="48">48 Hours</option>
                    <option value="72">72 Hours</option>
                  </select>
                </div>
                <button 
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded"
                  onClick={() => fetchForecasts(data, selectedModel, forecastHorizon)}
                  disabled={loadingForecast}
                >
                  {loadingForecast ? 'Loading...' : 'Refresh Forecast'}
                </button>
              </div>
            </div>
            
            {forecastError && (
              <div className="p-3 mb-4 rounded bg-yellow-50 text-yellow-800">
                <p className="text-sm">{forecastError}</p>
                <p className="text-xs mt-1">Showing mock forecast data as fallback. The API may be experiencing issues.</p>
              </div>
            )}
            
            {loadingForecast ? (
              <div className="flex items-center justify-center h-72">
                <div className="text-lg text-gray-600">Loading forecast data...</div>
              </div>
            ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={forecastData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(timestamp) => {
                      const date = new Date(timestamp);
                      // For longer horizons, show date and hour
                      if (forecastHorizon > 24) {
                        return `${date.getDate()}/${date.getMonth()+1} ${date.getHours()}:00`;
                      }
                      // For shorter horizons, just show hours
                      return `${date.getHours()}:00`;
                    }}
                    interval={forecastHorizon > 48 ? 8 : forecastHorizon > 24 ? 4 : 2}
                  />
                  <YAxis />
                  <Tooltip 
                    labelFormatter={(timestamp) => new Date(timestamp).toLocaleString()}
                    formatter={(value, name) => [
                      `${value.toFixed(2)} MWh`, 
                      name === 'Load' ? 'Actual/Forecast' : name
                    ]}
                  />
                  <Legend />
                  <Area 
                    dataKey="UpperBound" 
                    stroke="none" 
                    fill="#90caf9" 
                    name="Upper Bound"
                    fillOpacity={0.3}
                  />
                  <Area 
                    dataKey="LowerBound" 
                    stroke="none" 
                    fill="#90caf9" 
                    name="Lower Bound"
                    fillOpacity={0.3}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="Load" 
                    stroke={(data) => data && data.isForecast ? "#f44336" : "#2196f3"}
                    strokeWidth={2}
                    dot={{ strokeWidth: 2, r: 4 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            )}
            <div className="flex items-center mt-4">
              <div className="w-4 h-4 bg-blue-500 rounded-full mr-2"></div>
              <span className="mr-4 text-sm">Historical Data</span>
              <div className="w-4 h-4 bg-red-500 rounded-full mr-2"></div>
              <span className="mr-4 text-sm">Forecast</span>
              <div className="w-4 h-4 bg-blue-200 rounded-full mr-2"></div>
              <span className="text-sm">Confidence Interval</span>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              {forecastError ? 
                'Using simplified forecast model due to API errors.' :
                `Forecast generated using ${
                  selectedModel === 'gradient_boosting' ? 'Gradient Boosting' :
                  selectedModel === 'xgboost' ? 'XGBoost' :
                  selectedModel === 'random_forest' ? 'Random Forest' :
                  selectedModel === 'linear_regression' ? 'Linear Regression' : 'SVR'
                } model for the next ${forecastHorizon} hours.`
              }
            </p>
          </div>
          
          <div className="bg-white p-4 rounded-lg shadow">
            <h2 className="text-lg font-semibold mb-2">Forecast Details</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full bg-white">
                <thead>
                  <tr>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Time
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Forecast (MWh)
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Lower Bound
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Upper Bound
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {forecastData
                    .filter(item => item.isForecast)
                    .map((item, index) => (
                    <tr key={index} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm">
                        {new Date(item.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                          {' '}
                          {new Date(item.timestamp).toLocaleDateString([], {month: 'short', day: 'numeric'})}
                      </td>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm font-semibold">
                        {item.Load.toFixed(2)}
                      </td>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm text-gray-600">
                        {item.LowerBound.toFixed(2)}
                      </td>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm text-gray-600">
                        {item.UpperBound.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      
      {selectedTab === 'anomalies' && (
        <div>
          <div className="bg-white p-4 rounded-lg shadow mb-6">
            <div className="flex justify-between items-center mb-2">
              <h2 className="text-lg font-semibold">Detected Anomalies</h2>
              <div className="flex items-center space-x-4">
                <div className="flex items-center">
                  <span className="text-sm text-gray-600 mr-2">Threshold:</span>
                  <input 
                    type="range" 
                    min="1.0" 
                    max="3.0" 
                    step="0.1" 
                    value={anomalyThreshold}
                    onChange={(e) => setAnomalyThreshold(parseFloat(e.target.value))}
                    className="w-32"
                  />
                  <span className="text-sm ml-2">{anomalyThreshold.toFixed(1)}</span>
                </div>
                <button 
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded"
                  onClick={() => fetchAnomalies(data, anomalyThreshold)}
                  disabled={loadingAnomalies}
                >
                  {loadingAnomalies ? 'Analyzing...' : 'Refresh Analysis'}
                </button>
              </div>
            </div>
            
            {anomalyMessage && (
              <div className={`p-3 mb-4 rounded ${anomalyMessage.includes('No significant') ? 'bg-blue-50 text-blue-800' : 'bg-yellow-50 text-yellow-800'}`}>
                <p className="text-sm">{anomalyMessage}</p>
                {anomalyStats && (
                  <div className="mt-2 grid grid-cols-4 gap-2 text-xs">
                    <div className="border rounded p-2">
                      <span className="font-semibold">Mean Deviation:</span> {anomalyStats.mean_deviation_pct.toFixed(2)}%
                    </div>
                    <div className="border rounded p-2">
                      <span className="font-semibold">Max Deviation:</span> {anomalyStats.max_deviation_pct.toFixed(2)}%
                    </div>
                    <div className="border rounded p-2">
                      <span className="font-semibold">Data Points:</span> {anomalyStats.data_points.toLocaleString()}
                    </div>
                    <div className="border rounded p-2">
                      <span className="font-semibold">Threshold:</span> {anomalyStats.threshold_tried}
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {loadingAnomalies ? (
              <div className="flex items-center justify-center h-72">
                <div className="text-lg text-gray-600">Detecting anomalies...</div>
              </div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart 
                    data={data.slice(-5000)} 
                    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="timestamp" 
                      tickFormatter={(timestamp) => {
                        const date = new Date(timestamp);
                        return `${(date.getMonth()+1)}/${date.getDate()}`;
                      }}
                      interval={240}
                    />
                    <YAxis />
                    <Tooltip 
                      content={({ active, payload, label }) => {
                        if (active && payload && payload.length) {
                          const point = payload[0].payload;
                          const anomalyAtThisPoint = anomalies.find(a => a.timestamp === point.timestamp);
                          
                          return (
                            <div className="bg-white p-2 border rounded shadow-md">
                              <p className="font-medium">{new Date(point.timestamp).toLocaleString()}</p>
                              <p>Load: {point.Load.toLocaleString()} MWh</p>
                              {anomalyAtThisPoint && (
                                <>
                                  <p className="text-red-600 font-medium">Anomaly Detected</p>
                                  <p>Expected: {anomalyAtThisPoint.rolling_mean?.toLocaleString() || 'N/A'} MWh</p>
                                  <p>Deviation: {anomalyAtThisPoint.pct_deviation}%</p>
                                  {anomalyAtThisPoint.reason && <p>Possible reason: {anomalyAtThisPoint.reason}</p>}
                                  <p>Severity: {anomalyAtThisPoint.severity}</p>
                                </>
                              )}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="Load" 
                      stroke="#3182ce" 
                      dot={false} 
                    />
                    
                    {/* Group all anomalies into a single scatter chart to avoid duplicate legend items */}
                    <Scatter
                      name="Anomalies"
                      data={anomalies}
                      fill="#ff0000"
                      line={false}
                    >
                      {anomalies.map((anomaly, index) => (
                        <Cell
                          key={`anomaly-${index}`}
                          fill="white"
                          stroke={
                            anomaly.severity === 'High' ? '#ff0000' : 
                            anomaly.severity === 'Medium' ? '#ff9800' : 
                            anomaly.severity === 'Low' ? '#2196f3' : 
                            anomaly.severity === 'Very Low' ? '#4caf50' : '#9e9e9e'
                          }
                          strokeWidth={2}
                          r={
                            anomaly.severity === 'High' ? 6 : 
                            anomaly.severity === 'Medium' ? 5 : 
                            anomaly.severity === 'Low' ? 4 : 3
                          }
                        />
                      ))}
                    </Scatter>
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
            <p className="text-sm text-gray-600 mt-2">
              {anomalies.length > 0 ? (
                <>
                  Colored dots indicate detected anomalies in the electricity load pattern. 
                  {anomalies.some(a => a.severity === 'Very Low' || a.severity === 'Minimal') && 
                    " Smaller dots represent minor deviations that may not be true anomalies."}
                </>
              ) : (
                !loadingAnomalies && "No anomalies detected in the current data. Try refreshing the analysis or selecting a different time period."
              )}
            </p>
          </div>
          
          {anomalies.length > 0 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                {/* Anomalies by Hour of Day */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h2 className="text-lg font-semibold mb-2">Anomalies by Hour of Day</h2>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart 
                        data={
                          Array.from({length: 24}, (_, hour) => ({
                            hour,
                            count: anomalies.filter(a => new Date(a.timestamp).getHours() === hour).length
                          }))
                        }
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="hour" label={{ value: 'Hour of Day', position: 'insideBottom', offset: -5 }} />
                        <YAxis label={{ value: 'Number of Anomalies', angle: -90, position: 'insideLeft' }} />
                        <Tooltip formatter={(value) => [`${value}`, 'Anomalies']} />
                        <Bar dataKey="count" fill="#f44336" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    Distribution of anomalies across different hours of the day reveals patterns of when unusual load typically occurs.
                  </p>
                </div>

                {/* Anomalies by Day of Week */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h2 className="text-lg font-semibold mb-2">Anomalies by Day of Week</h2>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart 
                        data={
                          [
                            'Sunday', 'Monday', 'Tuesday', 'Wednesday', 
                            'Thursday', 'Friday', 'Saturday'
                          ].map((day, index) => ({
                            day,
                            count: anomalies.filter(a => new Date(a.timestamp).getDay() === index).length
                          }))
                        }
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="day" />
                        <YAxis />
                        <Tooltip formatter={(value) => [`${value}`, 'Anomalies']} />
                        <Bar dataKey="count" fill="#f44336" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    Analysis of which days of the week show more anomalies helps identify potential weekly patterns of unusual consumption.
                  </p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                {/* Anomalies by Severity */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h2 className="text-lg font-semibold mb-2">Anomalies by Severity</h2>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={
                            ['High', 'Medium', 'Low', 'Very Low', 'Minimal'].map(severity => ({
                              name: severity,
                              value: anomalies.filter(a => a.severity === severity).length || 0
                            })).filter(item => item.value > 0)
                          }
                          cx="50%"
                          cy="50%"
                          labelLine={true}
                          label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {
                            ['High', 'Medium', 'Low', 'Very Low', 'Minimal'].map((severity, index) => (
                              <Cell key={`cell-${index}`} fill={
                                severity === 'High' ? '#f44336' : 
                                severity === 'Medium' ? '#ff9800' : 
                                severity === 'Low' ? '#2196f3' : 
                                severity === 'Very Low' ? '#4caf50' :
                                '#9e9e9e'
                              } />
                            ))
                          }
                        </Pie>
                        <Tooltip formatter={(value, name) => [`${value} (${((value / anomalies.length) * 100).toFixed(1)}%)`, name]} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    Distribution of anomalies by severity helps prioritize which unusual patterns require immediate attention.
                  </p>
                </div>

                {/* Anomalies by Reason */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h2 className="text-lg font-semibold mb-2">Anomalies by Reason</h2>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={
                          Array.from(
                            anomalies.reduce((acc, anomaly) => {
                              acc.set(anomaly.reason, (acc.get(anomaly.reason) || 0) + 1);
                              return acc;
                            }, new Map())
                          ).map(([reason, count]) => ({ reason, count }))
                        }
                        layout="vertical"
                        margin={{ left: 150 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis type="number" />
                        <YAxis 
                          dataKey="reason" 
                          type="category" 
                          width={150}
                          tick={{ fontSize: 12 }}
                        />
                        <Tooltip formatter={(value) => [`${value}`, 'Count']} />
                        <Bar dataKey="count" fill="#2196f3" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    Understanding the most common reasons for anomalies helps identify patterns and root causes.
                  </p>
                </div>
              </div>
              
              <div className="bg-white p-4 rounded-lg shadow mb-6">
                <h2 className="text-lg font-semibold mb-4">Anomaly Patterns & Insights</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div className="border rounded p-3 bg-gray-50">
                    <h3 className="font-semibold text-sm mb-1">Time Concentration</h3>
                    <p className="text-sm text-gray-600">
                      {(() => {
                        // Calculate when most anomalies occur
                        const hourCounts = Array.from({length: 24}, (_, hour) => 
                          anomalies.filter(a => new Date(a.timestamp).getHours() === hour).length
                        );
                        const maxHour = hourCounts.indexOf(Math.max(...hourCounts));
                        const isDaytime = maxHour >= 8 && maxHour <= 18;
                        
                        return `Most anomalies occur around ${maxHour}:00 ${
                          isDaytime ? "(during business hours)" : "(outside business hours)"
                        }, which suggests ${
                          isDaytime ? 
                          "business activity may be causing unexpected load patterns." : 
                          "unusual activity during off-hours may be worth investigating."
                        }`;
                      })()}
                    </p>
                  </div>
                  
                  <div className="border rounded p-3 bg-gray-50">
                    <h3 className="font-semibold text-sm mb-1">Day of Week Pattern</h3>
                    <p className="text-sm text-gray-600">
                      {(() => {
                        // Calculate which day has most anomalies
                        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                        const dayCounts = days.map((_, index) => 
                          anomalies.filter(a => new Date(a.timestamp).getDay() === index).length
                        );
                        const maxDay = dayCounts.indexOf(Math.max(...dayCounts));
                        const isWeekend = maxDay === 0 || maxDay === 6;
                        
                        return `${days[maxDay]} shows the highest anomaly frequency (${Math.max(...dayCounts)} occurrences), ${
                          isWeekend ? 
                          "which is unusual since weekend patterns typically differ from weekdays." : 
                          "suggesting potential issues during regular work week activities."
                        }`;
                      })()}
                    </p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border rounded p-3 bg-gray-50">
                    <h3 className="font-semibold text-sm mb-1">Severity Distribution</h3>
                    <p className="text-sm text-gray-600">
                      {(() => {
                        // Calculate severity distribution
                        const severityCounts = {
                          High: anomalies.filter(a => a.severity === 'High').length,
                          Medium: anomalies.filter(a => a.severity === 'Medium').length,
                          Low: anomalies.filter(a => a.severity === 'Low').length
                        };
                        const total = severityCounts.High + severityCounts.Medium + severityCounts.Low;
                        const highPct = ((severityCounts.High / total) * 100).toFixed(1);
                        
                        return `${highPct}% of detected anomalies are high severity, ${
                          parseFloat(highPct) > 20 ?
                          "indicating significant deviations that should be investigated promptly." :
                          "suggesting most unusual patterns are moderate deviations from expected load."
                        }`;
                      })()}
                    </p>
                  </div>
                  
                  <div className="border rounded p-3 bg-gray-50">
                    <h3 className="font-semibold text-sm mb-1">Common Reason</h3>
                    <p className="text-sm text-gray-600">
                      {(() => {
                        // Calculate most common reason
                        const reasonCounts = {};
                        anomalies.forEach(a => {
                          reasonCounts[a.reason] = (reasonCounts[a.reason] || 0) + 1;
                        });
                        const mostCommonReason = Object.entries(reasonCounts)
                          .sort((a, b) => b[1] - a[1])[0];
                        
                        return `"${mostCommonReason[0]}" is the most common reason (${mostCommonReason[1]} instances), ${
                          mostCommonReason[0].includes("working hours") ?
                          "suggesting business hour activities need monitoring." :
                          mostCommonReason[0].includes("night") ?
                          "indicating unusual night-time electricity consumption patterns." :
                          "which may require specific attention for load management."
                        }`;
                      })()}
                    </p>
                  </div>
                </div>
          </div>
          
          <div className="bg-white p-4 rounded-lg shadow">
            <h2 className="text-lg font-semibold mb-2">Anomaly Details</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full bg-white">
                <thead>
                  <tr>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Date & Time
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Load (MWh)
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Deviation (%)
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Severity
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Possible Reason
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {anomalies.map((anomaly, index) => {
                    // Calculate percent deviation from expected (if available)
                    // Use the pct_deviation field if available, otherwise calculate it
                    const deviation = anomaly.pct_deviation || 
                                      (anomaly.rolling_mean ? 
                                      ((anomaly.Load - anomaly.rolling_mean) / anomaly.rolling_mean * 100).toFixed(2) : 
                                      'N/A');
                    const isPositive = parseFloat(deviation) > 0;
                    
                    return (
                      <tr key={index} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="py-2 px-4 border-b border-gray-200 text-sm">
                          {new Date(anomaly.timestamp).toLocaleString()}
                        </td>
                        <td className="py-2 px-4 border-b border-gray-200 text-sm font-semibold">
                          {typeof anomaly.Load === 'number' ? anomaly.Load.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'N/A'}
                        </td>
                        <td className={`py-2 px-4 border-b border-gray-200 text-sm font-semibold ${
                          isPositive ? 'text-red-600' : 'text-blue-600'
                        }`}>
                          {deviation !== 'N/A' ? `${isPositive ? '+' : ''}${deviation}%` : 'N/A'}
                        </td>
                        <td className="py-2 px-4 border-b border-gray-200 text-sm">
                          <span className={`px-2 py-1 rounded text-xs text-white ${
                            anomaly.severity === 'High' ? 'bg-red-500' : 
                            anomaly.severity === 'Medium' ? 'bg-yellow-500' : 
                            anomaly.severity === 'Low' ? 'bg-blue-500' :
                            anomaly.severity === 'Very Low' ? 'bg-green-500' :
                            'bg-gray-500'
                          }`}>
                            {anomaly.severity}
                          </span>
                        </td>
                        <td className="py-2 px-4 border-b border-gray-200 text-sm">
                          {anomaly.reason}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default ElectricityLoadDashboard;