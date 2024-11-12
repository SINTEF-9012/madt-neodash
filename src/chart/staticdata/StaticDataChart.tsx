import React, { useEffect, useState } from 'react';
import { ChartProps } from '../Chart';
import { generateCypher } from '../../openai/TextToCypher';
import axios from 'axios'; // HTTP client

/**
 * Renders Neo4j records as their JSON representation.
 */

const StaticDataChart = (props: ChartProps) => {
  //const { generated, setGenerated } = useState(0);

  const { records, settings, getGlobalParameter } = props;
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0] : {};
  const [url, setUrl] = useState('');
  const endpoint = node.properties['endpoint']; // Obs! Used as bucket name
  const node_name = node.properties['name'];

  const fetchUrl = () => {
    // Existing code to fetch the URL
    const httpString = 'http://localhost:5000/minio_get_last_url?endpoint=' + endpoint;
    axios.get(httpString)
      .then((response) => {
        const apiUrl = response.data.url;
        setUrl(apiUrl);  // This will trigger the useEffect listening to `url`
      })
      .catch((error) => {
        console.error('[StaticDataChart.tsx] Error fetching URL:', error);
      });
  };

  const handleDownload = () => {
    // Trigger the download function in `minio_api.py`
    const httpStringDownload = `http://localhost:5000/minio_local_download?endpoint=${endpoint}`;
    axios.get(httpStringDownload)
      .then((response) => {
        if (response.data.status === 200) {
          console.log('[StaticDataChart.tsx] Download triggered successfully.');
          // Add any additional success handling if needed
        } else {
          console.error('[StaticDataChart.tsx] Error triggering download:', response.data);
        }
      })
      .catch((error) => {
        console.error('[StaticDataChart.tsx] Error triggering download:', error);
      });
  };

  useEffect(() => {
    // Fetch the URL when the component mounts
    fetchUrl();
  }, [endpoint]);

  useEffect(() => {
    const fetchAndUpdateUrl = async () => {
      try {
        // Update the URL in the Neo4J graph
        if (url) {
          await axios.post('http://localhost:5001/neo4j_update_url', {
            node_name : node_name,
            endpoint: endpoint, 
            url: url
          });
          console.log('[StaticDataChart.tsx] Static node updated with URL:', url);
        }
      } catch (error) {
        console.error('[StaticDataChart.tsx] Error in fetchAndUpdateUrl:', error);
      }
    };
    // TODO: Change according to time expire date:
    if (endpoint) {
      fetchAndUpdateUrl();
    }
  }, [url, endpoint]); // Re-run when `endpoint` and 'url' changes


  return ( 
    <div style={{ marginTop: '0px', height: '100%', textAlign: 'center' }}>
      <p style={{ fontSize: '18px' }}> Download latest file to downloads directory: </p>
      <button onClick={handleDownload} style={{ fontSize: '18px', padding: '10px 20px' }}>
        Download
      </button>
    </div>
  );
};

export default StaticDataChart;

