import React, { useEffect, useState } from 'react';
import { ChartProps } from '../Chart';
import { generateCypher } from '../../openai/TextToCypher';
import axios from 'axios'; // HTTP client

/**
 * Renders Neo4j records as their JSON representation.
 */

const AnalyticsChart = (props: ChartProps) => {
  //const { generated, setGenerated } = useState(0);
  const { records, settings, getGlobalParameter } = props;
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0] : {};
  const endpoint = node.properties['endpoint']; // Obs! Used as bucket name
  const node_name = node.properties['name'];
  const [inputText, setInputText] = useState('');
  const [resultText, setResultText] = useState('');

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(event.target.value);
  };

  // Once "Solve" button is clicked on by user, perform:
  const handleSubmit = async () => {
    try {
      // Store task in Neo4J:
      const updateTaskResponse = await axios.post('http://localhost:5001/neo4j_update_task', {
        endpoint: endpoint,
        node_name: node_name,
        task: inputText
      });
      // If the task update is successful, call the analytics API to generate code:
      if (updateTaskResponse.status === 200) {
        const urlResponse = await axios.get(`http://localhost:5000/minio_get_last_url`, {
          params: { endpoint: endpoint }
        });
        const url = urlResponse.data.url;
        console.log('[AnalyticsChart.tsx] Fetched URL (for download):', url);
        const codeResponse = await axios.get(`http://localhost:5002/analytics_generate_code`, {
          params: { task: inputText, url: url }
        });
        const generatedCode = codeResponse.data.code;
        const generatedLib = codeResponse.data.lib;
        console.log('[AnalyticsChart.tsx] Running generated code ...');
        const runResponse = await axios.get(`http://localhost:5002/analytics_run_code`, {params: {code: generatedCode, lib: generatedLib}});
        // Save in local (card) variable:
        setResultText(runResponse.data.response);
        // Store the result from running code in Neo4J:
        const updateResultResponse = await axios.post('http://localhost:5001/neo4j_update_result', {node_name: node_name, result: runResponse.data.response, endpoint: endpoint});
        console.log('[AnalyticsChart.tsx] Status for updating result:', updateResultResponse.status);
      } else {
        // Handle unsuccessful task update response
        console.error('Failed to update task:', updateTaskResponse.status);
        alert('Failed to update task in Neo4J.');
      }
    } catch (error) {
      console.error('Failed in processing task:', error);
      alert('Failed to process task.');
    }
  };

  return (
    <div style={{ marginTop: '20px', height: 'auto', textAlign: 'center', padding: '20px' }}>
      <p style={{ fontSize: '18px' }}> Provide task:</p>
      <textarea
        value={inputText}
        onChange={handleInputChange}
        placeholder="Example: I want the number of unique IP addresses."
        style={{ width: '100%', height: '250px', fontSize: '18px', padding: '12px', margin: '10px auto', display: 'block',  border: '1px solid black' }}
      />
      <button
        onClick={handleSubmit}
        style={{
          width: '100px',
          height: '60px',
          fontSize: '20px',
          padding: '12px 20px',
          marginTop: '15px',
          marginBottom: '15px',
          cursor: 'pointer',
          display: 'block',
          margin: 'auto'
        }}
      >
        Solve
      </button>
  
      {/* Result display area */}
      <p style={{ fontSize: '18px' }}>Result:</p>
      <div style={{ marginTop: '20px', textAlign: 'left', border: '1px solid black', minHeight: '250px', padding: '12px', width: '100%', margin: '10px auto',  fontSize: '18px'}}>
        <div style={{ whiteSpace: 'pre-wrap' }}>{resultText}</div>
      </div>
    </div>
  );
  
};

export default AnalyticsChart;

