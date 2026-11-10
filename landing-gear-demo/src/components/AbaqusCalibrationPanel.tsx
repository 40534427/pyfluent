import React, { useState, useRef, useMemo } from 'react';
import {
  parseAbaqusText,
  compareTimeSeries,
  calibrateShockAbsorber,
  applyCalibration,
  exportCSV,
  downloadFile,
  type AbaqusTimeHistory,
  type CalibrationParams,
  type CalibrationTarget,
  type CompareMetrics,
} from '../lib/abaqus';
import type { SimulationParams, SimulationResult } from '../lib/types';
import { simulateLanding } from '../lib/solver';

interface AbaqusCalibrationPanelProps {
  currentParams: SimulationParams;
  currentResult: SimulationResult | null;
  onParamsUpdate: (params: SimulationParams) => void;
  onRun: () => void;
}

type CompareKey = 'strutForce' | 'strutCompression' | 'fuselageAcceleration' | 'tireForce';

const SIGNAL_MAP: Record<CompareKey, {
  label: string;
  color: string;
  odeSeries: (ode: SimulationResult) => { t: number[]; y: number[] };
  /** 在 AbaqusTimeHistory 中优先尝试的列名 */
  abaqusCandidates: string[];
  /** 物理单位用于显示 */
  unit: string;
  /** 峰值符号：力取绝对，加速度取负峰值 */
  peakSign: '+' | '-' | 'abs';
}> = {
  strutForce: {
    label: '缓冲器力',
    color: '#2563eb',
    odeSeries: (ode) => ({
      t: ode.timeHistory.map(p => p.time),
      y: ode.timeHistory.map(p => p.strutForce),
    }),
    abaqusCandidates: ['RF2', 'RF3', 'CF2', 'CF3', 'strutForce', 'ShockForce'],
    unit: 'kN',
    peakSign: 'abs',
  },
  strutCompression: {
    label: '缓冲器压缩量',
    color: '#f97316',
    odeSeries: (ode) => ({
      t: ode.timeHistory.map(p => p.time),
      y: ode.timeHistory.map(p => p.strutCompression * 1000),
    }),
    abaqusCandidates: ['U2', 'U3', 'strut_comp', 'Compression'],
    unit: 'mm',
    peakSign: '+',
  },
  fuselageAcceleration: {
    label: '机身竖向加速度',
    color: '#9333ea',
    odeSeries: (ode) => ({
      t: ode.timeHistory.map(p => p.time),
      y: ode.timeHistory.map(p => p.fuselageAcceleration),
    }),
    abaqusCandidates: ['A2', 'A3', 'Acceleration'],
    unit: 'm/s²',
    peakSign: '-',
  },
  tireForce: {
    label: '轮胎垂直力',
    color: '#059669',
    odeSeries: (ode) => ({
      t: ode.timeHistory.map(p => p.time),
      y: ode.timeHistory.map(p => p.tireVerticalForce),
    }),
    abaqusCandidates: ['CF2', 'CF3', 'RF2', 'TireForce'],
    unit: 'kN',
    peakSign: '+',
  },
};

/**
 * 在 ABAQUS 数据中自动匹配某物理量列
 */
function autoPickColumn(
  abq: AbaqusTimeHistory,
  candidates: string[]
): { key: string; series: number[] } | null {
  // 精确匹配列名
  for (const cand of candidates) {
    if (abq.series[cand]) return { key: cand, series: abq.series[cand] };
  }
  // 模糊匹配（不区分大小写、子串）
  for (const cand of candidates) {
    for (const actual of Object.keys(abq.series)) {
      if (actual.toLowerCase() === cand.toLowerCase()) {
        return { key: actual, series: abq.series[actual] };
      }
    }
  }
  // 按物理量类型匹配
  const kind = candidates.some(c => /force|RF|CF/.test(c)) ? 'force'
    : candidates.some(c => /acc|A\d/.test(c)) ? 'acceleration'
    : candidates.some(c => /U\d|comp|disp/.test(c)) ? 'displacement'
    : 'force';
  const matched = abq.columns.find(c => c.kind === kind && c.component === 2);
  if (matched) return { key: matched.raw, series: abq.series[matched.raw] };
  // Fallback：取第一个非 time 列
  const first = abq.columns.find(c => c.kind !== 'time' && c.kind !== 'unknown');
  if (first) return { key: first.raw, series: abq.series[first.raw] };
  return null;
}

