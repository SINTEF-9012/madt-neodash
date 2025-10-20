import React, { useState } from 'react';
import axios from 'axios'; // HTTP client
import { ChartProps } from '../Chart';




const DesignChart = (props: ChartProps) => {
  const { records } = props;
  // Extract nodes
  const validTypes = ['ASSET', 'ATTACKER', 'EVENT', 'CONSEQUENCE', 'THREAT'];

  const NEO4J_ENDPOINT_5001 = 'https://madt4bc.dynabic.dev/neo4j-api';
  const MINIO_ENPOINT_5000 = 'https://madt4bc.dynabic.dev/minio-api';
  const INFLUXDB_ENDPOINT_4999 = 'https://madt4bc.dynabic.dev/influxdb-api';

  // const NEO4J_ENDPOINT_5001 = "http://localhost:5001";
  // const MINIO_ENPOINT_5000 = "http://localhost:5000";
  // const INFLUXDB_ENDPOINT_4999 = "http://localhost:4999";

  const filteredNodes = records
    .map((record: any) => record._fields?.[0])
    .filter((node: any) => node?.labels?.some((label: string) => validTypes.includes(label)));

  const [nodeData, setNodeData] = useState({
    name: '',
    type: 'ASSET',
    // usecase: 1,
    assetTypes: {
        datasource: false,
        staticdata: false
    },
    customProps: [{ key: '', value: '' }],
    endpoint: ''
  });
  const [nodes, setNodes] = useState<any[]>([]);
  const [sourceNode, setSourceNode] = useState('');
  const [targetNode, setTargetNode] = useState('');
  const [selectedAsset, setSelectedAsset] = useState('');

 const handleStaticData = async () => {
    try {
      const postData = {asset_uid: selectedAsset};
      const postUrl = NEO4J_ENDPOINT_5001+'/neo4j_add_static_data';
      const updateResponse = await axios.post(postUrl, postData);
      const {message, uid } = updateResponse.data;
      alert(message);
      //console.log(uid);
      // If staticdata uid returned, create bucket in minio:
      if (uid) {
        await axios.post(MINIO_ENPOINT_5000+'/minio_add_bucket', { bucket: uid });
      }
    } catch (err) {
      console.error('[DesignChart.tsx] Error creating static data node:', err);
      alert('Failed to create Static Data node.');
    }
  };

  const handleConnect = async () => {
    
    try {
      const postData = {source_uid: sourceNode,
                        target_uid: targetNode};
      const postUrl = NEO4J_ENDPOINT_5001+'/neo4j_add_relation';
      const updateResponse = await axios.post(postUrl, postData);
      alert('Relation created!');
    } catch (err) {
      console.error('Error creating relation:', err);
      alert('Failed to create relation.');
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
  const { name, value, type, checked } = e.target;

    if (name === 'type') {
      setNodeData({ ...nodeData, type: value });
    } else if (name === 'datasource' || name === 'staticdata') {
      setNodeData({
        ...nodeData,
        assetTypes: { ...nodeData.assetTypes, [name]: checked }
      });
    } else {
      setNodeData({ ...nodeData, [name]: value });
    }
  };

  const handleCustomPropChange = (index: number, field: 'key' | 'value', value: string) => {
    const newProps = [...nodeData.customProps];
    newProps[index][field] = value;
    setNodeData({ ...nodeData, customProps: newProps });
  };

  const addCustomProp = () => {
    setNodeData({ ...nodeData, customProps: [...nodeData.customProps, { key: '', value: '' }] });
  };

  const removeCustomProp = (index: number) => {
    const newProps = nodeData.customProps.filter((_, i) => i !== index);
    setNodeData({ ...nodeData, customProps: newProps });
  };

  const handleSubmit = async () => {
    if (!nodeData.name || !nodeData.type) {
      alert('Name and Type are required');
      return;
    }
    const postData = {
      ...nodeData,
      customProps: nodeData.customProps.filter(p => p.key && p.value)
    };
    try {
      const postUrl = NEO4J_ENDPOINT_5001+'/neo4j_add_node';
      const updateResponse = await axios.post(postUrl, postData);
      // Destructure the response data
      const {message, datasource, staticdata, uid } = updateResponse.data;
      alert(message);
      //console.log(datasource);
      //console.log(staticdata);
      //console.log(uid);
      // If staticdata is true, create a bucket in Minio with uid as name
      if (staticdata === true) {
        console.log("Triggered minio bucket adding.")
        await axios.post(MINIO_ENPOINT_5000+'/minio_add_bucket', { bucket: uid });
      }
  
      // If datasource is true, create a bucket in InfluxDB with uid as name
      if (datasource === true) {
        console.log("Triggered influxdb bucket adding.")
        await axios.post(INFLUXDB_ENDPOINT_4999+'/influxdb_add_bucket', { bucket: uid });
      }
    } catch (error) {
      console.error(error);
      alert('Failed to create node');
    }
  };

  return (
    <div style={{ textAlign: 'center', padding: '30px' }}>
      {/* ------------------ CREATE NODE SECTION ------------------ */}
      <div style={{ padding: '20px', border: '1px solid #ccc', borderRadius: '10px', marginBottom: '40px' }}>
        <h2 style={{ color: '#333', marginBottom: '20px' }}>➕ Create New Node</h2>
  
        {/* Name*/}
        {['name'].map(field => (
          <div key={field} style={{ marginBottom: '15px' }}>
            <label>{field.charAt(0).toUpperCase() + field.slice(1)}:</label>
            <input
              type="text"
              name={field}
              value={nodeData[field]}
              onChange={handleChange}
              style={{ display: 'block', width: '100%', padding: '10px' }}
            />
          </div>
        ))}
  
        {/* Node Type Selection */}
        <div style={{ marginBottom: '20px' }}>
          <label>Node Type:</label>
          <select name="type" value={nodeData.type} onChange={handleChange} style={{ width: '100%', padding: '10px' }}>
            <option value="ASSET">ASSET</option>
            <option value="ATTACKER">ATTACKER</option>
            <option value="EVENT">EVENT</option>
            <option value="CONSEQUENCE">CONSEQUENCE</option>
            <option value="THREAT">THREAT</option>
          </select>
        </div>
  
        {/* ASSET Subtypes */}
        {nodeData.type === 'ASSET' && (
        <>
            <div style={{ marginBottom: '20px' }}>
            <label>
                <input
                type="checkbox"
                name="datasource"
                checked={nodeData.assetTypes.datasource}
                onChange={handleChange}
                />
                Data Source
            </label>
            <label style={{ marginLeft: '10px' }}>
                <input
                type="checkbox"
                name="staticdata"
                checked={nodeData.assetTypes.staticdata}
                onChange={handleChange}
                />
                Static Data
            </label>
            </div>

            {nodeData.assetTypes.datasource && (
            <div style={{ marginTop: '20px' }}>
                <label>Endpoint:</label>
                <input
                type="text"
                name="endpoint"
                placeholder="Kafka Topic Name"
                value={nodeData.endpoint}
                onChange={handleChange}
                style={{ display: 'block', width: '100%', padding: '10px', marginTop: '5px' }}
                />
            </div>
            )}
        </>
        )}
  
        {/* Custom Properties */}
        <div>
          <h4 style={{ marginBottom: '10px' }}>Custom Properties</h4>
          {nodeData.customProps.map((prop, idx) => (
            <div key={idx} style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px' }}>
              <input
                type="text"
                placeholder="Key"
                value={prop.key}
                onChange={e => handleCustomPropChange(idx, 'key', e.target.value)}
                style={{ marginRight: '10px', padding: '8px' }}
              />
              <input
                type="text"
                placeholder="Value"
                value={prop.value}
                onChange={e => handleCustomPropChange(idx, 'value', e.target.value)}
                style={{ marginRight: '10px', padding: '8px' }}
              />
              <button
                onClick={() => removeCustomProp(idx)}
                style={{ backgroundColor: '#dc3545', color: 'white', padding: '5px 10px', borderRadius: '4px' }}
              >
                X
              </button>
            </div>
          ))}
          <button onClick={addCustomProp} style={{ padding: '8px 12px', marginTop: '10px' }}>
            Add Property
          </button>
        </div>
  
        <button
          onClick={handleSubmit}
          style={{
            marginTop: '30px',
            padding: '12px 20px',
            backgroundColor: '#28a745',
            color: 'white',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '6px',
          }}
        >
          Create Node
        </button>
      </div>
  
      {/* ------------------ ADD RELATIONSHIP SECTION ------------------ */}
      <div style={{ padding: '20px', border: '1px solid #ccc', borderRadius: '10px' }}>
        <h2 style={{ color: '#333', marginBottom: '20px' }}>🔗 Create Relationship</h2>
  
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            marginBottom: '20px',
          }}
        >
          {/* Source Node Dropdown */}
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>Source Node:</label>
            <select
              value={sourceNode}
              onChange={(e) => setSourceNode(e.target.value)}
              style={{ width: '100%', padding: '10px' }}
            >
              <option value="">Select Source Node</option>
              {filteredNodes.map((node: any) => (
                <option key={node.properties.uid} value={node.properties.uid}>
                  {node.properties.name} ({node.labels[0]}, {node.properties.uid.slice(0, 6)}…)
                </option>
              ))}
            </select>
          </div>
  
          {/* CONNECT TO Arrow Button */}
          <button
            onClick={handleConnect}
            disabled={!sourceNode || !targetNode}
            style={{
              position: 'relative',
              padding: '10px 30px',
              backgroundColor: !sourceNode || !targetNode ? '#ccc' : '#007bff',
              color: 'white',
              fontWeight: 'bold',
              borderRadius: '5px',
              border: 'none',
              cursor: !sourceNode || !targetNode ? 'not-allowed' : 'pointer',
              marginTop: '22px',
              transition: 'background-color 0.3s',
            }}
          >
            CONNECT TO
            <div
              style={{
                position: 'absolute',
                top: '50%',
                right: '-15px',
                transform: 'translateY(-50%)',
                width: '0',
                height: '0',
                borderTop: '7px solid transparent',
                borderBottom: '7px solid transparent',
                borderLeft: `15px solid ${!sourceNode || !targetNode ? '#ccc' : '#007bff'}`,
              }}
            ></div>
          </button>
  
          {/* Target Node Dropdown */}
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>Target Node:</label>
            <select
              value={targetNode}
              onChange={(e) => setTargetNode(e.target.value)}
              style={{ width: '100%', padding: '10px' }}
            >
              <option value="">Select Target Node</option>
              {filteredNodes
              .filter((node: any) => 
                node.labels.includes('ASSET') || 
                node.labels.includes('EVENT') || 
                node.labels.includes('CONSEQUENCE')
              )
              .map((node: any) => (
                <option key={node.properties.uid} value={node.properties.uid}>
                  {node.properties.name} ({node.labels[0]}, {node.properties.uid.slice(0, 6)}…)
                </option>
                ))}
            </select>
          </div>
        </div>
      </div>
       {/* ------------------ CREATE STATIC DATA SECTION ------------------ */}
      <div
        style={{
          padding: '20px',
          border: '1px solid #ccc',
          borderRadius: '10px',
          marginTop: '40px',
        }}
      >
        <h2 style={{ color: '#333', marginBottom: '20px' }}>📄 Link Static Data</h2>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            marginBottom: '20px',
          }}
        >
          {/* Asset Node dropdown */}
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>Asset Node:</label>
            <select
              value={selectedAsset}
              onChange={(e) => setSelectedAsset(e.target.value)}
              style={{ width: '100%', padding: '10px' }}
            >
              <option value="">Select Asset Node</option>
              {filteredNodes
                .filter((node: any) => node.labels.includes('ASSET'))
                .map((node: any) => (
                  <option key={node.properties.uid} value={node.properties.uid}>
                    {node.properties.name} ({node.properties.uid.slice(0, 6)}…)
                  </option>
                ))}
            </select>
          </div>

          {/* Create Static Data button */}
          <button
            onClick={handleStaticData}
            disabled={!selectedAsset}
            style={{
              padding: '10px 20px',
              backgroundColor: !selectedAsset ? '#ccc' : '#17a2b8',
              color: 'white',
              fontWeight: 'bold',
              borderRadius: '5px',
              border: 'none',
              cursor: !selectedAsset ? 'not-allowed' : 'pointer',
              marginTop: '22px',
            }}
          >
            Link
          </button>
        </div>
      </div>
    </div>
  );
};

export default DesignChart;
