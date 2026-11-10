import React, { useMemo, useState, useRef } from 'react';

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
  /** 是否对称Y轴（围绕0） */
  symmetric?: boolean;
  /** 是否启用分位数裁剪（避免极端值撑满坐标轴） */
  quantileClip?: boolean;
}

/**
 * 将数值格式化为可读字符串
 */
function formatNum(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (abs >= 1e3) return (n / 1e3).toFixed(2) + 'k';
  if (abs >= 100) return n.toFixed(0);
  if (abs >= 1) return n.toFixed(2);
  if (abs >= 0.01 && abs > 0) return n.toFixed(3);
  if (abs === 0) return '0';
  return n.toExponential(1);
}

/**
 * 计算分位数
 */
function quantile(sortedArr: number[], q: number): number {
  if (sortedArr.length === 0) return 0;
  const pos = (sortedArr.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (base + 1 < sortedArr.length) {
    return sortedArr[base] + rest * (sortedArr[base + 1] - sortedArr[base]);
  }
  return sortedArr[base];
}

interface ComputeScaleResult {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  xScale: (x: number) => number;
  yScale: (y: number) => number;
  xTicks: { value: number; x: number }[];
  yTicks: { value: number; y: number }[];
}

function computeScale(
  data: DataPoint[],
  padding: { top: number; right: number; bottom: number; left: number },
  chartWidth: number,
  chartHeight: number,
  xRange: [number, number] | null,
  symmetric: boolean,
  quantileClip: boolean
): ComputeScaleResult | null {
  if (data.length === 0) return null;

  let xMin = Infinity, xMax = -Infinity;
  let yRawMin = Infinity, yRawMax = -Infinity;

  data.forEach(d => {
    xMin = Math.min(xMin, d.x);
    xMax = Math.max(xMax, d.x);
    yRawMin = Math.min(yRawMin, d.y);
    yRawMax = Math.max(yRawMax, d.y);
  });

  if (xRange) {
    xMin = xRange[0];
    xMax = xRange[1];
  }

  let yMin = yRawMin;
  let yMax = yRawMax;

  // 分位数裁剪：跳过最极端的1%异常点来定Y轴范围
  if (quantileClip) {
    const sortedY = data.map(d => d.y).slice().sort((a, b) => a - b);
    const q01 = quantile(sortedY, 0.01);
    const q99 = quantile(sortedY, 0.99);
    // 只有极值远离分位数时才裁剪（保留99%的数据）
    const iqr = q99 - q01 || Math.abs(q99) * 0.1 || 1;
    const lowerFence = q01 - 1.5 * iqr;
    const upperFence = q99 + 1.5 * iqr;
    yMin = Math.max(yRawMin, lowerFence);
    yMax = Math.min(yRawMax, upperFence);
  }

  // 给两端留出5%的边距
  const yPad = (yMax - yMin) * 0.05 || Math.abs(yMax) * 0.01 || 1;
  yMin -= yPad;
  yMax += yPad;

  // 强制包含0（如果数据跨越0附近）
  if (yMin < 0 && yMax > 0) {
    // 让0轴在中间附近
  } else if (symmetric) {
    // 对称Y轴（围绕0）
    const yAbsMax = Math.max(Math.abs(yMin), Math.abs(yMax));
    yMin = -yAbsMax * 1.02;
    yMax = yAbsMax * 1.02;
  } else if (yMin >= 0) {
    yMin = 0;
  } else if (yMax <= 0) {
    yMax = 0;
  }

  const xScale = (x: number) => padding.left + ((x - xMin) / (xMax - xMin || 1)) * chartWidth;
  const yScale = (y: number) => padding.top + chartHeight - ((y - yMin) / (yMax - yMin || 1)) * chartHeight;

  // 刻度数量：X轴根据范围自适应
  const rangeX = xMax - xMin;
  let xTickCount = 6;
  if (rangeX <= 0.05) xTickCount = 5;
  else if (rangeX <= 0.15) xTickCount = 5;
  else if (rangeX >= 0.5) xTickCount = 7;

  const xTicks = Array.from({ length: xTickCount + 1 }, (_, i) => {
    const x = xMin + (i / xTickCount) * rangeX;
    return { value: x, x: xScale(x) };
  });

  const yTickCount = 5;
  const yTicks = Array.from({ length: yTickCount + 1 }, (_, i) => {
    const y = yMin + (i / yTickCount) * (yMax - yMin);
    return { value: y, y: yScale(y) };
  });

  return { xMin, xMax, yMin, yMax, xScale, yScale, xTicks, yTicks };
}

/**
 * 简化路径：数据点太多时做抽稀（Douglas-Peucker简化的简化版）
 */
function simplifyPath(points: DataPoint[], maxPoints: number): DataPoint[] {
  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  const result: DataPoint[] = [];
  for (let i = 0; i < points.length; i += step) {
    result.push(points[i]);
  }
  // 确保包含最后一个点
  if (result[result.length - 1] !== points[points.length - 1]) {
    result.push(points[points.length - 1]);
  }
  return result;
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
  symmetric = false,
  quantileClip = true,
}) => {
  const padding = { top: 35, right: 15, bottom: 50, left: 65 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const [xRange, setXRange] = useState<[number, number] | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  // 计算可用的X轴范围
  const fullRange = useMemo<[number, number] | null>(() => {
    if (data.length === 0) return null;
    let mn = Infinity, mx = -Infinity;
    data.forEach(d => {
      mn = Math.min(mn, d.x);
      mx = Math.max(mx, d.x);
    });
    return [mn, mx];
  }, [data]);

  // 找到峰值点
  const peakPoint = useMemo(() => {
    if (data.length === 0) return null;
    let idx = 0;
    for (let i = 1; i < data.length; i++) {
      if (Math.abs(data[i].y) > Math.abs(data[idx].y)) idx = i;
    }
    return data[idx];
  }, [data]);

  // 找到Y=0的点（过零点）
  const zeroCrossings = useMemo(() => {
    if (data.length < 2) return [];
    const result: DataPoint[] = [];
    for (let i = 1; i < data.length; i++) {
      if ((data[i - 1].y >= 0 && data[i].y < 0) || (data[i - 1].y <= 0 && data[i].y > 0)) {
        // 线性插值求精确过零点
        const t = Math.abs(data[i - 1].y) / (Math.abs(data[i - 1].y) + Math.abs(data[i].y));
        result.push({ x: data[i - 1].x + t * (data[i].x - data[i - 1].x), y: 0 });
      }
    }
    return result.slice(0, 10); // 最多显示10个
  }, [data]);

  // 可视化数据抽稀
  const displayData = useMemo(() => {
    if (xRange) {
      return data.filter(d => d.x >= xRange[0] && d.x <= xRange[1]);
    }
    return simplifyPath(data, Math.max(200, chartWidth * 2));
  }, [data, xRange, chartWidth]);

  const scale = useMemo(() => {
    return computeScale(displayData, padding, chartWidth, chartHeight, xRange, symmetric, quantileClip);
  }, [displayData, padding, chartWidth, chartHeight, xRange, symmetric, quantileClip]);

  // 鼠标事件处理（拖动选框缩放）
  const handleMouseDown = (e: React.MouseEvent) => {
    if (!svgRef.current || !scale) return;
    const rect = svgRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    if (px >= padding.left && px <= width - padding.right) {
      setIsDragging(true);
      setDragStart(px);
    }
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!isDragging || !svgRef.current || !scale || !dragStart || !fullRange) {
      setIsDragging(false);
      setDragStart(null);
      return;
    }
    const rect = svgRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;

    const startX = Math.min(dragStart, px);
    const endX = Math.max(dragStart, px);
    const marginPx = 5;
    if (endX - startX < marginPx) {
      setIsDragging(false);
      setDragStart(null);
      return;
    }

    // 反向映射x坐标到数据值
    const invRange: [number, number] = [
      fullRange[0] + ((startX - padding.left) / chartWidth) * (fullRange[1] - fullRange[0]),
      fullRange[0] + ((endX - padding.left) / chartWidth) * (fullRange[1] - fullRange[0]),
    ];

    // 至少保留10%的范围
    const minWidth = (fullRange[1] - fullRange[0]) * 0.1;
    if (invRange[1] - invRange[0] >= minWidth) {
      setXRange(invRange);
    }

    setIsDragging(false);
    setDragStart(null);
  };

  const resetZoom = () => setXRange(null);

  // 快捷时间窗口
  const quickZoom = (ratio: number) => {
    if (!fullRange) return;
    const center = peakPoint ? peakPoint.x : (fullRange[0] + fullRange[1]) / 2;
    const full = fullRange[1] - fullRange[0];
    const half = (full * ratio) / 2;
    setXRange([
      Math.max(fullRange[0], center - half),
      Math.min(fullRange[1], center + half),
    ]);
  };

  if (!scale) {
    return (
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="h-full flex items-center justify-center text-gray-400 text-sm">
          请运行仿真以查看结果
        </div>
      </div>
    );
  }

  const pathD = displayData.length > 1
    ? displayData
        .map((d, i) => `${i === 0 ? 'M' : 'L'} ${scale.xScale(d.x).toFixed(2)} ${scale.yScale(d.y).toFixed(2)}`)
        .join(' ')
    : '';

  const dragging = dragStart !== null && isDragging;
  const currentMouseX = isDragging && svgRef.current
    ? (() => {
        // 无法直接拿当前位置，简化处理
        return 0;
      })()
    : 0;
  void currentMouseX;

  const hasPeakOutOfView = peakPoint && xRange && (peakPoint.x < xRange[0] || peakPoint.x > xRange[1]);

  return (
    <div className="relative">
      {/* 工具栏 */}
      <div className="flex items-center justify-between mb-1 px-1">
        <div className="text-[11px] text-gray-400">
          {title && <span className="font-semibold text-gray-700">{title}</span>}
          <span className="ml-2">数据点: {data.length}</span>
          {xRange && fullRange && (
            <span className="ml-2 text-blue-500">
              显示: [{xRange[0].toFixed(3)} ~ {xRange[1].toFixed(3)}]s
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-gray-400 mr-1">缩放:</span>
          <button onClick={() => quickZoom(0.3)} className="px-1.5 py-0.5 text-[10px] bg-gray-100 hover:bg-gray-200 rounded text-gray-600">30%</button>
          <button onClick={() => quickZoom(0.5)} className="px-1.5 py-0.5 text-[10px] bg-gray-100 hover:bg-gray-200 rounded text-gray-600">50%</button>
          <button onClick={() => quickZoom(1.0)} className="px-1.5 py-0.5 text-[10px] bg-gray-100 hover:bg-gray-200 rounded text-gray-600">100%</button>
          <button onClick={resetZoom} disabled={!xRange}
            className="px-1.5 py-0.5 text-[10px] rounded bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-40 disabled:cursor-not-allowed">
            重置
          </button>
        </div>
      </div>

      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="bg-white rounded-lg border border-gray-200 cursor-crosshair select-none"
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { setIsDragging(false); setDragStart(null); }}
      >
        {/* 网格线 */}
        {scale.yTicks.map((tick, i) => (
          <line
            key={`yg-${i}`}
            x1={padding.left}
            x2={width - padding.right}
            y1={tick.y}
            y2={tick.y}
            stroke="#e5e7eb"
            strokeWidth="1"
          />
        ))}

        {/* 零线 */}
        {scale.yMin < 0 && scale.yMax > 0 && (
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={scale.yScale(0)}
            y2={scale.yScale(0)}
            stroke="#9ca3af"
            strokeWidth="1"
            strokeDasharray="4,3"
          />
        )}

        {/* 坐标轴 */}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />

        {/* Y轴刻度 */}
        {scale.yTicks.map((tick, i) => (
          <g key={`yt-${i}`}>
            <line x1={padding.left - 4} x2={padding.left} y1={tick.y} y2={tick.y} stroke="#374151" />
            <text x={padding.left - 8} y={tick.y + 4} textAnchor="end" fontSize="11" className="fill-gray-600" fontFamily="ui-monospace, monospace">
              {formatNum(tick.value)}
            </text>
          </g>
        ))}

        {/* X轴刻度 */}
        {scale.xTicks.map((tick, i) => {
          const xVal = tick.value;
          let label: string;
          if (Math.abs(xVal) < 0.01 || Math.abs(xVal) >= 100) label = xVal.toExponential(1);
          else if (scale.xMax - scale.xMin <= 0.1) label = xVal.toFixed(4);
          else if (scale.xMax - scale.xMin <= 0.5) label = xVal.toFixed(3);
          else label = xVal.toFixed(2);
          return (
            <g key={`xt-${i}`}>
              <line x1={tick.x} x2={tick.x} y1={height - padding.bottom} y2={height - padding.bottom + 4} stroke="#374151" />
              <text x={tick.x} y={height - padding.bottom + 16} textAnchor="middle" fontSize="11" className="fill-gray-600" fontFamily="ui-monospace, monospace">
                {label}
              </text>
            </g>
          );
        })}

        {/* Y轴标签 */}
        <text
          x={15} y={padding.top + chartHeight / 2} textAnchor="middle" fontSize="12" className="fill-gray-700"
          transform={`rotate(-90, 15, ${padding.top + chartHeight / 2})`}
        >
          {yLabel} {unit}
        </text>

        {/* X轴标签 */}
        <text x={padding.left + chartWidth / 2} y={height - 8} textAnchor="middle" fontSize="12" className="fill-gray-700">
          {xLabel}
        </text>

        {/* 数据曲线 —— 下面画，上面是网格背景 */}
        <path
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* 峰值点标注 */}
        {peakPoint && !hasPeakOutOfView && peakPoint.x >= (xRange?.[0] ?? -Infinity) && peakPoint.x <= (xRange?.[1] ?? Infinity) && (() => {
          const px = scale.xScale(peakPoint.x);
          const py = scale.yScale(peakPoint.y);
          const outOfYView = py < padding.top - 5 || py > height - padding.bottom + 5;
          if (outOfYView) return null;
          const textOffsetY = py - 12;
          return (
            <g>
              <circle cx={px} cy={py} r="4" fill="white" stroke={color} strokeWidth="2" />
              <text
                x={px + 6} y={textOffsetY}
                fontSize="10" fontWeight="bold"
                fill={color}
                className="select-none pointer-events-none"
                fontFamily="ui-monospace, monospace"
              >
                {formatNum(peakPoint.y)}{unit} @ {peakPoint.x.toFixed(4)}s
              </text>
            </g>
          );
        })()}

        {/* 过零点 */}
        {zeroCrossings.map((p, i) => {
          const px = scale.xScale(p.x);
          const py = scale.yScale(0);
          if (px < padding.left || px > width - padding.right) return null;
          if (py < padding.top || py > height - padding.bottom) return null;
          return <circle key={`zc-${i}`} cx={px} cy={py} r="2.5" fill="#9ca3af" />;
        })}

        {/* 拖拽选框高亮（仅视觉提示） */}
        {dragging && dragStart !== null && (
          <rect
            x={Math.min(dragStart, padding.left)}
            y={padding.top}
            width={Math.abs(padding.left - dragStart)}
            height={chartHeight}
            fill="#2563eb"
            fillOpacity="0.1"
            stroke="#2563eb"
            strokeWidth="1"
            strokeDasharray="3,3"
          />
        )}
      </svg>
    </div>
  );
};

