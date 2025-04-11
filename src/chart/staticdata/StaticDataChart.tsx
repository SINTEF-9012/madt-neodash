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
  const bucket = node.properties['bucket']; // Obs! Instead of endpoint
  const node_name = node.properties['name'];
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleDownload = () => {
    // Trigger the download function in `minio_api.py`
    const httpStringDownload = `http://localhost:5000/minio_local_download?endpoint=${bucket}`;
    axios.get(httpStringDownload)
      .then((response) => {
        if (response.data.status === 200) {
          console.log('[StaticDataChart.tsx] Download triggered.');
          // Add any additional success handling if needed
        } else {
          console.error('[StaticDataChart.tsx] Error triggering download:', response.data);
        }
      })
      .catch((error) => {
        console.error('[StaticDataChart.tsx] Error triggering download:', error);
      });
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('asset_id', bucket);
    // Upload file in MinIO
    try {
      const uploadResponse = await axios.post('http://localhost:5000/minio_upload_file', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      console.log('[StaticDataChart.tsx] File upload returned following status:', uploadResponse.data.status);
      // If upload is successful, fetch last object URL
      if (uploadResponse.data.status === 200){
        const httpString = 'http://localhost:5000/minio_get_last_url?endpoint=' + bucket;
        const urlResponse = await axios.get(httpString);
        console.log('[StaticDataChart.tsx] URL fetched:', urlResponse.data.url);
        // If fetching URL is successful, update node with metadata
        if (urlResponse.data.url){
          // Update Neo4J - Currently type is same as format
          const postData = {
            node_name: node_name,   
            bucket: bucket,     
            url: urlResponse.data.url,
            file_name: uploadResponse.data.file_name,
            add_date: uploadResponse.data.add_date,
            data_format: uploadResponse.data.format,
            data_type: uploadResponse.data.format
          };
          const postUrl = 'http://localhost:5001/neo4j_update_metadata';
          const updateResponse = await axios.post(postUrl, postData);
          console.log('[StaticDataChart.tsx] Update status in Neo4j:', updateResponse.data.status);
        } else {
          console.error('[StaticDataChart.tsx] Error fetching URL.');
        }
      } else {
        console.error('[StaticDataChart.tsx] Error uploading file.');
      }
    } catch (error) {
      console.error('[StaticDataChart.tsx] Error uploading file:', error);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        marginTop: '0px',
      }}
    >
      {/* Upload Section */}
      <div
        style={{
          width: '80%',
          maxWidth: '400px',
          padding: '15px',
          marginBottom: '20px',
          border: '1px solid #ccc',
          borderRadius: '8px',
          textAlign: 'center',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
        }}
      >
        <h3 style={{ margin: '10px 0', fontSize: '20px', color: '#333' }}>Upload</h3>
        <p style={{ margin: '5px 0', fontSize: '14px', color: '#555' }}>
          Upload a static file.
        </p>
        <div style={{ marginTop: '15px' }}>
          <input
            type="file"
            onChange={handleFileChange}
            style={{
              margin: '10px 0',
              padding: '8px',
              fontSize: '14px',
              cursor: 'pointer',
            }}
          />
          <button
            onClick={handleFileUpload}
            style={{
              padding: '10px 20px',
              fontSize: '14px',
              cursor: 'pointer',
              backgroundColor: '#007BFF',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              marginTop: '10px',
              transition: 'background-color 0.3s',
            }}
            disabled={!selectedFile}
          >
            Upload
          </button>
        </div>
      </div>
  
      {/* Download Section */}
      <div
        style={{
          width: '80%',
          maxWidth: '400px',
          padding: '15px',
          border: '1px solid #ccc',
          borderRadius: '8px',
          textAlign: 'center',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
        }}
      >
        <h3 style={{ margin: '10px 0', fontSize: '20px', color: '#333' }}>Download</h3>
        <p style={{ margin: '10px 0', fontSize: '14px', color: '#555' }}>
          Download the latest file to your downloads directory:
        </p>
        <button
          onClick={handleDownload}
          style={{
            padding: '10px 20px',
            fontSize: '14px',
            cursor: 'pointer',
            backgroundColor: '#28A745',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            transition: 'background-color 0.3s',
          }}
        >
          Download
        </button>
      </div>
    </div>
  );
  
};

export default StaticDataChart;

