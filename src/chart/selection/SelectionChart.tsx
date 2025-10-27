import React, { useState } from 'react';
import { ChartProps } from '../Chart';
import axios from 'axios'; 

const NEO4J_ENDPOINT_5001 = 'https://madt4bc.dynabic.dev/neo4j-api';

const SelectionChart = (props: ChartProps) => {
  const { records, settings, getGlobalParameter } = props;
  const [selectedUC, setSelectedUC] = useState<string>('0'); // Default

  const handleChange = async (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newUc = event.target.value;
    setSelectedUC(newUc);
    console.log('[SelectionChart.tsx] Selected UC:', newUc);

    try {
      const postUrl = `${NEO4J_ENDPOINT_5001}/neo4j_update_uc`;
      const updateResponse = await axios.post(postUrl, { uc: newUc }); // send as JSON
      console.log('[SelectionChart.tsx] UC update status in Neo4j:', updateResponse.data.status);
    } catch (error: any) {
      console.error('[SelectionChart.tsx] Error updating UC in Neo4j:', error.message || error);
    }
  };

  return (
    <div style={{ padding: '10px' }}>
      <label htmlFor="uc-select" style={{ marginRight: '10px', fontWeight: 'bold' }}>
        Use Case:
      </label>
      <select
        id="uc-select"
        value={selectedUC}
        onChange={handleChange}
        style={{
          padding: '6px 10px',
          borderRadius: '8px',
          border: '1px solid #ccc',
          fontSize: '14px',
          backgroundColor: '#fff',
          cursor: 'pointer',
        }}
      >
        <option value="0">Select</option>
        <option value="1">UC1</option>
        <option value="2">UC2</option>
        <option value="3">UC3</option>
        <option value="4">UC4</option>
      </select>
    </div>
  );
};

export default SelectionChart;