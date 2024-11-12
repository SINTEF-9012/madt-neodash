import React, { useState, useEffect } from 'react';
import { ChartProps } from '../Chart';
import { generateCypher } from '../../openai/TextToCypher';
import ReactJson from 'react-json-view'
import { MqttList } from './component/MqttList';
import { RestGet } from './component/RestGet';
import axios from 'axios';

/**
 * Renders Neo4j records as their JSON representation.
 */
const DataSourceChart = (props: ChartProps) => {
  const { records, settings, getGlobalParameter } = props;
  const type = settings && settings.format ? settings.format : 'json';
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0] : {};
  const nodetype = node.properties['type'];
  const asset_id = node.properties['uid']; // This is bucket name
  const endpoint = node.properties['endpoint']; // This is the topic
  
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [timeInterval, setTimeInterval] = useState<number>(1);
  const [timeUnit, setTimeUnit] = useState<string>('seconds');
  const [isPopulating, setIsPopulating] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number | null>(null);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPopulating && countdown !== null && countdown > 0) {
      timer = setInterval(() => {
        setCountdown((prev) => (prev !== null ? prev - 1 : null));
      }, 1000);
    } else if (countdown === 0) {
      alert('Data collection has stopped.');
      setIsPopulating(false);
      setCountdown(null);
    }
    return () => clearInterval(timer);
  }, [isPopulating, countdown]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('asset_id', asset_id);

    try {
      const response = await axios.post('http://localhost:5000/minio_upload_file', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      console.log('[DataSource.tsx] File upload returned following status:', response.data);
    } catch (error) {
      console.error('[DataSource.tsx] Error uploading file:', error);
    }
  };

  const handleTimeIntervalChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setTimeInterval(Number(event.target.value));
  };

  const handleTimeUnitChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setTimeUnit(event.target.value);
  };

  const handleBeginPopulating = () => {
    alert(`Data collection started. Collecting data for ${timeInterval} ${timeUnit}.`);
    setIsPopulating(true);
    setCountdown(convertToSeconds(timeInterval, timeUnit));
  };

  const handleStopPopulating = () => {
    alert("Data collection stopped.");
    setIsPopulating(false);
    setCountdown(null);
  };

  const convertToSeconds = (interval: number, unit: string): number => {
    switch (unit) {
      case 'seconds':
        return interval;
      case 'minutes':
        return interval * 60;
      case 'hours':
        return interval * 3600;
      case 'days':
        return interval * 86400;
      default:
        return interval;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', height: '100%', textAlign: 'center', fontSize: '14px' }}>
      {/* Static Section */}
      <div style={{ padding: '10px', border: '1px solid #ccc', borderRadius: '5px' }}>
        <h3 style={{ margin: '5px 0' }}>Static</h3>
        <p style={{ margin: '5px 0' }}>Upload a file for static processing.</p>
        {nodetype !== 'rest' && nodetype !== 'mqtt' && (
          <div style={{ marginTop: '10px' }}>
            <input
              type="file"
              onChange={handleFileChange}
              style={{ padding: '5px', fontSize: '12px', cursor: 'pointer' }}
            />
            <button
              onClick={handleFileUpload}
              style={{ padding: '5px 10px', fontSize: '12px', cursor: 'pointer', marginTop: '5px' }}
              disabled={!selectedFile}
            >
              Upload
            </button>
          </div>
        )}
      </div>

      {/* Realtime Section */}
      <div style={{ padding: '10px', border: '1px solid #ccc', borderRadius: '5px' }}>
        <h3 style={{ margin: '5px 0' }}>Realtime</h3>
        <p style={{ margin: '5px 0' }}>Set a time interval for real-time data.</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginTop: '10px' }}>
          <input
            type="number"
            value={timeInterval}
            onChange={handleTimeIntervalChange}
            style={{ padding: '5px', fontSize: '12px', width: '50px' }}
            min="1"
          />
          <select
            value={timeUnit}
            onChange={handleTimeUnitChange}
            style={{ padding: '5px', fontSize: '12px' }}
          >
            <option value="seconds">Sec</option>
            <option value="minutes">Min</option>
            <option value="hours">Hr</option>
            <option value="days">Day</option>
          </select>
          {isPopulating ? (
            <>
              <button
                onClick={handleStopPopulating}
                style={{ padding: '5px 10px', fontSize: '12px', cursor: 'pointer' }}
              >
                Stop
              </button>
              <span style={{ fontSize: '12px', marginLeft: '10px' }}>
                Time remaining: {countdown} seconds
              </span>
            </>
          ) : (
            <button
              onClick={handleBeginPopulating}
              style={{ padding: '5px 10px', fontSize: '12px', cursor: 'pointer' }}
            >
              Start
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default DataSourceChart;
