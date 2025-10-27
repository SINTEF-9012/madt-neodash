import React, { useState } from 'react';
import axios from 'axios'; // HTTP client
import { ChartProps } from '../Chart';

  const NEO4J_ENDPOINT_5001 = 'https://madt4bc.dynabic.dev/neo4j-api';
  const MINIO_ENPOINT_5000 = 'https://madt4bc.dynabic.dev/minio-api';
  const INFLUXDB_ENDPOINT_4999 = 'https://madt4bc.dynabic.dev/influxdb-api';

  // const NEO4J_ENDPOINT_5001 = "http://localhost:5001";
  // const MINIO_ENPOINT_5000 = "http://localhost:5000";
  // const INFLUXDB_ENDPOINT_4999 = "http://localhost:4999";

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
      criticality: string; // Criticality of asset
      events: number;  // The number of events associated with the asset.
    }>;
  }

  // Local state to store the report data, loading status, and errors.
  const [reportData, setReportData] = useState<EventReport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Determines the background color based on the number of events and criticality level.
  const getColorForCount = (count: number, criticality: string): string => {
    if (criticality === 'high') {
      // Any number of events is red if critical
      return 'red';
    } else if (criticality === 'low') {
      // Always return yellow for low criticality, regardless of count
      return 'yellow';
    } else if (criticality === 'medium') {
      // Use the original color logic for medium criticality
      if (count === 1) {
        return 'yellow';
      } else if (count === 2) {
        return 'orange';
      } else if (count >= 3) {
        return 'red';
      }
    } else {
      // Fallback/default
      return 'lightgrey';
    }
  };

  // Fetch data from the Flask API endpoint and update state.
  const generateReport = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      // Adjust the endpoint URL to point to the correct host and port.
      const response = await axios.get<EventReport>(NEO4J_ENDPOINT_5001+'/neo4j_events');
      setReportData(response.data);
      // console.log(response.data)
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
                  backgroundColor: getColorForCount(asset.events, asset.criticality),
                  padding: '0.5rem',
                  marginBottom: '0.5rem',
                  borderRadius: '4px'
                }}
              >
                <strong>Asset:</strong> {asset.name} &nbsp;|&nbsp;
                <strong>Criticality:</strong> {asset.criticality} &nbsp;|&nbsp;
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