// ============= 多线对比图 =============
interface MultiLineChartProps {
  datasets: { data: DataPoint[]; color: string; label: string }[];
  width?: number;
  height?: number;
  title?: string;
  xLabel?: string;
  yLabel?: string;
  unit?: string;
  quantileClip?: boolean;
}

export const MultiLineChart: React.FC<MultiLineChartProps> = ({
  datasets,
  width = 600,
  height = 250,
  title,
  xLabel = '时间 (s)',
  yLabel,
  unit = '',
  quantileClip = true,
}) => {
  const padding = { top: 35, right: 15, bottom: 50, left: 65 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const [xRange, setXRange] = useState<[number, number] | null>(null);

  const allPoints = useMemo(() => {
    const pts: DataPoint[] = [];
    datasets.forEach(ds => ds.data.forEach(d => pts.push(d)));
    return pts;
  }, [datasets]);

  const fullRange = useMemo<[number, number] | null>(() => {
    if (allPoints.length === 0) return null;
    let mn = Infinity, mx = -Infinity;
    allPoints.forEach(d => { mn = Math.min(mn, d.x); mx = Math.max(mx, d.x); });
    return [mn, mx];
  }, [allPoints]);

  const scale = useMemo(() => {
    if (allPoints.length === 0) return null;
    // 对所有数据集联合计算Y范围
    return computeScale(allPoints, padding, chartWidth, chartHeight, xRange, false, quantileClip);
  }, [allPoints, padding, chartWidth, chartHeight, xRange, quantileClip]);

  if (!scale || !fullRange) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">暂无数据</div>;
  }

  const paths = datasets.map(ds => {
    const visibleData = xRange
      ? ds.data.filter(d => d.x >= xRange![0] && d.x <= xRange![1])
      : simplifyPath(ds.data, Math.max(150, chartWidth));
    const pathD = visibleData.length > 1
      ? visibleData.map((d, i) => `${i === 0 ? 'M' : 'L'} ${scale.xScale(d.x).toFixed(2)} ${scale.yScale(d.y).toFixed(2)}`).join(' ')
      : '';
    return { pathD, color: ds.color, label: ds.label };
  });

  const quickZoom = (ratio: number) => {
    const center = allPoints.reduce((a, b) => (a + b.x) / 2, 0);
    const full = fullRange[1] - fullRange[0];
    const half = (full * ratio) / 2;
    setXRange([Math.max(fullRange[0], center - half), Math.min(fullRange[1], center + half)]);
  };

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-1 px-1">
        <div className="text-[11px] text-gray-400">
          {title && <span className="font-semibold text-gray-700">{title}</span>}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => quickZoom(0.5)} className="px-1.5 py-0.5 text-[10px] bg-gray-100 hover:bg-gray-200 rounded text-gray-600">50%</button>
          <button onClick={() => setXRange(null)} disabled={!xRange}
            className="px-1.5 py-0.5 text-[10px] rounded bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-40">
            重置
          </button>
        </div>
      </div>
      <svg width={width} height={height} className="bg-white rounded-lg border border-gray-200">
        {scale.yTicks.map((tick, i) => (
          <line key={`yg-${i}`} x1={padding.left} x2={width - padding.right} y1={tick.y} y2={tick.y} stroke="#e5e7eb" />
        ))}
        {scale.yMin < 0 && scale.yMax > 0 && (
          <line x1={padding.left} x2={width - padding.right} y1={scale.yScale(0)} y2={scale.yScale(0)} stroke="#9ca3af" strokeWidth="1" strokeDasharray="4,3" />
        )}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />

        {scale.yTicks.map((tick, i) => (
          <g key={`yt-${i}`}>
            <line x1={padding.left - 4} x2={padding.left} y1={tick.y} y2={tick.y} stroke="#374151" />
            <text x={padding.left - 8} y={tick.y + 4} textAnchor="end" fontSize="11" className="fill-gray-600" fontFamily="ui-monospace, monospace">
              {formatNum(tick.value)}
            </text>
          </g>
        ))}

        {scale.xTicks.map((tick, i) => {
          const xVal = tick.value;
          let label: string;
          if (scale.xMax - scale.xMin <= 0.1) label = xVal.toFixed(4);
          else label = xVal.toFixed(3);
          return (
            <g key={`xt-${i}`}>
              <line x1={tick.x} x2={tick.x} y1={height - padding.bottom} y2={height - padding.bottom + 4} stroke="#374151" />
              <text x={tick.x} y={height - padding.bottom + 16} textAnchor="middle" fontSize="11" className="fill-gray-600" fontFamily="ui-monospace, monospace">
                {label}
              </text>
            </g>
          );
        })}

        <text x={15} y={padding.top + chartHeight / 2} textAnchor="middle" fontSize="12" className="fill-gray-700"
          transform={`rotate(-90, 15, ${padding.top + chartHeight / 2})`}>
          {yLabel} {unit}
        </text>
        <text x={padding.left + chartWidth / 2} y={height - 8} textAnchor="middle" fontSize="12" className="fill-gray-700">{xLabel}</text>

        {paths.map((p, i) => (
          <path key={i} d={p.pathD} fill="none" stroke={p.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        ))}

        {/* 图例 */}
        <g transform={`translate(${padding.left + 10}, ${padding.top + 8})`}>
          {paths.map((p, i) => (
            <g key={i} transform={`translate(0, ${i * 16})`}>
              <rect width="14" height="3" fill={p.color} rx="1" />
              <text x="20" y="4" fontSize="10" className="fill-gray-600">{p.label}</text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
};