export const AbaqusCalibrationPanel: React.FC<AbaqusCalibrationPanelProps> = ({
  currentParams,
  currentResult,
  onParamsUpdate,
  onRun,
}) => {
  const [abaqusData, setAbaqusData] = useState<AbaqusTimeHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [pasteText, setPasteText] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [loadType, setLoadType] = useState<'file' | 'paste' | 'url'>('file');

  // 标定状态
  const [calibResult, setCalibResult] = useState<CalibrationParams | null>(null);
  const [calibHistory, setCalibHistory] = useState<{ iter: number; score: number }[]>([]);
  const [calibRunning, setCalibRunning] = useState(false);
  const [busy, setBusy] = useState(false);

  // 对比指标（针对不同物理量）
  const metrics: Record<CompareKey, CompareMetrics | null> = useMemo(() => {
    if (!abaqusData || !currentResult) return {
      strutForce: null, strutCompression: null, fuselageAcceleration: null, tireForce: null,
    };
    const out: Partial<Record<CompareKey, CompareMetrics>> = {};
    (Object.keys(SIGNAL_MAP) as CompareKey[]).forEach(key => {
      const cfg = SIGNAL_MAP[key];
      const picked = autoPickColumn(abaqusData, cfg.abaqusCandidates);
      if (!picked) return;
      const ode = cfg.odeSeries(currentResult);
      // 单位换算：ABAQUS 通常 N / m / m/s²，ODE 也用 SI。但压缩量ODE已转mm，这里需要统一
      let abqSeries = picked.series;
      let odeSeries = ode.y;
      if (key === 'strutCompression') {
        // 如果 ABAQUS 压缩量是 m → 转 mm；如果已经是 mm 不变
        // 启发式：若所有值都 <1 则判为 m → *1000
        const maxVal = Math.max(...abqSeries.map(Math.abs));
        if (maxVal < 0.5) abqSeries = abqSeries.map(v => v * 1000);
      }
      if (key === 'strutForce' || key === 'tireForce') {
        // 如果 ABAQUS 单位是 N（典型量级 1e3~1e6）→ 保持 N；如果是 kN → *1000
        const maxVal = Math.max(...abqSeries.map(Math.abs));
        if (maxVal < 100) abqSeries = abqSeries.map(v => v * 1000); // kN → N
        // ODE 单位统一为 N
      }
      out[key] = compareTimeSeries(
        abaqusData.time, abqSeries,
        ode.t, odeSeries,
        { peakSign: cfg.peakSign, acceptanceThreshold: 0.05 }
      );
    });
    return out as Record<CompareKey, CompareMetrics | null>;
  }, [abaqusData, currentResult]);

  const handleFile = async (file: File) => {
    setBusy(true);
    try {
      const text = await file.text();
      const data = parseAbaqusText(text, file.name);
      setAbaqusData(data);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? String(e));
      setAbaqusData(null);
    } finally {
      setBusy(false);
    }
  };

  const handleLoadPaste = () => {
    setBusy(true);
    try {
      if (!pasteText.trim()) throw new Error('粘贴框为空');
      const data = parseAbaqusText(pasteText, 'pasted.csv');
      setAbaqusData(data);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? String(e));
      setAbaqusData(null);
    } finally {
      setBusy(false);
    }
  };

  const handleLoadUrl = async () => {
    setBusy(true);
    try {
      if (!urlInput.trim()) throw new Error('请输入 URL');
      const resp = await fetch(urlInput.trim());
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      const name = urlInput.split('/').pop() || 'remote.csv';
      const data = parseAbaqusText(text, name);
      setAbaqusData(data);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? String(e));
      setAbaqusData(null);
    } finally {
      setBusy(false);
    }
  };

  const handleLoadSample = async () => {
    setBusy(true);
    try {
      const resp = await fetch('/abaqus_sample.csv');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      const data = parseAbaqusText(text, 'abaqus_sample.csv');
      setAbaqusData(data);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? String(e));
      setAbaqusData(null);
    } finally {
      setBusy(false);
    }
  };

  const handleCalibrate = () => {
    if (!abaqusData || !currentResult) return;

    const forceCfg = SIGNAL_MAP.strutForce;
    const picked = autoPickColumn(abaqusData, forceCfg.abaqusCandidates);
    if (!picked) {
      setError('ABAQUS 数据中未找到力相关列（RF2/RF3/CF2等），无法自动辨识');
      return;
    }

    // 统一到 N
    const abqForce = picked.series.map(v =>
      Math.max(...picked.series.map(Math.abs)) < 100 ? v * 1000 : v
    );
    let abqPeak = 0, abqPeakTime = 0;
    for (let i = 0; i < abqForce.length; i++) {
      if (Math.abs(abqForce[i]) > Math.abs(abqPeak)) { abqPeak = abqForce[i]; abqPeakTime = abaqusData.time[i]; }
    }
    abqPeak = Math.abs(abqPeak);

    const target: CalibrationTarget = { peakForce: abqPeak, peakTime: abqPeakTime };

    setCalibRunning(true);
    setCalibHistory([]);

    setTimeout(() => {
      const { best, history: _history } = calibrateShockAbsorber(currentParams, target, {
        iterations: 6,
        searchRange: 0.5,
        onProgress: (iter, _, score) => {
          setCalibHistory(h => [...h, { iter, score }]);
        },
      });
      setCalibResult(best);
      setCalibRunning(false);
    }, 10);
  };

  const applyCalibAndRerun = () => {
    if (!calibResult) return;
    const newParams = applyCalibration(currentParams, calibResult);
    onParamsUpdate(newParams);
    // 重新跑 ODE
    setTimeout(() => {
      simulateLanding(newParams);
      onRun();
    }, 10);
  };

  const exportOdeCSV = () => {
    if (!currentResult) return;
    const csv = exportCSV(
      currentResult.timeHistory.map(p => p.time),
      [
        { name: 'RF2', values: currentResult.timeHistory.map(p => p.strutForce) },
        { name: 'U2_wheel', values: currentResult.timeHistory.map(p => p.wheelDisplacement) },
        { name: 'A2_fuselage', values: currentResult.timeHistory.map(p => p.fuselageAcceleration) },
        { name: 'CF2_tire', values: currentResult.timeHistory.map(p => p.tireVerticalForce) },
      ]
    );
    downloadFile(csv, 'ode_time_history.csv');
  };

  const allPassed = metrics && Object.values(metrics).every(m => m === null || m.pass);

  return (
    <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 h-full overflow-y-auto">
      <h2 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
        <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
        ABAQUS 校核与参数辨识
      </h2>

      {/* Step 1: 文件导入 - 移动端友好 */}
      <div className="mb-4 p-3 bg-white rounded-lg border border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-gray-700">Step 1 · 导入 ABAQUS 结果</span>
          <button
            onClick={handleLoadSample}
            disabled={busy}
            className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 disabled:opacity-40 border border-blue-200"
          >
            📥 加载示例数据
          </button>
        </div>

        {/* 加载方式 Tab */}
        <div className="flex gap-1 mb-3 bg-gray-100 rounded-lg p-1">
          {([
            { key: 'file', label: '📱 选文件', hint: '手机/电脑存储' },
            { key: 'paste', label: '📋 粘贴', hint: 'CSV 文本' },
            { key: 'url', label: '🔗 URL', hint: '远程文件' },
          ] as const).map(t => (
            <button
              key={t.key}
              onClick={() => setLoadType(t.key)}
              className={`flex-1 py-2 text-xs font-semibold rounded-md transition-all ${
                loadType === t.key
                  ? 'bg-white text-indigo-700 shadow-sm border border-gray-200'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <div>{t.label}</div>
              <div className="text-[10px] font-normal opacity-70">{t.hint}</div>
            </button>
          ))}
        </div>

        {/* 方式 A: 文件选择 */}
        {loadType === 'file' && (
          <div className="space-y-2">
            <label
              htmlFor="abaqus-file-input"
              className="block w-full cursor-pointer"
            >
              <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center hover:border-indigo-400 hover:bg-indigo-50 active:bg-indigo-100 transition-colors">
                <svg className="w-10 h-10 mx-auto text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
                <p className="text-sm font-semibold text-gray-700">点击按钮选择文件</p>
                <p className="text-[11px] text-gray-500 mt-1">
                  支持 {'.csv / .dat / .rpt / .txt'.split(' / ').map((s, i, a) => (
                    <span key={s}>
                      <span className="inline-block px-1.5 py-0.5 bg-gray-100 rounded text-gray-600 font-mono">{s}</span>
                      {i < a.length - 1 && <span className="text-gray-300 mx-1">+</span>}
                    </span>
                  ))}
                </p>
                <p className="text-[10px] text-gray-400 mt-1">
                  手机上会弹出系统文件选择器，可从"文件/相册/下载"中选择
                </p>
              </div>
              <input
                id="abaqus-file-input"
                ref={fileRef}
                type="file"
                accept=".csv,.dat,.rpt,.txt,text/csv,text/plain"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                  // 重置 value，允许选同一个文件再次触发
                  if (e.target) e.target.value = '';
                }}
              />
            </label>
          </div>
        )}

        {/* 方式 B: 粘贴文本 */}
        {loadType === 'paste' && (
          <div className="space-y-2">
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder={"Time, U2, A2, RF2, CF2\n0.0001, 0.000, 3.50, 15000, 15000\n0.0002, 0.001, 3.48, 14980, 14960\n..."}
              rows={8}
              className="w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-gray-50"
            />
            <button
              onClick={handleLoadPaste}
              disabled={busy}
              className="w-full py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {busy ? '解析中...' : '解析粘贴内容'}
            </button>
          </div>
        )}

        {/* 方式 C: URL */}
        {loadType === 'url' && (
          <div className="space-y-2">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://example.com/abaqus_result.csv"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <button
              onClick={handleLoadUrl}
              disabled={busy}
              className="w-full py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {busy ? '加载中...' : '远程加载'}
            </button>
            <p className="text-[10px] text-gray-500">
              注意：URL 服务器需允许 CORS。同域可直接用 <code>/abaqus_sample.csv</code>。
            </p>
          </div>
        )}

        {/* 加载状态反馈 */}
        {busy && (
          <div className="mt-3 p-2 bg-indigo-50 border border-indigo-200 rounded text-xs text-indigo-700 flex items-center gap-2">
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            正在加载并解析...
          </div>
        )}

        {/* 成功状态 */}
        {abaqusData && (
          <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-green-700 font-semibold text-sm">✅ 已加载</span>
                <span className="text-xs text-green-600">{abaqusData.source}</span>
              </div>
              <button
                onClick={() => { setAbaqusData(null); setError(null); }}
                className="text-[11px] text-gray-500 hover:text-gray-700 px-2 py-0.5 rounded hover:bg-gray-200"
              >
                清除
              </button>
            </div>
            <div className="text-[11px] text-green-700">
              {abaqusData.rowCount} 行 × {Object.keys(abaqusData.series).length} 列
            </div>
            <div className="mt-1 text-[10px] text-green-600 font-mono">
              列: {Object.keys(abaqusData.series).join(', ')}
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
            ❌ {error}
          </div>
        )}

        <div className="mt-3 flex gap-2">
          <button
            onClick={exportOdeCSV}
            disabled={!currentResult}
            className="px-3 py-1.5 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-40"
          >
            📤 导出 ODE 时间历程 CSV
          </button>
          <span className="text-[10px] text-gray-400 self-center">→ 供 ABAQUS 前处理作为对比基准</span>
        </div>
      </div>

      {/* Step 2: 对比指标 */}
      {abaqusData && currentResult && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-gray-700">Step 2 · 量化误差指标</span>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-gray-500">验收阈值: 峰值相对误差 ≤ 5%</span>
              {allPassed ? (
                <span className="px-2 py-0.5 text-[11px] bg-green-100 text-green-700 rounded-full font-semibold">✓ 通过</span>
              ) : (
                <span className="px-2 py-0.5 text-[11px] bg-red-100 text-red-700 rounded-full font-semibold">✗ 需辨识</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(Object.keys(SIGNAL_MAP) as CompareKey[]).map(key => {
              const cfg = SIGNAL_MAP[key];
              const m = metrics[key];
              if (!m) return (
                <div key={key} className="p-2 bg-gray-100 rounded-lg border border-gray-200">
                  <div className="text-xs font-semibold text-gray-600">{cfg.label}</div>
                  <div className="text-[10px] text-gray-500 mt-1">ABAQUS 数据中未找到匹配列</div>
                </div>
              );
              const pass = m.pass;
              return (
                <div
                  key={key}
                  className={`p-3 rounded-lg border ${pass ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-gray-700">{cfg.label}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${pass ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}`}>
                      {pass ? '✓ PASS' : '✗ FAIL'}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] font-mono">
                    <div className="text-gray-500">ABAQUS 峰值:</div>
                    <div className="text-right text-gray-800">{formatPeak(m.abaqusPeak, cfg.unit)} @ {m.abaqusPeakTime.toFixed(4)}s</div>
                    <div className="text-gray-500">ODE 峰值:</div>
                    <div className="text-right text-gray-800">{formatPeak(m.odePeak, cfg.unit)} @ {m.odePeakTime.toFixed(4)}s</div>
                    <div className="text-gray-500">峰值误差:</div>
                    <div className={`text-right font-semibold ${Math.abs(m.peakRelativeError) <= 0.05 ? 'text-green-700' : 'text-red-700'}`}>
                      {(m.peakRelativeError * 100).toFixed(2)}%
                    </div>
                    <div className="text-gray-500">峰值时刻差:</div>
                    <div className={`text-right ${Math.abs(m.peakTimeRelativeError) <= 0.1 ? 'text-green-700' : 'text-red-700'}`}>
                      {(m.peakTimeRelativeError * 100).toFixed(1)}%
                    </div>
                    <div className="text-gray-500">NRMSE:</div>
                    <div className="text-right text-gray-800">{(m.nrmse * 100).toFixed(2)}%</div>
                    <div className="text-gray-500">Pearson R:</div>
                    <div className="text-right text-gray-800">{m.pearsonCorr.toFixed(3)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 3: 叠加对比图 */}
      {abaqusData && currentResult && (
        <div className="mb-4">
          <span className="text-sm font-semibold text-gray-700">Step 3 · 时间历程叠加对比</span>
          <div className="mt-2 space-y-3">
            {(Object.keys(SIGNAL_MAP) as CompareKey[]).map(key => {
              const cfg = SIGNAL_MAP[key];
              const picked = autoPickColumn(abaqusData, cfg.abaqusCandidates);
              if (!picked) return null;
              const ode = cfg.odeSeries(currentResult);

              // 统一单位
              let abqY = picked.series;
              if (key === 'strutCompression') {
                const maxV = Math.max(...abqY.map(Math.abs));
                if (maxV < 0.05) abqY = abqY.map(v => v * 1000);
              }
              if (key === 'strutForce' || key === 'tireForce') {
                const maxV = Math.max(...abqY.map(Math.abs));
                if (maxV < 100) abqY = abqY.map(v => v * 1000);
              }
              const abqData = abaqusData.time.map((t, i) => ({
                x: t,
                y: key === 'strutForce' || key === 'tireForce' ? abqY[i] / 1000 : abqY[i],
              }));
              const odeData = ode.t.map((t, i) => ({
                x: t,
                y: key === 'strutForce' || key === 'tireForce' ? ode.y[i] / 1000 : ode.y[i],
              }));
              const yUnit = key === 'strutForce' || key === 'tireForce' ? 'kN' : cfg.unit;

              // 合并数据的min/max确定显示范围
              const merged = [...abqData, ...odeData];
              let yMin = Infinity, yMax = -Infinity;
              merged.forEach(d => { yMin = Math.min(yMin, d.y); yMax = Math.max(yMax, d.y); });

              return (
                <div key={key} className="bg-white rounded-lg border border-gray-200 p-3">
                  <div className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-2">
                    {cfg.label}
                    <span className="text-[10px] text-gray-400 font-normal">
                      (ABAQUS 列: {picked.key}, 单位: {yUnit})
                    </span>
                  </div>
                  <CompareChart
                    odeData={odeData}
                    abqData={abqData}
                    color={cfg.color}
                    yLabel={cfg.label}
                    unit={yUnit}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 4: 自动辨识 */}
      {abaqusData && currentResult && (
        <div className="mb-4 p-3 bg-white rounded-lg border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-gray-700">Step 4 · 灰盒参数自动辨识</span>
            <button
              onClick={handleCalibrate}
              disabled={calibRunning}
              className="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-40"
            >
              {calibRunning ? '辨识中...' : '▶ 开始辨识'}
            </button>
          </div>
          <p className="text-[10px] text-gray-500 mb-2">
            以 ABAQUS 峰值力 + 峰值时刻 为目标，网格搜索 + 模式搜索优化 4 个缓冲器参数（初始气压 / 阻尼系数 / 多变指数 / 阻尼孔面积）
          </p>

          {calibHistory.length > 0 && (
            <div className="mb-2">
              <div className="text-[10px] text-gray-500 mb-1">收敛曲线 (score ↓ 越好):</div>
              <div className="flex items-end gap-1 h-16 bg-gray-50 rounded border border-gray-200 p-2">
                {calibHistory.map(h => (
                  <div key={h.iter} className="flex-1 flex flex-col items-center justify-end h-full">
                    <div
                      className="w-full bg-indigo-400 rounded-t"
                      style={{ height: `${Math.max(5, 100 - h.score * 100)}%` }}
                      title={`iter ${h.iter}: score=${h.score.toFixed(4)}`}
                    />
                    <span className="text-[8px] text-gray-400">{h.iter}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {calibResult && (
            <div className="space-y-2">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <RatioCard label="初始气压" ratio={calibResult.pressureRatio} original={currentParams.shockAbsorber.initialGasPressure} unit="MPa" />
                <RatioCard label="阻尼系数" ratio={calibResult.dampingRatio} original={currentParams.shockAbsorber.dampingCoefficient} unit="N·s/m" />
                <RatioCard label="多变指数" ratio={calibResult.polytropicRatio} original={currentParams.shockAbsorber.polytropicIndex} unit="" />
                <RatioCard label="阻尼孔面积" ratio={calibResult.orificeRatio} original={currentParams.shockAbsorber.orificeArea} unit="mm²" />
              </div>
              <button
                onClick={applyCalibAndRerun}
                className="w-full px-3 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold"
              >
                ✓ 应用辨识结果并重新运行 ODE 仿真
              </button>
            </div>
          )}
        </div>
      )}

      {!abaqusData && (
        <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="text-xs text-amber-700 font-semibold mb-1">📝 ABAQUS 前置准备</div>
          <ol className="text-[11px] text-amber-700 space-y-1 list-decimal list-inside">
            <li>在 ABAQUS/CAE 的 Step 中勾选 History Output</li>
            <li>输出 Request → Step Time + RF (支反力) + U (位移) + A (加速度)</li>
            <li>Job 完成后，.odb → .csv 导出：
              <code className="bg-white px-1 mx-1 rounded text-[10px]">odb2csv Job-1.odb -o result.csv</code>
              或在 Visualization 模块 <b>File → Export → Data</b>
            </li>
            <li>拖入本 Demo，自动列映射 + 误差计算 + 参数辨识</li>
          </ol>
        </div>
      )}
    </div>
  );
};

function formatPeak(v: number, unit: string): string {
  const abs = Math.abs(v);
  let s: string;
  if (abs >= 1e6) s = (v / 1e6).toFixed(2) + 'M';
  else if (abs >= 1e3) s = (v / 1e3).toFixed(2) + 'k';
  else if (abs >= 1) s = v.toFixed(2);
  else s = v.toExponential(2);
  return `${s} ${unit}`;
}

const RatioCard: React.FC<{ label: string; ratio: number; original: number; unit: string }> = ({ label, ratio, original, unit }) => {
  const adjusted = original * ratio;
  const ratioColor = ratio < 0.8 || ratio > 1.2 ? 'text-orange-600' : 'text-green-600';
  return (
    <div className="p-2 bg-gray-50 rounded border border-gray-200">
      <div className="text-[10px] text-gray-500">{label}</div>
      <div className="flex items-baseline gap-1">
        <span className="text-sm font-bold text-gray-800">{adjusted.toFixed(3)}</span>
        <span className="text-[10px] text-gray-400">{unit}</span>
      </div>
      <div className={`text-[10px] font-semibold ${ratioColor}`}>
        × {ratio.toFixed(3)} {ratio !== 1 ? (ratio > 1 ? '↑' : '↓') : '='}
      </div>
    </div>
  );
};

/** 简洁叠加对比图（ABAQUS 虚线，ODE 实线） */
const CompareChart: React.FC<{
  odeData: { x: number; y: number }[];
  abqData: { x: number; y: number }[];
  color: string;
  yLabel: string;
  unit: string;
}> = ({ odeData, abqData, color, yLabel, unit }) => {
  const padding = { top: 10, right: 15, bottom: 40, left: 55 };
  const width = 580;
  const height = 180;
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const { xScale, yScale, xMin, xMax, yMin, yMax } = useMemo(() => {
    const merged = [...odeData, ...abqData];
    let xMn = Infinity, xMx = -Infinity, yMn = Infinity, yMx = -Infinity;
    merged.forEach(d => {
      xMn = Math.min(xMn, d.x); xMx = Math.max(xMx, d.x);
      yMn = Math.min(yMn, d.y); yMx = Math.max(yMx, d.y);
    });
    const range = yMx - yMn || 1;
    yMn -= range * 0.05; yMx += range * 0.05;

    const xs = (x: number) => padding.left + ((x - xMn) / (xMx - xMn || 1)) * chartWidth;
    const ys = (y: number) => padding.top + chartHeight - ((y - yMn) / (yMx - yMn || 1)) * chartHeight;
    return { xScale: xs, yScale: ys, xMin: xMn, xMax: xMx, yMin: yMn, yMax: yMx };
  }, [odeData, abqData, chartWidth, chartHeight]);

  const pathFor = (data: { x: number; y: number }[]) => data
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(d.x).toFixed(2)} ${yScale(d.y).toFixed(2)}`)
    .join(' ');

  // 刻度
  const xTicks = Array.from({ length: 6 }, (_, i) => {
    const v = xMin + (i / 5) * (xMax - xMin);
    return { v, x: xScale(v) };
  });
  const yTicks = Array.from({ length: 5 }, (_, i) => {
    const v = yMin + (i / 4) * (yMax - yMin);
    return { v, y: yScale(v) };
  });

  const fmt = (n: number) => {
    const a = Math.abs(n);
    if (a >= 1e3) return (n / 1e3).toFixed(1) + 'k';
    if (a < 0.1 && a > 0) return n.toFixed(3);
    return n.toFixed(2);
  };

  return (
    <svg width={width} height={height}>
      {/* 网格 */}
      {yTicks.map((t, i) => (
        <line key={`y${i}`} x1={padding.left} x2={width - padding.right} y1={t.y} y2={t.y} stroke="#e5e7eb" />
      ))}
      {/* 轴 */}
      <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />
      <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#374151" strokeWidth="1.5" />
      {/* Y 刻度 */}
      {yTicks.map((t, i) => (
        <text key={`yt${i}`} x={padding.left - 6} y={t.y + 4} textAnchor="end" fontSize="10" className="fill-gray-600">{fmt(t.v)}</text>
      ))}
      {/* X 刻度 */}
      {xTicks.map((t, i) => (
        <text key={`xt${i}`} x={t.x} y={height - padding.bottom + 12} textAnchor="middle" fontSize="10" className="fill-gray-600">{t.v.toFixed(3)}</text>
      ))}
      {/* ABAQUS 虚线 */}
      <path d={pathFor(abqData)} fill="none" stroke="#dc2626" strokeWidth="2" strokeDasharray="4,3" />
      {/* ODE 实线 */}
      <path d={pathFor(odeData)} fill="none" stroke={color} strokeWidth="2" />
      {/* 图例 */}
      <g transform={`translate(${width - 170}, ${padding.top + 5})`}>
        <rect width="12" height="3" fill={color} />
        <text x="16" y="4" fontSize="10" className="fill-gray-700">ODE 快速</text>
        <rect x="80" width="12" height="3" fill="none" stroke="#dc2626" strokeWidth="2" strokeDasharray="3,2" />
        <text x="96" y="4" fontSize="10" className="fill-gray-700">ABAQUS</text>
      </g>
      <text x={10} y={padding.top + chartHeight / 2} textAnchor="middle" fontSize="10" className="fill-gray-600"
        transform={`rotate(-90, 10, ${padding.top + chartHeight / 2})`}>{yLabel} ({unit})</text>
    </svg>
  );
};
