import React, { useEffect,  useState } from 'react';
import { ChartProps } from '../Chart';
import { generateCypher } from '../../openai/TextToCypher';
import { ChordChart } from './component/ChordChart';
import SimpleBarChart from './component/BarChart';
import axios from 'axios'; // HTTP client

const CountChart = (props: ChartProps) => {
  //const { generated, setGenerated } = useState(0);
  const { records, settings, getGlobalParameter } = props;
  // const type = settings && settings.format ? settings.format : 'json';
  const node = records && records[0] && records[0]._fields && records[0]._fields[0] ? records[0]._fields[0]: {};
  const name = node.properties['name'] // Obs. We use name as identifier - TODO: use something else #UNDO
  const [result, setResult] = useState('');
  const [chartData, setChartData] = useState(null);
  const [chartType, setChartType] = useState(''); // 'bar' or 'chord'
  const [isAnalysisRun, setIsAnalysisRun] = useState(false);

  const handleSubmit = async () => {
    // Fetch result of the static node linked to current node using identifier: 
    try {
      const updateResultResponse = await axios.post('http://localhost:5001/fetch_result', {node_name: name});
      // console.log(updateResultResponse.data[0].toString());
      setResult(updateResultResponse.data[0].toString()); // Assuming response data is the result
      console.log('[CountChart.tsx] Fetched following result from static node:', result);
      if (updateResultResponse.status === 200){
        setIsAnalysisRun(true);
        const { transformedData, chartType } = transformResultToChartFormat(updateResultResponse.data[0].toString());
        setChartData(transformedData);
        setChartType(chartType);
      } else {
        // If result is not fetched succesfully, remind user to run analysis first. 
        alert("Please run the analysis module.");
      }
    } catch (error) {
      console.error('[CountChart.tsx] Failed fetching result from static node:', error);
    }
  }

  const transformResultToChartFormat = (response) => {
    // TODO: Guarantee output format by guardrails.
    // Check to see if response string includes something that looks like a Python dictionary
    const dictionaryRegex = /\{(?:[^{}]|{[^{}]*})*\}/;
    const dictionaryMatch = response.match(dictionaryRegex);
    if (dictionaryMatch){
      // Extract only dictionary part:
      const dictionaryContent = dictionaryMatch[0];
      console.log("[CountChart.tsx] Dictionary string content:");
      console.log(dictionaryContent);
      // Transform string to actual dictionary:
      const correctedJSONString = dictionaryContent.replace(/'/g, '"');
      const actualDict = JSON.parse(correctedJSONString);
      console.log("[CountChart.tsx] Dictionary object content:");
      console.log(actualDict);
      // Build regex with format rules:
      const barRegex = /\{\s*([\'"])(?!answer\b)[^\'"]+\1\s*:\s*-?\d+(\.\d+)?\s*(,\s*([\'"])(?!answer\b)[^\'"]+\4\s*:\s*-?\d+(\.\d+)?\s*)*\}/;
      const chordRegex = /\{\s*(['"])(?!answer\b)[^'"]+\1\s*:\s*\[\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)(?:,\s*-?\d+(?:\.\d+)?)*\s*\](?:,\s*\1(?!answer\b)[^'"]+\1\s*:\s*\[\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)(?:,\s*-?\d+(?:\.\d+)?)*\s*\])*\s*\}/;
      const simpleRegex = /\{\s*(['"])answer\s*\1\s*:\s*(\1[^'\"]*?\1|[\d.-]+)\s*\}/;
      // Test each regex against the dictionary content:
      if (barRegex.test(dictionaryContent)) {
          // This block will execute if the dictionary meets the bar format rule {key (str) : value (int,float), ...}
          console.log("[CountChart.tsx] The dictionary follows the bar format rules.");
          const labels = Object.keys(actualDict); // Categories
          const data = Object.values(actualDict); // Values
          const barTransformedData = {
            labels: labels,
            datasets: [{
              label: 'Bar chart',
              data: data,
              backgroundColor: 'rgba(255, 99, 132, 0.2)', // Example color
            }]
          };
          return { transformedData: barTransformedData, chartType: "bar"};
      } else if (chordRegex.test(dictionaryContent)) {
        // This block will execute if the dictionary meets the chord format rule {key (str) : [value (int,float), ... ],  ... }
         console.log("[CountChart.tsx] The dictionary follows the chord format rules.");
         const chordTransformedData = correctedJSONString;
         return { transformedData: chordTransformedData, chartType: "chord" };
      } else if (simpleRegex.test(dictionaryContent)) {
        // This block will execute if the dictionary meets the simple answer format rule {"answer" : val (str/int/float)}
        console.log("[CountChart.tsx] The dictionary follows the simple format rules.");
        const simpleTransformedData = Object.values(actualDict)[0]; 
        return { transformedData: simpleTransformedData, chartType: "simple" };
      } else {
          console.log("[CountChart.tsx] Error: The dictionary does not follow any recognized format rules.");
          alert("Format not recognized. Please run the analysis module again.");
      }
    } else {
      console.log("[CountChart.tsx] Error: The response does not include a dictionary.");
      alert("Please run the analysis module again.");
    }
    return { transformedData: null, chartType: "" };
  }

  return (
    <div style={{ marginTop: '20px', height: 'auto', textAlign: 'center', padding: '20px' }}>
        {!isAnalysisRun && <p style={{ fontSize: '18px' }}>Run analytics module before graph generation!</p>}
        {!chartData && (  // Render the button only if there is no chartData
            <button onClick={handleSubmit} style={{ width: '120px', height: '60px', fontSize: '20px', padding: '12px 20px', marginTop: '10px', marginBottom: '15px', cursor: 'pointer', display: 'block', margin: 'auto' }}>
                Generate
            </button>
        )}
        {chartData && (
            <>
                {chartType === 'chord' && <ChordChart rvalue={chartData} />}
                {chartType === 'bar' && <SimpleBarChart chartData={chartData} />}
                {chartType === 'simple' && (
                    <pre style={{ textAlign: 'left', whiteSpace: 'pre-wrap', wordWrap: 'break-word', fontSize: '18px' }}>
                        {"Diagram cannot be generated for given result: \n" + JSON.stringify(chartData, null, 2)}
                    </pre>
                )}
            </>
        )}
    </div>
);

};

export default CountChart;