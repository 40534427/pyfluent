import React from 'react';
import type { SimulationResult } from '../lib/types';
import { TimeSeriesChart, MultiLineChart } from './Charts';

interface ResultsPanelProps {
  result: SimulationResult | null;
  compareResult?: SimulationResult | null;
}

interface StatCardProps {
  label: string;
  value: string;
  unit: string;
  icon: React.ReactNode;
  color: string;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, unit, icon, color }) => (
  <div className={`bg-white rounded-xl p-4 border border-gray-200 shadow-sm`}>
    <div className="flex items-center gap-3">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
        {icon}
      </div>
      <div>
        <div className="text-xs text-gray-500 mb-0.5">{label}</div>
        <div className="text-xl font-bold text-gray-800">
          {value} <span className="text-xs font-normal text-gray-500">{unit}</span>
        </div>
      </div>
    </div>
  </div>
);

export const ResultsPanel: React.FC<ResultsPanelProps> = ({ result, compareResult }) => {
  if (!result) {
    return (
      <div className="bg-gray-50 rounded-xl p-8 border border-gray-200 h-full flex flex-col items-center justify-center text-center">
        <svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <h3 className="text-lg font-semibold text-gray-400 mb-2">等待仿真</h3>
        <p className="text-sm text-gray-400 max-w-xs">
          在左侧面板配置起落架几何参数和工况参数，点击「运行动力学仿真」按钮开始计算
        </p>
      </div>
    );
  }

  const th = result.timeHistory;

  // 准备图表数据
  const strutForceData = th.map(p => ({ x: p.time, y: p.strutForce / 1000 })); // kN
  const displacementData = th.map(p => ({ x: p.time, y: p.strutCompression * 1000 })); // mm
  const accelData = th.map(p => ({ x: p.time, y: p.fuselageAcceleration })); // m/s²
  const tireForceData = th.map(p => ({ x: p.time, y: p.tireVerticalForce / 1000 })); // kN

  // 对比数据
  const compareStrutForceData = compareResult
    ? compareResult.timeHistory.map(p => ({ x: p.time, y: p.strutForce / 1000 }))
    : null;
  const compareDisplacementData = compareResult
    ? compareResult.timeHistory.map(p => ({ x: p.time, y: p.strutCompression * 1000 }))
    : null;

  return (
    <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 h-full overflow-y-auto">
      <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
        <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        动力学仿真结果
      </h2>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <StatCard
          label="峰值缓冲器力"
          value={(result.peakLoad / 1000).toFixed(2)}
          unit="kN"
          color="bg-blue-100 text-blue-600"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        />
        <StatCard
          label="最大压缩量"
          value={(result.maxCompression * 1000).toFixed(2)}
          unit="mm"
          color="bg-orange-100 text-orange-600"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          }
        />
        <StatCard
          label="最大机身加速度"
          value={result.maxFuselageAcceleration.toFixed(1)}
          unit="m/s²"
          color="bg-purple-100 text-purple-600"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
        />
        <StatCard
          label="求解耗时"
          value={result.solveTime.toFixed(1)}
          unit="ms"
          color="bg-green-100 text-green-600"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      {/* 对比提示 */}
      {compareResult && (
        <div className="mb-3 px-3 py-2 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-700">
          📊 当前显示对比模式：蓝色为当前参数，橙色为对比参数
          <br />
          对比峰值载荷变化：
          {compareResult.peakLoad > 0 && (
            <span className="ml-2 font-semibold">
              {((result.peakLoad - compareResult.peakLoad) / compareResult.peakLoad * 100).toFixed(1)}%
            </span>
          )}
        </div>
      )}

      {/* 图表区域 */}
      <div className="space-y-4">
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-700">① 缓冲器力 - 时间历程</h3>
            <span className="text-xs text-gray-400">核心输出指标</span>
          </div>
          {compareResult ? (
            <MultiCompareChart
              primary={strutForceData}
              compare={compareStrutForceData!}
              primaryLabel="当前参数"
              compareLabel="对比参数"
              title=""
              yLabel="缓冲器力"
              unit="kN"
            />
          ) : (
            <TimeSeriesChart
              data={strutForceData}
              height={220}
              color="#2563eb"
              yLabel="缓冲器力"
              unit="kN"
            />
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-3">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">② 缓冲器压缩量 - 时间历程</h3>
            {compareResult && compareDisplacementData ? (
              <MultiCompareChart
                primary={displacementData}
                compare={compareDisplacementData}
                primaryLabel="当前"
                compareLabel="对比"
                title=""
                yLabel="压缩量"
                unit="mm"
                height={180}
              />
            ) : (
              <TimeSeriesChart
                data={displacementData}
                height={180}
                color="#f97316"
                yLabel="压缩量"
                unit="mm"
              />
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-3">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">③ 机身加速度 - 时间历程</h3>
            <TimeSeriesChart
              data={accelData}
              height={180}
              color="#9333ea"
              yLabel="加速度"
              unit="m/s²"
              symmetric
            />
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-3">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">④ 轮胎垂直力 - 时间历程</h3>
            <TimeSeriesChart
              data={tireForceData}
              height={180}
              color="#059669"
              yLabel="轮胎力"
              unit="kN"
              quantileClip={false}
            />
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-3">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">⑤ 轮心位移 - 时间历程</h3>
            <TimeSeriesChart
              data={th.map(p => ({ x: p.time, y: p.wheelDisplacement * 1000 }))}
              height={180}
              color="#0891b2"
              yLabel="位移"
              unit="mm"
            />
          </div>
        </div>
      </div>

      {/* 物理方程说明 */}
      <div className="mt-4 p-3 bg-gray-100 rounded-lg border border-gray-200">
        <h3 className="text-xs font-semibold text-gray-600 mb-2">📐 动力学方程（2自由度灰盒ODE）</h3>
        <div className="text-xs text-gray-700 font-mono space-y-1 bg-white p-2 rounded">
          <div>M₁·ẍ₁ = -F<sub>strut</sub> - M₁·g</div>
          <div>M₂·ẍ₂ = F<sub>strut</sub> - F<sub>tire</sub> - M₂·g</div>
          <div className="text-gray-500 mt-1">
            F<sub>strut</sub> = P₀·(V₀/(V₀-A·δ))ⁿ·A + 0.5ρ·(A·δ̇/A<sub>orifice</sub>)²·C<sub>d</sub>·A + C·δ̇
          </div>
        </div>
        <p className="text-[10px] text-gray-500 mt-2">
          灰盒模型保留物理方程结构，通过参数辨识获得等效物理参数。
          求解器使用4阶Runge-Kutta积分，步长10μs，总时长350ms。
        </p>
      </div>
    </div>
  );
};

// 对比图表组件
interface MultiCompareChartProps {
  primary: { x: number; y: number }[];
  compare: { x: number; y: number }[];
  primaryLabel: string;
  compareLabel: string;
  title?: string;
  xLabel?: string;
  yLabel?: string;
  unit?: string;
  height?: number;
}

const MultiCompareChart: React.FC<MultiCompareChartProps> = ({
  primary,
  compare,
  primaryLabel,
  compareLabel,
  title,
  xLabel = '时间 (s)',
  yLabel,
  unit = '',
  height = 220,
}) => {
  return (
    <MultiLineChart
      datasets={[
        { data: primary, color: '#2563eb', label: primaryLabel },
        { data: compare, color: '#f97316', label: compareLabel },
      ]}
      height={height}
      title={title}
      xLabel={xLabel}
      yLabel={yLabel}
      unit={unit}
    />
  );
};
