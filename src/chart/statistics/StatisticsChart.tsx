import React, { useState } from 'react';
import axios from 'axios';
import { ChartProps } from '../Chart';

const StatisticsTable = ({ data }) => {
  if (!data) {
    return <p style={{ fontSize: '16px', marginTop: '20px' }}>No data available.</p>;
  }

  const keys = Object.keys(data);
  const stats = keys.length > 0 ? Object.keys(data[keys[0]]) : [];

  return (
    <table style={{
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: '16px',
      marginTop: '20px'
    }}>
      <thead>
        <tr style={{ backgroundColor: '#f2f2f2' }}>
          <th style={{ border: '1px solid #ccc', padding: '10px' }}>Statistic</th>
          {stats.map(stat => (
            <th key={stat} style={{ border: '1px solid #ccc', padding: '10px' }}>{stat}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {keys.map((key, index) => (
          <tr key={key} style={{ backgroundColor: index % 2 === 0 ? '#fff' : '#f9f9f9' }}>
            <td style={{ border: '1px solid #ccc', padding: '10px', fontWeight: 'bold' }}>{key}</td>
            {stats.map(stat => (
              <td key={`${key}-${stat}`} style={{ border: '1px solid #ccc', padding: '10px' }}>
                {data[key][stat]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
};

const StatisticsChart = (props: ChartProps) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statistics, setStatistics] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    setStatistics(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert("Please select a PCAP file before computing statistics.");
      return;
    }

    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await axios.post('http://localhost:5003/get_statistics', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.status === 200) {
        setStatistics(response.data);
      } else {
        alert("Failed to compute statistics.");
      }
    } catch (error) {
      console.error('[StatisticsChart.tsx] Error uploading file:', error);
      alert("An error occurred while computing statistics.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      marginTop: '20px',
      padding: '20px',
      fontFamily: 'Arial, sans-serif',
      textAlign: 'center',
      backgroundColor: '#f7f9fb',
      borderRadius: '10px',
      boxShadow: '0 2px 6px rgba(0,0,0,0.1)'
    }}>
      <h2 style={{ fontSize: '24px', marginBottom: '10px' }}>PCAP Statistics</h2>

      <input
        type="file"
        accept=".pcap,.pcapng"
        onChange={handleFileChange}
        style={{
          marginBottom: '10px',
          fontSize: '16px',
          padding: '6px',
          borderRadius: '5px',
          border: '1px solid #ccc'
        }}
      />
      <br />

      <button
        onClick={handleUpload}
        disabled={loading}
        style={{
          fontSize: '16px',
          padding: '10px 20px',
          borderRadius: '6px',
          border: 'none',
          backgroundColor: loading ? '#aaa' : '#007bff',
          color: 'white',
          cursor: loading ? 'not-allowed' : 'pointer',
          transition: 'background-color 0.3s ease'
        }}
      >
        {loading ? 'Computing...' : 'Compute Statistics'}
      </button>

      <div style={{ marginTop: '30px', overflowX: 'auto' }}>
        <StatisticsTable data={statistics} />
      </div>
    </div>
  );
};

export default StatisticsChart;
