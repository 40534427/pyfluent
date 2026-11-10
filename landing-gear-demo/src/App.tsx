import React, { useState, useCallback } from 'react';
import { ParamsPanel } from './components/ParamsPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { TimeSeriesChart } from './components/Charts';
import { simulateLanding, createDefaultParams } from './lib/solver';
import type { SimulationParams, SimulationResult, GeometryParams, LoadCaseParams } from './lib/types';

// 默认参数 - 典型支线客机起落架
const defaultGeom: GeometryParams = {
  outerDiameter: 80,    // mm
  wallThickness: 6,     // mm
  strutLength: 600,     // mm
  tireRadius: 400,      // mm
};

const defaultLoad: LoadCaseParams = {
  landingWeight: 15000, // kg - 约15吨
  sinkSpeed: 3.5,       // m/s - 典型下沉速度
  pitchAngle: 5,        // deg
};

const App: React.FC = () => {
  const [params, setParams] = useState<SimulationParams>(
    createDefaultParams(defaultGeom, defaultLoad)
  );
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [compareResult, setCompareResult] = useState<SimulationResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [scanResults, setScanResults] = useState<{ paramName: string; scanData: { value: number; peakLoad: number; maxCompression: number }[] } | null>(null);
  const [showScanPanel, setShowScanPanel] = useState(false);

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    setCompareResult(null);
    // 使用setTimeout让UI更新
    await new Promise(resolve => setTimeout(resolve, 50));
    
    const res = simulateLanding(params);
    setResult(res);
    setIsRunning(false);
  }, [params]);

  // 参数扫描
  const handleParamScan = useCallback(async (paramName: 'outerDiameter' | 'wallThickness' | 'strutLength' | 'sinkSpeed' | 'landingWeight') => {
    setIsRunning(true);
    await new Promise(resolve => setTimeout(resolve, 50));

    const scanData: { value: number; peakLoad: number; maxCompression: number }[] = [];
    
    let min: number, max: number, step: number;
    switch (paramName) {
      case 'outerDiameter': min = 50; max = 120; step = 7; break;
      case 'wallThickness': min = 3; max = 12; step = 1; break;
      case 'strutLength': min = 400; max = 800; step = 40; break;
      case 'sinkSpeed': min = 2.0; max = 6.0; step = 0.4; break;
      case 'landingWeight': min = 8000; max = 25000; step = 2000; break;
      default: min = 0; max = 1; step = 1;
    }

    for (let v = min; v <= max; v += step) {
      const scanParams = JSON.parse(JSON.stringify(params)) as SimulationParams;
      if (paramName === 'outerDiameter') scanParams.geometry.outerDiameter = v;
      else if (paramName === 'wallThickness') scanParams.geometry.wallThickness = v;
      else if (paramName === 'strutLength') scanParams.geometry.strutLength = v;
      else if (paramName === 'sinkSpeed') scanParams.loadCase.sinkSpeed = v;
      else if (paramName === 'landingWeight') scanParams.loadCase.landingWeight = v;

      const res = simulateLanding(scanParams);
      scanData.push({
        value: v,
        peakLoad: res.peakLoad / 1000, // kN
        maxCompression: res.maxCompression * 1000, // mm
      });
    }

    setScanResults({ paramName, scanData });
    setShowScanPanel(true);
    setIsRunning(false);
  }, [params]);

  const handleCompare = useCallback(async () => {
    if (!result) return;
    
    setIsRunning(true);
    await new Promise(resolve => setTimeout(resolve, 50));

    // 创建一个变化后的参数（支柱壁厚增加20%）用于对比
    const compareParams = JSON.parse(JSON.stringify(params)) as SimulationParams;
    compareParams.geometry.wallThickness = params.geometry.wallThickness * 1.2;
    
    const compareRes = simulateLanding(compareParams);
    setCompareResult(compareRes);
    setIsRunning(false);
  }, [params, result]);

  const resetParams = () => {
    setParams(createDefaultParams(defaultGeom, defaultLoad));
    setResult(null);
    setCompareResult(null);
    setScanResults(null);
  };

  // 参数扫描图表
  const ScanChart: React.FC = () => {
    if (!scanResults) return null;

    const { paramName, scanData } = scanResults;
    
    const paramLabels: Record<string, string> = {
      outerDiameter: '支柱外径 D (mm)',
      wallThickness: '支柱壁厚 t (mm)',
      strutLength: '支柱长度 L (mm)',
      sinkSpeed: '下沉速度 (m/s)',
      landingWeight: '着陆重量 (kg)',
    };

    const forceData = scanData.map(d => ({ x: d.value, y: d.peakLoad }));
    const dispData = scanData.map(d => ({ x: d.value, y: d.maxCompression }));

    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 mt-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">📈 参数敏感性分析 - {paramLabels[paramName]}</h3>
          <button
            onClick={() => { setShowScanPanel(false); setScanResults(null); }}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            ✕ 关闭
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TimeSeriesChart
            data={forceData}
            height={180}
            color="#2563eb"
            title="峰值缓冲器力"
            xLabel={paramLabels[paramName]}
            yLabel="峰值力"
            unit="kN"
          />
          <TimeSeriesChart
            data={dispData}
            height={180}
            color="#f97316"
            title="最大缓冲器压缩量"
            xLabel={paramLabels[paramName]}
            yLabel="压缩量"
            unit="mm"
          />
        </div>
        <div className="text-xs text-gray-500 mt-2">
          💡 参数扫描：计算效率 {scanData.length} 组工况总耗时 &lt; 1秒
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200">
      {/* 顶部导航 */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-xl flex items-center justify-center text-white shadow-md">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-800">起落架动力学快速反演 Demo</h1>
                <p className="text-xs text-gray-500">
                  ABAQUS落震动力学 → 灰盒ODE快速求解器 · 毫秒级响应
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-3 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full border border-green-200">
                路线一：系统辨识灰盒ODE
              </span>
              <button
                onClick={resetParams}
                className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              >
                重置参数
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-[1600px] mx-auto px-6 py-6">
        {/* 参数扫描快捷按钮 */}
        {result && (
          <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-semibold text-gray-700">🔍 快速参数扫描：</span>
              <button
                onClick={() => handleParamScan('outerDiameter')}
                disabled={isRunning}
                className="px-3 py-1.5 text-xs bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 disabled:opacity-50 border border-blue-200"
              >
                D (外径)
              </button>
              <button
                onClick={() => handleParamScan('wallThickness')}
                disabled={isRunning}
                className="px-3 py-1.5 text-xs bg-orange-50 text-orange-700 rounded-lg hover:bg-orange-100 disabled:opacity-50 border border-orange-200"
              >
                t (壁厚)
              </button>
              <button
                onClick={() => handleParamScan('strutLength')}
                disabled={isRunning}
                className="px-3 py-1.5 text-xs bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 disabled:opacity-50 border border-purple-200"
              >
                L (长度)
              </button>
              <button
                onClick={() => handleParamScan('sinkSpeed')}
                disabled={isRunning}
                className="px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded-lg hover:bg-green-100 disabled:opacity-50 border border-green-200"
              >
                下沉速度
              </button>
              <button
                onClick={() => handleParamScan('landingWeight')}
                disabled={isRunning}
                className="px-3 py-1.5 text-xs bg-cyan-50 text-cyan-700 rounded-lg hover:bg-cyan-100 disabled:opacity-50 border border-cyan-200"
              >
                着陆重量
              </button>
              
              <div className="ml-auto flex gap-2">
                <button
                  onClick={handleCompare}
                  disabled={isRunning}
                  className="px-3 py-1.5 text-xs bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 disabled:opacity-50 border border-indigo-200"
                >
                  对比：壁厚 +20%
                </button>
                {compareResult && (
                  <button
                    onClick={() => setCompareResult(null)}
                    className="px-3 py-1.5 text-xs bg-red-50 text-red-700 rounded-lg hover:bg-red-100 border border-red-200"
                  >
                    清除对比
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 参数扫描结果 */}
        {showScanPanel && <ScanChart />}

        {/* 主内容区 */}
        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 mt-4">
          {/* 左侧参数面板 */}
          <div className="lg:sticky lg:top-6 lg:self-start max-h-[calc(100vh-120px)] overflow-hidden">
            <ParamsPanel
              params={params}
              onChange={setParams}
              onRun={handleRun}
              isRunning={isRunning}
            />
          </div>

          {/* 右侧结果展示 */}
          <ResultsPanel result={result} compareResult={compareResult} />
        </div>

        {/* 底部信息栏 */}
        <div className="mt-6 p-4 bg-white rounded-xl border border-gray-200">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="flex gap-3">
              <div className="w-8 h-8 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="font-bold">1</span>
              </div>
              <div>
                <div className="font-semibold text-gray-700">物理可解释</div>
                <div className="text-xs text-gray-500">保留动力学微分方程结构，参数有工程含义</div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="w-8 h-8 bg-green-100 text-green-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="font-bold">2</span>
              </div>
              <div>
                <div className="font-semibold text-gray-700">极快求解速度</div>
                <div className="text-xs text-gray-500">单工况毫秒级，50组参数扫描＜1分钟</div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="w-8 h-8 bg-orange-100 text-orange-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="font-bold">3</span>
              </div>
              <div>
                <div className="font-semibold text-gray-700">可封装FMI-2.0 FMU</div>
                <div className="text-xs text-gray-500">支持Co-Simulation接入智能体系统</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 全局样式补充 */}
      <style>{`
        input[type="number"]::-webkit-inner-spin-button,
        input[type="number"]::-webkit-outer-spin-button {
          -webkit-appearance: none;
          margin: 0;
        }
        input[type="number"] {
          -moz-appearance: textfield;
        }
      `}</style>
    </div>
  );
};

export default App;
