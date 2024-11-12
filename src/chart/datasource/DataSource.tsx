import React, { useEffect, useState } from 'react';
import { ChartProps } from '../Chart';
import { generateCypher } from '../../openai/TextToCypher';
import ReactJson from 'react-json-view'
import { MqttList } from './component/MqttList';
import {RestGet} from './component/RestGet';
import axios from 'axios';


/**
 * Renders Neo4j records as their JSON representation.
 */
const DataSourceChart = (props: ChartProps) => {
  //const { generated, setGenerated } = useState(0);

  const { records, settings, getGlobalParameter } = props;
  const type = settings && settings.format ? settings.format : 'json';
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0] : {};
  const nodetype = node.properties['type'];
  const asset_id = node.properties['uid'].toLowerCase();
  const endpoint = node.properties['endpoint'];

  const handleUpdateClick = async () => {
    try {
      const response = await axios.get('http://localhost:5000/minio_update_database', {
        params: {
          topic: endpoint,
          asset_id: asset_id,
        } 
      });
      console.log('[DataSource.tsx] Updating database returned following status:');
      console.log(response.data); // For now, just log the response
    } catch (error) {
      console.error('[DataSource.tsx] Error updating database:', error);
    }
  };

  return (
    <div style={{ marginTop: '0px', height: '100%', textAlign: 'center' }}>
      {nodetype === 'rest' && <RestGet endpoint={endpoint} />}
      {nodetype === 'mqtt' && <MqttList endpoint={endpoint} topic={node?.properties['topic']} />}
      {nodetype !== 'rest' && nodetype !== 'mqtt' && (
        <button
          style={{ padding: '15px 25px', fontSize: '20px', cursor: 'pointer', marginTop: '20px' }}
          onClick={handleUpdateClick}
        >
          Update database
        </button>
      )}
    </div>
  );
};

export default DataSourceChart;
