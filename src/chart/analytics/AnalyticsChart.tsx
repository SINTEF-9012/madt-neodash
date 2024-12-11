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
    const startTime = new Date(); // Start timer
    try {
      // Check what kind of node is being WorkedOn by Analytics node:
      const parent_type =  await axios.get('http://localhost:5001/neo4j_get_parent_type', {
        params: { endpoint: endpoint, node_name: node_name }
      });
      if (parent_type.data[0] === "staticdata") {
        // Static Data Analysis - Analyses the last uploaded static file
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
          const codeResponse = await axios.get(`http://localhost:5002/analytics_generate_and_run_code`, {
            params: { task: inputText, url: url }
          });
          const generatedCode = codeResponse.data.code;
          const executationResult = codeResponse.data.result;
          setResultText(codeResponse.data.result);
          // Store the result from running code in Neo4J:
          const updateResultResponse = await axios.post('http://localhost:5001/neo4j_update_result', {node_name: node_name, result: codeResponse.data.result, endpoint: endpoint});
          console.log('[AnalyticsChart.tsx] Status for updating result:', updateResultResponse.status);
        } else {
          // Handle unsuccessful task update response
          console.error('Failed to update task:', updateTaskResponse.status);
          alert('Failed to update task in Neo4J.');
        }
      } else {
        // Realtime Data Analysis - Analyses the latest downloaded real-time file
        // Store task in Neo4J:
        const updateTaskResponse = await axios.post('http://localhost:5001/neo4j_update_task', {
          endpoint: endpoint,
          node_name: node_name,
          task: inputText
        });
         // If the task update is successful, call the analytics API to generate code:
        if (updateTaskResponse.status === 200) {
          const url = null;
          const codeResponse = await axios.get(`http://localhost:5002/analytics_generate_and_run_code`, {
            params: { task: inputText, url: url }
          });
          const generatedCode = codeResponse.data.code;
          const executationResult = codeResponse.data.result;
          setResultText(codeResponse.data.result);
          // Store the result from running code in Neo4J:
          const updateResultResponse = await axios.post('http://localhost:5001/neo4j_update_result', {node_name: node_name, result: codeResponse.data.result, endpoint: endpoint});
          console.log('[AnalyticsChart.tsx] Status for updating result:', updateResultResponse.status);
        }
      }
    } catch (error) {
      console.error('Failed in processing task:', error);
      alert('Failed to process task.');
    }  finally {
      const endTime = new Date(); // End timer
      const duration = (endTime.getTime() - startTime.getTime()) / 1000; // Calculate duration in seconds
      console.log(`[AnalyticsChart.tsx] handleSubmit execution time: ${duration} seconds`);
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
      }}
    >
      <p
        style={{
          fontSize: '20px',
          fontWeight: 'bold',
          marginBottom: '10px',
          color: '#333',
        }}
      >
        Provide task:
      </p>
      <textarea
        value={inputText}
        onChange={handleInputChange}
        placeholder="Example: I want the number of unique IP addresses."
        style={{
          width: '100%',
          height: '300px', // Increased height
          fontSize: '16px',
          padding: '10px',
          border: '1px solid #ccc',
          borderRadius: '4px',
          resize: 'none',
          marginBottom: '15px',
          boxSizing: 'border-box',
        }}
      />
      <button
        onClick={handleSubmit}
        style={{
          width: '120px',
          height: '50px',
          fontSize: '16px',
          fontWeight: 'bold',
          color: '#fff',
          backgroundColor: '#007BFF',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          display: 'block',
          margin: '10px auto 20px auto',
          transition: 'background-color 0.3s',
        }}
        onMouseOver={(e) =>
          (e.currentTarget.style.backgroundColor = '#0056b3')
        }
        onMouseOut={(e) =>
          (e.currentTarget.style.backgroundColor = '#007BFF')
        }
      >
        Solve
      </button>

      {/* Result display area */}
      <p
        style={{
          fontSize: '20px',
          fontWeight: 'bold',
          marginBottom: '10px',
          color: '#333',
        }}
      >
        Solution:
      </p>
      <div
        style={{
          textAlign: 'left',
          border: '1px solid #ccc',
          minHeight: '300px', // Increased height
          padding: '10px',
          borderRadius: '4px',
          backgroundColor: '#fff',
          boxSizing: 'border-box',
          fontSize: '16px',
          whiteSpace: 'pre-wrap',
        }}
      >
        {resultText || 'No result yet. Please provide a task and click "Solve".'}
      </div>
    </div>
  );
};

export default AnalyticsChart;

