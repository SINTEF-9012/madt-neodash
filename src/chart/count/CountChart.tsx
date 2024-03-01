import React, { useState } from 'react';
import { ChartProps } from '../Chart';
import { generateCypher } from '../../openai/TextToCypher';
import { ChordChart } from './component/ChordChart';


/**
 * Renders Neo4j records as their JSON representation.
 */
const CountChart = (props: ChartProps) => {
  //const { generated, setGenerated } = useState(0);

  const { records, settings, getGlobalParameter } = props;
  const type = settings && settings.format ? settings.format : 'json';
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0] : {};
  return (
    <div style={{ marginTop: '0px', height: '100%' }}>
      {node.properties?.rtype == 'traffic_p2p_count' &&
        <ChordChart
          rvalue={node.properties['result']} 
        />
      }
    </div>
  );
};

export default CountChart;