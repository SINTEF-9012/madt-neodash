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
    <div
      style={{
        marginTop: '20px',
        padding: '20px',
        fontFamily: 'Arial, sans-serif',
        maxWidth: '600px',
        margin: 'auto',
        borderRadius: '8px',
        boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)',
        backgroundColor: '#f9f9f9',
        textAlign: 'center',
      }}
    >
      <h4 style={{ fontSize: '22px', fontWeight: 'bold', color: '#333', marginBottom: '20px' }}>
        Select timeframe:
      </h4>
  
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '15px',
        }}
      >
        <label
          style={{
            fontSize: '16px',
            fontWeight: 'bold',
            color: '#555',
            marginRight: '10px',
          }}
        >
          Start:
        </label>
        <input
          type="datetime-local"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          style={{
            fontSize: '14px',
            padding: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
            width: '70%',
          }}
        />
      </div>
  
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
        }}
      >
        <label
          style={{
            fontSize: '16px',
            fontWeight: 'bold',
            color: '#555',
            marginRight: '10px',
          }}
        >
          End:
        </label>
        <input
          type="datetime-local"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          style={{
            fontSize: '14px',
            padding: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
            width: '70%',
          }}
        />
      </div>
  
      <button
        style={{
          padding: '12px 30px',
          fontSize: '18px',
          fontWeight: 'bold',
          color: '#fff',
          backgroundColor: '#007BFF',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          transition: 'background-color 0.3s',
          marginTop: '10px',
        }}
        onClick={downloadData}
        onMouseOver={(e) => (e.currentTarget.style.backgroundColor = '#0056b3')}
        onMouseOut={(e) => (e.currentTarget.style.backgroundColor = '#007BFF')}
      >
        Download
      </button>
    </div>
  );
  
};

export default RealtimeDataChart;
