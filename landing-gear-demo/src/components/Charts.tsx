import React, { useMemo } from 'react';

interface DataPoint {
  x: number;
  y: number;
}

interface TimeSeriesChartProps {
  data: DataPoint[];
  width?: number;
  height?: number;
  title?: string;
  xLabel?: string;
  yLabel?: string;
  color?: string;
  unit?: string;
}

export const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({
  data,
  width = 600,
  height = 250,
  title,
  xLabel = '时间 (s)',
  yLabel,
  color = '#2563eb',
  unit = '',
}) => {
  const padding = { top: 30, right: 20, bottom: 45, left: 60 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const { pathD, yScale, xTicks, yTicks, yMin, yMax } = useMemo(() => {
    if (data.length === 0) {
      return { pathD: '', yScale: (_y: number) => 0, xTicks: [], yTicks: [], yMin: 0, yMax: 0 };
    }

    let xMin = Infinity, xMax = -Infinity;
    let yMin = Infinity, yMax = -Infinity;

    data.forEach(d => {
      xMin = Math.min(xMin, d.x);
      xMax = Math.max(xMax, d.x);
      yMin = Math.min(yMin, d.y);
      yMax = Math.max(yMax, d.y);
    });

    // 扩展Y轴范围，包含0
    if (yMin > 0) yMin = Math.min(0, yMin * 0.95);
    if (yMax < 0) yMax = Math.max(0, yMax * 0.95);
    if (Math.abs(yMax - yMin) < 1e-10) {
      yMin -= 1;
      yMax += 1;
    }

    // 对称Y轴（围绕0）
    const yAbsMax = Math.max(Math.abs(yMin), Math.abs(yMax));
    yMin = -yAbsMax * 0.05;
    yMax = yAbsMax * 1.05;

    const xScale = (x: number) => padding.left + ((x - xMin) / (xMax - xMin || 1)) * chartWidth;
    const yScale = (y: number) => padding.top + chartHeight - ((y - yMin) / (yMax - yMin || 1)) * chartHeight;

    const pathD = data
      .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(d.x).toFixed(2)} ${yScale(d.y).toFixed(2)}`)
      .join(' ');

    // 生成刻度
    const xTickCount = 6;
    const xTicks = Array.from({ length: xTickCount + 1 }, (_, i) => {
      const x = xMin + (i / xTickCount) * (xMax - xMin);
      return { value: x, x: xScale(x) };
    });

    const yTickCount = 5;
    const yTicks = Array.from({ length: yTickCount + 1 }, (_, i) => {
      const y = yMin + (i / yTickCount) * (yMax - yMin);
      return { value: y, y: yScale(y) };
    });

    return { pathD, xScale, yScale, xTicks, yTicks, yMin, yMax };
  }, [data, chartWidth, chartHeight]);

  const formatNum = (n: number) => {
    if (Math.abs(n) >= 1000) return (n / 1000).toFixed(2) + 'k';
    if (Math.abs(n) < 0.01 && n !== 0) return n.toExponential(1);
    return n.toFixed(2);
  };

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="h-full flex items-center justify-center text-gray-400">
          请运行仿真以查看结果
        </div>
      </div>
    );
  }

  return (
    <svg width={width} height={height} className="bg-white rounded-lg border border-gray-200">
      {title && (
        <text
          x={width / 2}
          y={18}
          textAnchor="middle"
          className="text-sm font-semibold fill-gray-700"
          fontSize="14"
        >
          {title}
        </text>
      )}

      {/* 网格线 */}
      {yTicks.map((tick, i) => (
        <line
          key={`y-grid-${i}`}
          x1={padding.left}
          x2={width - padding.right}
          y1={tick.y}
          y2={tick.y}
          stroke="#e5e7eb"
          strokeWidth="1"
        />
      ))}

      {/* 零线 */}
      {yMin < 0 && yMax > 0 && (
        <line
          x1={padding.left}
          x2={width - padding.right}
          y1={yScale(0)}
          y2={yScale(0)}
          stroke="#9ca3af"
          strokeWidth="1"
          strokeDasharray="4,4"
        />
      )}

      {/* 坐标轴 */}
      <line
        x1={padding.left}
        y1={padding.top}
        x2={padding.left}
        y2={height - padding.bottom}
        stroke="#374151"
        strokeWidth="1.5"
      />
      <line
        x1={padding.left}
        y1={height - padding.bottom}
        x2={width - padding.right}
        y2={height - padding.bottom}
        stroke="#374151"
        strokeWidth="1.5"
      />

      {/* Y轴刻度 */}
      {yTicks.map((tick, i) => (
        <g key={`y-tick-${i}`}>
          <line
            x1={padding.left - 4}
            x2={padding.left}
            y1={tick.y}
            y2={tick.y}
            stroke="#374151"
          />
          <text
            x={padding.left - 8}
            y={tick.y + 4}
            textAnchor="end"
            fontSize="11"
            className="fill-gray-600"
          >
            {formatNum(tick.value)}
          </text>
        </g>
      ))}

      {/* X轴刻度 */}
      {xTicks.map((tick, i) => (
        <g key={`x-tick-${i}`}>
          <line
            x1={tick.x}
            x2={tick.x}
            y1={height - padding.bottom}
            y2={height - padding.bottom + 4}
            stroke="#374151"
          />
          <text
            x={tick.x}
            y={height - padding.bottom + 16}
            textAnchor="middle"
            fontSize="11"
            className="fill-gray-600"
          >
            {tick.value.toFixed(3)}
          </text>
        </g>
      ))}

      {/* Y轴标签 */}
      <text
        x={15}
        y={padding.top + chartHeight / 2}
        textAnchor="middle"
        fontSize="12"
        className="fill-gray-700"
        transform={`rotate(-90, 15, ${padding.top + chartHeight / 2})`}
      >
        {yLabel} {unit}
      </text>

      {/* X轴标签 */}
      <text
        x={padding.left + chartWidth / 2}
        y={height - 8}
        textAnchor="middle"
        fontSize="12"
        className="fill-gray-700"
      >
        {xLabel}
      </text>

      {/* 数据曲线 */}
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
};

interface MultiLineChartProps {
  datasets: {
    data: DataPoint[];
    color: string;
    label: string;
  }[];
  width?: number;
  height?: number;
  title?: string;
  xLabel?: string;
  yLabel?: string;
  unit?: string;
}

export const MultiLineChart: React.FC<MultiLineChartProps> = ({
  datasets,
  width = 600,
  height = 250,
  title,
  xLabel = '时间 (s)',
  yLabel,
  unit = '',
}) => {
  const padding = { top: 30, right: 20, bottom: 45, left: 60 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const chartData = useMemo(() => {
    let xMin = Infinity, xMax = -Infinity;
    let yMin = Infinity, yMax = -Infinity;

    datasets.forEach(ds => {
      ds.data.forEach(d => {
        xMin = Math.min(xMin, d.x);
        xMax = Math.max(xMax, d.x);
        yMin = Math.min(yMin, d.y);
        yMax = Math.max(yMax, d.y);
      });
    });

    if (!isFinite(xMin)) {
      return null;
    }

    // 对称Y轴
    const yAbsMax = Math.max(Math.abs(yMin), Math.abs(yMax), 1);
    yMin = -yAbsMax * 0.05;
    yMax = yAbsMax * 1.05;

    const xScale = (x: number) => padding.left + ((x - xMin) / (xMax - xMin || 1)) * chartWidth;
    const yScale = (y: number) => padding.top + chartHeight - ((y - yMin) / (yMax - yMin || 1)) * chartHeight;

    const paths = datasets.map(ds => {
      const pathD = ds.data.length > 0
        ? ds.data
            .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(d.x).toFixed(2)} ${yScale(d.y).toFixed(2)}`)
            .join(' ')
        : '';
      return { pathD, color: ds.color, label: ds.label };
    });

    const xTickCount = 5;
    const xTicks = Array.from({ length: xTickCount + 1 }, (_, i) => {
      const x = xMin + (i / xTickCount) * (xMax - xMin);
      return { value: x, x: xScale(x) };
    });

    const yTickCount = 5;
    const yTicks = Array.from({ length: yTickCount + 1 }, (_, i) => {
      const y = yMin + (i / yTickCount) * (yMax - yMin);
      return { value: y, y: yScale(y) };
    });

    return { paths, xTicks, yTicks, yMin, yMax, xScale, yScale };
  }, [datasets, chartWidth, chartHeight]);

  const formatNum = (n: number) => {
    if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'k';
    if (Math.abs(n) < 0.01 && n !== 0) return n.toExponential(1);
    return n.toFixed(2);
  };

  if (!chartData) {
    return <div className="h-full flex items-center justify-center text-gray-400">暂无数据</div>;
  }

  return (
    <svg width={width} height={height} className="bg-white rounded-lg border border-gray-200">
      {title && (
        <text x={width / 2} y={18} textAnchor="middle" className="text-sm font-semibold fill-gray-700" fontSize="14">
          {title}
        </text>
      )}

      {/* 网格线 */}
      {chartData.yTicks.map((tick, i) => (
        <line key={`y-grid-${i}`} x1={padding.left} x2={width - padding.right} y1={tick.y} y2={tick.y} stroke="#e5e7eb" />
      ))}

      {/* 坐标轴 */}
      <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />
      <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />

      {/* Y轴刻度 */}
      {chartData.yTicks.map((tick, i) => (
        <g key={`y-tick-${i}`}>
          <line x1={padding.left - 4} x2={padding.left} y1={tick.y} y2={tick.y} stroke="#374151" />
          <text x={padding.left - 8} y={tick.y + 4} textAnchor="end" fontSize="11" className="fill-gray-600">
            {formatNum(tick.value)}
          </text>
        </g>
      ))}

      {/* X轴刻度 */}
      {chartData.xTicks.map((tick, i) => (
        <g key={`x-tick-${i}`}>
          <line x1={tick.x} x2={tick.x} y1={height - padding.bottom} y2={height - padding.bottom + 4} stroke="#374151" />
          <text x={tick.x} y={height - padding.bottom + 16} textAnchor="middle" fontSize="11" className="fill-gray-600">
            {tick.value.toFixed(3)}
          </text>
        </g>
      ))}

      {/* Y轴标签 */}
      <text x={15} y={padding.top + chartHeight / 2} textAnchor="middle" fontSize="12" className="fill-gray-700"
        transform={`rotate(-90, 15, ${padding.top + chartHeight / 2})`}>
        {yLabel} {unit}
      </text>

      {/* X轴标签 */}
      <text x={padding.left + chartWidth / 2} y={height - 8} textAnchor="middle" fontSize="12" className="fill-gray-700">
        {xLabel}
      </text>

      {/* 数据曲线 */}
      {chartData.paths.map((p, i) => (
        <path key={i} d={p.pathD} fill="none" stroke={p.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      ))}

      {/* 图例 */}
      <g transform={`translate(${padding.left + 10}, ${padding.top + 10})`}>
        {chartData.paths.map((p, i) => (
          <g key={i} transform={`translate(0, ${i * 16})`}>
            <rect width="12" height="3" fill={p.color} />
            <text x="18" y="4" fontSize="10" className="fill-gray-600">{p.label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
};
