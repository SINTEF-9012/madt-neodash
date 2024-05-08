import React, { useEffect, useState } from 'react';
import { ChartProps } from '../Chart';
import axios from 'axios';

const RealtimeDataChart = (props: ChartProps) => {
  const { records } = props;
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0] : {};
  const endpoint = node.properties["endpoint"]; // Obs! Used as bucket name
  // Hold state for date selection
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Function to retrieve data within time frame, activated by clicking "Donwload"
  const downloadData = async () => {
    try {
      const response = await axios.get('http://localhost:4999/influxdb_download_data', {
        params: {
          endpoint: endpoint,
          start: startDate,
          end: endDate
        } 
      });
      console.log('[RealtimeDataChart.tsx] Fetched user-defined data.');
      console.log(response.data); // For now, just log the response
    } catch (error) {
      console.error('[RealtimeDataChart.tsx] Error fetching data:', error);
    }
  };
 
  return (
    <div style={{ marginTop: '0px', height: '100%', textAlign: 'center' }}>
      <div style={{ marginTop: '20px' }}>
        <h4>Select timeframe for data selection:</h4>
        <div>
          <label>Start: </label>
          <input
            type="datetime-local"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>
        <div>
          <label>End: </label>
          <input
            type="datetime-local"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
      </div>

      <button 
        style={{ 
          padding: '15px 25px', 
          fontSize: '20px', 
          cursor: 'pointer',
          marginTop: '20px'
        }} 
        onClick={downloadData}
      >
        Download
      </button>
    </div>
  );
};

export default RealtimeDataChart;
