import React from 'react';
import type { SimulationParams } from '../lib/types';

interface ParamsPanelProps {
  params: SimulationParams;
  onChange: (params: SimulationParams) => void;
  onRun: () => void;
  isRunning: boolean;
}

interface ParamInputProps {
  label: string;
  value: number;
  unit: string;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
  hint?: string;
}

const ParamInput: React.FC<ParamInputProps> = ({
  label,
  value,
  unit,
  min,
  max,
  step = 1,
  onChange,
  hint,
}) => {
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-medium text-gray-600">{label}</label>
        {hint && <span className="text-[10px] text-gray-400">{hint}</span>}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white"
        />
        <span className="text-xs text-gray-500 w-12">{unit}</span>
      </div>
    </div>
  );
};

interface SectionProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

const Section: React.FC<SectionProps> = ({ title, children, defaultOpen = true }) => {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  return (
    <div className="border border-gray-200 rounded-lg mb-3 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-sm font-semibold text-gray-700 transition-colors"
      >
        <span>{title}</span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && <div className="px-3 py-3 bg-white">{children}</div>}
    </div>
  );
};

export const ParamsPanel: React.FC<ParamsPanelProps> = ({
  params,
  onChange,
  onRun,
  isRunning,
}) => {
  const update = (path: string, value: number) => {
    const newParams = { ...params };
    const keys = path.split('.') as (keyof SimulationParams)[];
    let obj: any = newParams;
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]];
    }
    obj[keys[keys.length - 1]] = value;
    onChange(newParams);
  };

  return (
    <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 h-full overflow-y-auto">
      <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
        <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        参数配置
      </h2>

      {/* 几何参数 */}
      <Section title="📐 几何参数">
        <ParamInput
          label="支柱外径 D"
          value={params.geometry.outerDiameter}
          unit="mm"
          min={30}
          max={200}
          step={1}
          onChange={(v) => update('geometry.outerDiameter', v)}
          hint="60-120"
        />
        <ParamInput
          label="支柱壁厚 t"
          value={params.geometry.wallThickness}
          unit="mm"
          min={2}
          max={20}
          step={0.5}
          onChange={(v) => update('geometry.wallThickness', v)}
          hint="5-10"
        />
        <ParamInput
          label="支柱长度 L"
          value={params.geometry.strutLength}
          unit="mm"
          min={300}
          max={1500}
          step={10}
          onChange={(v) => update('geometry.strutLength', v)}
          hint="500-800"
        />
        <ParamInput
          label="轮胎半径"
          value={params.geometry.tireRadius}
          unit="mm"
          min={200}
          max={600}
          step={10}
          onChange={(v) => update('geometry.tireRadius', v)}
        />
      </Section>

      {/* 工况参数 */}
      <Section title="✈️ 工况参数">
        <ParamInput
          label="着陆重量"
          value={params.loadCase.landingWeight}
          unit="kg"
          min={500}
          max={50000}
          step={100}
          onChange={(v) => update('loadCase.landingWeight', v)}
          hint="小型~中型飞机"
        />
        <ParamInput
          label="下沉速度"
          value={params.loadCase.sinkSpeed}
          unit="m/s"
          min={1}
          max={8}
          step={0.1}
          onChange={(v) => update('loadCase.sinkSpeed', v)}
          hint="规范要求≥3.0"
        />
        <ParamInput
          label="俯仰角"
          value={params.loadCase.pitchAngle}
          unit="°"
          min={0}
          max={20}
          step={0.5}
          onChange={(v) => update('loadCase.pitchAngle', v)}
        />
      </Section>

      {/* 缓冲器参数 */}
      <Section title="🔧 油气缓冲器参数" defaultOpen={false}>
        <ParamInput
          label="初始气室压力"
          value={params.shockAbsorber.initialGasPressure}
          unit="MPa"
          min={0.5}
          max={10}
          step={0.1}
          onChange={(v) => update('shockAbsorber.initialGasPressure', v)}
        />
        <ParamInput
          label="气室体积"
          value={params.shockAbsorber.gasVolume}
          unit="cm³"
          min={50}
          max={500}
          step={10}
          onChange={(v) => update('shockAbsorber.gasVolume', v)}
        />
        <ParamInput
          label="多变指数"
          value={params.shockAbsorber.polytropicIndex}
          unit=""
          min={1.0}
          max={1.5}
          step={0.05}
          onChange={(v) => update('shockAbsorber.polytropicIndex', v)}
          hint="1.2-1.4"
        />
        <ParamInput
          label="阻尼系数"
          value={params.shockAbsorber.dampingCoefficient}
          unit="N·s/m"
          min={5000}
          max={50000}
          step={500}
          onChange={(v) => update('shockAbsorber.dampingCoefficient', v)}
        />
        <ParamInput
          label="阻尼孔面积"
          value={params.shockAbsorber.orificeArea}
          unit="mm²"
          min={5}
          max={100}
          step={1}
          onChange={(v) => update('shockAbsorber.orificeArea', v)}
        />
      </Section>

      {/* 轮胎参数 */}
      <Section title="🛞 轮胎参数" defaultOpen={false}>
        <ParamInput
          label="垂直刚度"
          value={params.tire.verticalStiffness}
          unit="N/m"
          min={100000}
          max={2000000}
          step={50000}
          onChange={(v) => update('tire.verticalStiffness', v)}
        />
        <ParamInput
          label="轮胎阻尼"
          value={params.tire.damping}
          unit="N·s/m"
          min={1000}
          max={20000}
          step={500}
          onChange={(v) => update('tire.damping', v)}
        />
        <ParamInput
          label="摩擦系数"
          value={params.tire.frictionCoefficient}
          unit=""
          min={0.3}
          max={0.9}
          step={0.05}
          onChange={(v) => update('tire.frictionCoefficient', v)}
        />
      </Section>

      {/* 运行按钮 */}
      <button
        onClick={onRun}
        disabled={isRunning}
        className="w-full mt-4 px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold rounded-lg hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
      >
        {isRunning ? (
          <>
            <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            求解中...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            运行动力学仿真
          </>
        )}
      </button>

      <div className="mt-3 text-xs text-gray-500 p-2 bg-blue-50 rounded border border-blue-100">
        💡 提示：本demo实现<b>路线一：系统辨识灰盒ODE</b>的核心思想，
        保留物理方程结构，毫秒级快速求解。结果仅供方案迭代，
        关键设计需回退ABAQUS全仿真复核。
      </div>
    </div>
  );
};
