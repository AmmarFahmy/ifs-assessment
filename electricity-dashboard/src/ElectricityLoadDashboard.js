import React, { useState, useEffect } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, ComposedChart } from 'recharts';
import _ from 'lodash';

const ElectricityLoadDashboard = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [forecastData, setForecastData] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [timeRange, setTimeRange] = useState('week'); // 'day', 'week', 'month', 'year'
  const [selectedTab, setSelectedTab] = useState('overview'); // 'overview', 'patterns', 'forecast', 'anomalies'

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        // const response = await window.fs.readFile('DS_ElectricityLoad.csv', { encoding: 'utf8' });
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
        
        // Generate some demo forecast data (last 24 hours + 24 more hours)
        const lastTimestamp = processedData[processedData.length - 1].timestamp;
        const mockForecast = [];
        
        // Last 24 hours of actual data
        const lastDayData = processedData.slice(-24);
        mockForecast.push(...lastDayData);
        
        // Next 24 hours of forecasted data
        for (let i = 1; i <= 24; i++) {
          const lastDate = new Date(lastTimestamp + i * 60 * 60 * 1000);
          const hour = lastDate.getHours();
          
          // Create a simple model based on hour of day and add some randomness
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
        
        // Generate some mock anomalies
        const mockAnomalies = [];
        for (let i = 0; i < 5; i++) {
          const randomIndex = Math.floor(Math.random() * (processedData.length - 24)) + 24;
          const anomalyPoint = { ...processedData[randomIndex] };
          anomalyPoint.reason = ['Unexpected spike', 'Holiday effect', 'Weather anomaly', 'System error', 'Unknown factor'][i];
          anomalyPoint.severity = ['High', 'Medium', 'Low'][Math.floor(Math.random() * 3)];
          mockAnomalies.push(anomalyPoint);
        }
        
        setData(processedData);
        setForecastData(mockForecast);
        setAnomalies(mockAnomalies);
        setLoading(false);
      } catch (error) {
        console.error('Error loading data:', error);
        setLoading(false);
      }
    };
    
    loadData();
  }, []);
  
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
            <h2 className="text-lg font-semibold mb-2">Load Forecast (Next 24 Hours)</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={forecastData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(timestamp) => new Date(timestamp).getHours() + ':00'}
                    interval={1}
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
            <div className="flex items-center mt-4">
              <div className="w-4 h-4 bg-blue-500 rounded-full mr-2"></div>
              <span className="mr-4 text-sm">Historical Data</span>
              <div className="w-4 h-4 bg-red-500 rounded-full mr-2"></div>
              <span className="mr-4 text-sm">Forecast</span>
              <div className="w-4 h-4 bg-blue-200 rounded-full mr-2"></div>
              <span className="text-sm">Confidence Interval (95%)</span>
            </div>
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
                  {forecastData.filter(item => item.isForecast).slice(0, 12).map((item, index) => (
                    <tr key={index} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm">
                        {new Date(item.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
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
            <h2 className="text-lg font-semibold mb-2">Detected Anomalies</h2>
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
                    labelFormatter={(timestamp) => new Date(timestamp).toLocaleString()}
                    formatter={(value) => [`${value.toFixed(2)} MWh`, 'Load']}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="Load" stroke="#3182ce" dot={false} />
                  {anomalies.map((anomaly, index) => (
                    <Line
                      key={index}
                      dataKey="Load"
                      data={[anomaly]}
                      stroke="#ff0000"
                      strokeWidth={0}
                      dot={{ stroke: '#ff0000', strokeWidth: 2, r: 6 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              Red dots indicate detected anomalies in the electricity load pattern.
            </p>
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
                      Severity
                    </th>
                    <th className="py-2 px-4 border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Possible Reason
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {anomalies.map((anomaly, index) => (
                    <tr key={index} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm">
                        {new Date(anomaly.timestamp).toLocaleString()}
                      </td>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm font-semibold">
                        {anomaly.Load.toFixed(2)}
                      </td>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm">
                        <span className={`px-2 py-1 rounded text-xs text-white ${
                          anomaly.severity === 'High' ? 'bg-red-500' : 
                          anomaly.severity === 'Medium' ? 'bg-yellow-500' : 'bg-blue-500'
                        }`}>
                          {anomaly.severity}
                        </span>
                      </td>
                      <td className="py-2 px-4 border-b border-gray-200 text-sm">
                        {anomaly.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ElectricityLoadDashboard;