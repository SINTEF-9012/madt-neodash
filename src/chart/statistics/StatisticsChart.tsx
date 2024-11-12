import React, { useEffect, useState } from 'react';
import { ChartProps } from '../Chart';
import { generateCypher } from '../../openai/TextToCypher';
import axios from 'axios'; // HTTP client

/**
 * Renders Neo4j records as their JSON representation.
 */

const StatisticsTable = ({ data }) => {
  if (!data) {
    return <p>No data available.</p>;
  }

  // Extracting keys (packet_size, inter_arrival) and stats (count, mean, etc.)
  const keys = Object.keys(data);
  const stats = keys.length > 0 ? Object.keys(data[keys[0]]) : [];

  return (
    <table>
      <thead>
        <tr>
          <th>Statistic</th>
          {stats.map(stat => <th key={stat}>{stat}</th>)}
        </tr>
      </thead>
      <tbody>
        {keys.map(key => (
          <tr key={key}>
            <td>{key}</td>
            {stats.map(stat => <td key={`${key}-${stat}`}>{data[key][stat]}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
};


const StatisticsChart = (props: ChartProps) => {
  //const { generated, setGenerated } = useState(0);

  const { records, settings, getGlobalParameter } = props;
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0] : {};
  const [statistics, setStatistics] = useState('');
  const endpoint = node.properties['endpoint']; // Obs! Used as bucket name

  const fetchStatistics = async () => {
    try {
      const urlResponse = await axios.get(`http://localhost:5000/minio_get_last_url`, {
        params: { endpoint: endpoint }
      });
      const url = urlResponse.data.url;
      console.log('[StatisticsChart.tsx] Fetched URL:', url);
      const statResponse = await axios.get(`http://localhost:5003/get_statistics`, {
        params: { url: url }
      });
      console.log(statResponse.data);
      setStatistics(statResponse.data); // Assuming response data is the url
      if (statResponse.status === 200){
        console.log('[StatisticsChart.tsx] Fetched statistics.');
      } else {
        // TODO: If result is not fetched succesfully, alert user:
        alert("[StatisticsChart.tsx] Error encountered in fetching statistics.");
      }
    } catch (error) {
    console.error('[CountChart.tsx] Failed fetching result from static node:', error);
    }
  };

  useEffect(() => {
    // Fetch the statistics when the component mounts
    fetchStatistics();
  }, [endpoint]);

  return ( 
    <div style={{ marginTop: '0px', height: '100%', textAlign: 'center'}}>
		<div style={{ overflowX: 'auto' }}>
			<StatisticsTable data={statistics} />
		</div>
    </div>
  );
};

export default StatisticsChart;
