import React, { useState } from 'react';
import axios from 'axios'; // HTTP client
import { ChartProps } from '../Chart';

/**
 * Renders a generated event report with conditional color coding.
 */
const EventChart = (props: ChartProps) => {
  const { records, settings, getGlobalParameter } = props;
  const type = settings && settings.format ? settings.format : 'json';

  // Define the expected structure of the event report.
  interface EventReport {
    total: number;
    assets: Array<{
      name: string;    // The asset identifier/name.
      events: number;  // The number of events associated with the asset.
    }>;
  }

  // Local state to store the report data, loading status, and errors.
  const [reportData, setReportData] = useState<EventReport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Determines the background color based on the number of events.
  const getColorForCount = (count: number): string => {
    if (count === 1) {
      return 'yellow';
    } else if (count === 2) {
      return 'orange';
    } else if (count >= 3) {
      return 'red';
    }
    return 'lightgrey';
  };

  // Fetch data from the Flask API endpoint and update state.
  const generateReport = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      // Adjust the endpoint URL to point to the correct host and port.
      const response = await axios.get<EventReport>('http://localhost:5001/neo4j_events');
      setReportData(response.data);
    } catch (err) {
      console.error('Error fetching event report:', err);
      setError('Failed to fetch data. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '1rem', textAlign: 'center' }}>
      <button
        onClick={generateReport}
        style={{
          fontSize: '1.2rem',
          padding: '12px 24px',
          borderRadius: '8px',
          cursor: 'pointer'
        }}
      >
        Generate Report
      </button>
      {loading && <p>Loading data…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {reportData && (
        <div style={{ marginTop: '1rem', textAlign: 'left' }}>
          <h2>Total Events: {reportData.total}</h2>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {reportData.assets.map((asset, index) => (
              <li
                key={index}
                style={{
                  backgroundColor: getColorForCount(asset.events),
                  padding: '0.5rem',
                  marginBottom: '0.5rem',
                  borderRadius: '4px'
                }}
              >
                <strong>Asset:</strong> {asset.name} &nbsp;|&nbsp;
                <strong>Events:</strong> {asset.events}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default EventChart;
