import React from 'react';
import { Bar } from 'react-chartjs-2';

// Import Chart.js parts needed for a bar chart
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

// Register the components in Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface SimpleBarChartProps {
  chartData: {
    labels: string[];
    datasets: {
      label: string;
      data: number[];
      backgroundColor: string;
    }[];
  };
}

const SimpleBarChart: React.FC<SimpleBarChartProps> = ({ chartData }) => {
  return <Bar data={chartData} />;
};

export default SimpleBarChart;