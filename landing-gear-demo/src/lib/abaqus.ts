/**
 * ABAQUS 结果导入、对比校核与灰盒参数辨识
 */

import type { SimulationParams, SimulationResult } from './types';
import { simulateLanding } from './solver';

/* ------------------------------------------------------------------ */
/* 类型                                                               */
/* ------------------------------------------------------------------ */

export type ColumnKind = 'time' | 'force' | 'displacement' | 'acceleration' | 'unknown';

export interface AbaqusColumn {
  /** 原始列名 */
  raw: string;
  /** 物理量类型 */
  kind: ColumnKind;
  /** 方向分量（2 = 竖向），无则为 0 */
  component: number;
}

export interface AbaqusTimeHistory {
  /** 数据来源（文件名 / URL） */
  source: string;
  /** 列元信息 */
  columns: AbaqusColumn[];
  /** 列名 → 数值序列 */
  series: Record<string, number[]>;
  /** 时间序列 (s) */
  time: number[];
  /** 数据行数 */
  rowCount: number;
}

export interface CompareMetrics {
  /** ABAQUS 峰值（绝对值） */
  abaqusPeak: number;
  abaqusPeakTime: number;
  /** ODE 峰值（绝对值） */
  odePeak: number;
  odePeakTime: number;
  /** (ODE - ABAQUS) / ABAQUS */
  peakRelativeError: number;
  /** 峰值时刻相对偏差 */
  peakTimeRelativeError: number;
  /** 归一化均方根误差 */
  nrmse: number;
  /** 皮尔逊相关系数 */
  pearsonCorr: number;
  /** 是否通过验收 */
  pass: boolean;
}

export interface CalibrationTarget {
  /** 目标峰值力 (N) */
  peakForce: number;
  /** 目标峰值时刻 (s) */
  peakTime: number;
}

export interface CalibrationParams {
  pressureRatio: number;
  dampingRatio: number;
  polytropicRatio: number;
  orificeRatio: number;
}

export interface CalibrationOptions {
  /** 迭代轮数 */
  iterations?: number;
  /** 首轮搜索范围（相对值，0.5 表示 ±50%） */
  searchRange?: number;
  /** 进度回调 */
  onProgress?: (iter: number, params: CalibrationParams, score: number) => void;
}

export interface ExportColumn {
  name: string;
  values: number[];
}

/* ------------------------------------------------------------------ */
/* 解析                                                               */
/* ------------------------------------------------------------------ */

/** 判断单元格是否为数字 */
function isNumericCell(raw: string): boolean {
  const s = raw.trim();
  if (!s) return false;
  return /^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(s);
}

/** 识别列语义 */
export function classifyColumn(raw: string): AbaqusColumn {
  const name = raw.trim();
  const upper = name.toUpperCase();

  if (/^TIME$/i.test(name) || /^(STEP\s*)?TIME$/i.test(upper) || upper === 'T') {
    return { raw: name, kind: 'time', component: 0 };
  }

  const match = upper.match(/^([A-Z]+)\s*[_\-]?\s*(\d+)?/);
  const prefix = match ? match[1] : upper;
  const component = match && match[2] ? Number(match[2]) : 0;

  if (/^(RF|CF|SF|TF|NF|FORCE|SHOCKFORCE|TIREFORCE)/.test(prefix)) {
    return { raw: name, kind: 'force', component };
  }
  if (/^(A|ACC|ACCEL|ACCELERATION)/.test(prefix)) {
    return { raw: name, kind: 'acceleration', component };
  }
  if (/^(U|V|DISP|COMPRESSION|STRUT_COMP)/.test(prefix)) {
    return { raw: name, kind: 'displacement', component };
  }
  return { raw: name, kind: 'unknown', component };
}

/** 探测分隔符：扫描前若干行，取逗号/制表符出现最多的那种 */
function detectSeparator(lines: string[]): string {
  let commas = 0;
  let tabs = 0;
  for (const line of lines.slice(0, 30)) {
    for (const ch of line) {
      if (ch === ',') commas++;
      else if (ch === '\t') tabs++;
    }
  }
  return tabs > commas ? '\t' : ',';
}

/**
 * 解析 ABAQUS 导出的文本数据（CSV / .dat / .rpt）
 * 自动跳过元信息行、识别表头与分隔符
 */
export function parseAbaqusText(text: string, source = 'abaqus'): AbaqusTimeHistory {
  const clean = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');

  // 丢弃空行与注释行
  const lines = clean
    .split('\n')
    .map(l => l.trimEnd())
    .filter(l => l.trim().length > 0 && !/^\s*(\*|#|!)/.test(l));

  if (lines.length < 2) {
    throw new Error('数据为空或行数不足，无法解析');
  }

  const separator = detectSeparator(lines);
  const splitLine = (line: string) =>
    line.split(separator).map(c => c.trim().replace(/^"(.*)"$/, '$1'));

  // 定位表头
  let headerIndex = -1;
  for (let i = 0; i < Math.min(lines.length, 60); i++) {
    const cells = splitLine(lines[i]);
    if (cells.length >= 2 && /^time$/i.test(cells[0])) {
      headerIndex = i;
      break;
    }
  }

  let headers: string[];
  let dataStart: number;

  if (headerIndex >= 0) {
    headers = splitLine(lines[headerIndex]);
    dataStart = headerIndex + 1;
  } else {
    // 无表头：找到第一段连续 2 行以上、且各列均为数字的位置
    let probe = -1;
    for (let i = 0; i < lines.length - 1; i++) {
      const c1 = splitLine(lines[i]);
      const c2 = splitLine(lines[i + 1]);
      if (
        c1.length >= 2 && c2.length >= 2 &&
        c1.every(isNumericCell) && c2.every(isNumericCell)
      ) {
        probe = i;
        break;
      }
    }
    if (probe < 0) {
      throw new Error('未找到数值数据行，请检查文件格式');
    }
    dataStart = probe;
    headers = splitLine(lines[probe - 1] ?? '');
    const width = splitLine(lines[probe]).length;
    if (headers.length !== width || headers.some(h => isNumericCell(h))) {
      headers = Array.from({ length: width }, (_, i) => (i === 0 ? 'Time' : `Col${i + 1}`));
    }
  }

  // 收集数据行
  const rows: number[][] = [];
  for (let i = dataStart; i < lines.length; i++) {
    const cells = splitLine(lines[i]);
    if (cells.length < 2) continue;
    const values = cells.map(c => (isNumericCell(c) ? Number(c) : NaN));
    const numericCount = values.filter(v => Number.isFinite(v)).length;
    if (numericCount < 2) continue;
    rows.push(values.slice(0, headers.length));
  }

  if (rows.length === 0) {
    throw new Error('未解析到有效数值行');
  }

  // 补全缺失列名
  const width = Math.max(...rows.map(r => r.length));
  const columnNames: string[] = [];
  for (let i = 0; i < width; i++) {
    const name = headers[i] && headers[i].length > 0 ? headers[i] : `Col${i + 1}`;
    columnNames.push(columnNames.includes(name) ? `${name}_${i}` : name);
  }

  // 时间列：优先名为 Time 的列，否则第 0 列
  let timeIndex = columnNames.findIndex(n => /^time$/i.test(n));
  if (timeIndex < 0) timeIndex = 0;

  // 组装列数据
  const columns: AbaqusColumn[] = [];
  const series: Record<string, number[]> = {};
  columnNames.forEach((name, idx) => {
    const col = classifyColumn(name);
    columns.push(col.kind === 'time' && idx !== timeIndex ? { ...col, kind: 'unknown' } : col);
    series[name] = rows.map(r => (Number.isFinite(r[idx]) ? r[idx] : 0));
  });

  let time = series[columnNames[timeIndex]];

  // 时间必须单调递增，否则按时间排序
  let order: number[] | null = null;
  for (let i = 1; i < time.length; i++) {
    if (time[i] < time[i - 1]) {
      order = time.map((_, i2) => i2).sort((a, b) => time[a] - time[b]);
      break;
    }
  }
  if (order) {
    for (const key of Object.keys(series)) {
      series[key] = order.map(i => series[key][i]);
    }
    time = series[columnNames[timeIndex]];
  }

  return {
    source,
    columns,
    series,
    time,
    rowCount: rows.length,
  };
}

/* ------------------------------------------------------------------ */
/* 对比                                                               */
/* ------------------------------------------------------------------ */

/** 线性插值 */
function interpolate(xs: number[], ys: number[], x: number): number {
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];

  let lo = 0;
  let hi = xs.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  const t = (x - xs[lo]) / (xs[hi] - xs[lo] || 1);
  return ys[lo] + t * (ys[hi] - ys[lo]);
}

/** 取指定符号意义的峰值 */
function pickPeak(values: number[], times: number[], sign: '+' | '-' | 'abs') {
  let best = 0;
  let bestTime = times[0] ?? 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    const candidate = sign === '-' ? -v : Math.abs(v);
    if (candidate > best) {
      best = candidate;
      bestTime = times[i];
    }
  }
  return { value: best, time: bestTime };
}

/**
 * 对比 ABAQUS 与 ODE 时间历程
 */
export function compareTimeSeries(
  abaqusTime: number[],
  abaqusValues: number[],
  odeTime: number[],
  odeValues: number[],
  options: { peakSign?: '+' | '-' | 'abs'; acceptanceThreshold?: number } = {}
): CompareMetrics {
  const peakSign = options.peakSign ?? 'abs';
  const threshold = options.acceptanceThreshold ?? 0.05;

  if (abaqusTime.length < 2 || odeTime.length < 2) {
    throw new Error('时间序列数据不足，无法对比');
  }

  // 重叠时间区间
  const t0 = Math.max(abaqusTime[0], odeTime[0]);
  const t1 = Math.min(abaqusTime[abaqusTime.length - 1], odeTime[odeTime.length - 1]);
  if (!(t1 > t0)) {
    throw new Error('两条曲线时间区间无重叠');
  }

  // 在 ABAQUS 时间网格上重采样 ODE
  const abqX: number[] = [];
  const abqY: number[] = [];
  const odeY: number[] = [];
  for (let i = 0; i < abaqusTime.length; i++) {
    const t = abaqusTime[i];
    if (t < t0 || t > t1) continue;
    abqX.push(t);
    abqY.push(abaqusValues[i]);
    odeY.push(interpolate(odeTime, odeValues, t));
  }

  if (abqY.length < 5) {
    throw new Error('重叠区间内采样点过少（< 5），无法对比');
  }

  const abqPeak = pickPeak(abqY, abqX, peakSign);
  const odePeak = pickPeak(odeY, abqX, peakSign);

  const peakRelativeError = abqPeak.value !== 0
    ? (odePeak.value - abqPeak.value) / abqPeak.value
    : 0;
  const peakTimeRelativeError = abqPeak.time !== 0
    ? (odePeak.time - abqPeak.time) / abqPeak.time
    : 0;

  // NRMSE
  let sumSq = 0;
  let minV = Infinity;
  let maxV = -Infinity;
  for (let i = 0; i < abqY.length; i++) {
    const d = odeY[i] - abqY[i];
    sumSq += d * d;
    if (abqY[i] < minV) minV = abqY[i];
    if (abqY[i] > maxV) maxV = abqY[i];
  }
  const rmse = Math.sqrt(sumSq / abqY.length);
  const range = maxV - minV;
  const nrmse = range > 1e-12 ? rmse / range : rmse;

  // Pearson 相关
  const n = abqY.length;
  const meanA = abqY.reduce((a, b) => a + b, 0) / n;
  const meanO = odeY.reduce((a, b) => a + b, 0) / n;
  let cov = 0;
  let varA = 0;
  let varO = 0;
  for (let i = 0; i < n; i++) {
    const da = abqY[i] - meanA;
    const doo = odeY[i] - meanO;
    cov += da * doo;
    varA += da * da;
    varO += doo * doo;
  }
  const denom = Math.sqrt(varA * varO);
  const pearsonCorr = denom > 1e-12 ? cov / denom : 0;

  return {
    abaqusPeak: Math.abs(abqPeak.value),
    abaqusPeakTime: abqPeak.time,
    odePeak: Math.abs(odePeak.value),
    odePeakTime: odePeak.time,
    peakRelativeError,
    peakTimeRelativeError,
    nrmse,
    pearsonCorr,
    pass: Math.abs(peakRelativeError) <= threshold,
  };
}

/* ------------------------------------------------------------------ */
/* 参数辨识                                                           */
/* ------------------------------------------------------------------ */

/** 施加比例系数到缓冲器参数（带上下限保护） */
export function applyRatios(
  base: SimulationParams,
  ratio: CalibrationParams
): SimulationParams {
  const sa = base.shockAbsorber;
  const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

  return {
    ...base,
    shockAbsorber: {
      ...sa,
      initialGasPressure: clamp(sa.initialGasPressure * ratio.pressureRatio, 0.5, 20),
      dampingCoefficient: clamp(sa.dampingCoefficient * ratio.dampingRatio, 500, 120000),
      polytropicIndex: clamp(sa.polytropicIndex * ratio.polytropicRatio, 1.0, 1.8),
      orificeArea: clamp(sa.orificeArea * ratio.orificeRatio, 2, 200),
    },
  };
}

/** 应用辨识结果 */
export function applyCalibration(
  base: SimulationParams,
  calib: CalibrationParams
): SimulationParams {
  return applyRatios(base, calib);
}

/** 单次辨识评分：峰值误差为主，辅以峰值时刻偏差 */
function scoreParams(result: SimulationResult, target: CalibrationTarget): number {
  if (!Number.isFinite(result.peakLoad) || result.peakLoad <= 0) return 1e6;
  const peakErr = Math.abs(result.peakLoad - target.peakForce) / Math.max(target.peakForce, 1);
  const timeErr = Math.abs(result.peakLoadTime - target.peakTime) / Math.max(target.peakTime, 1e-3);
  return peakErr + 0.2 * Math.min(timeErr, 1);
}

/**
 * 灰盒参数辨识：网格 + 模式搜索
 * 依次调整 4 个无量纲比例因子，使 ODE 峰值力逼近 ABAQUS 结果
 */
export function calibrateShockAbsorber(
  base: SimulationParams,
  target: CalibrationTarget,
  options: CalibrationOptions = {}
): { best: CalibrationParams; score: number; history: { iter: number; score: number }[] } {
  const iterations = Math.max(1, options.iterations ?? 6);
  const initialRange = Math.max(0.05, options.searchRange ?? 0.5);

  // 辨识使用较粗的步长以控制耗时
  const fastParams: SimulationParams = {
    ...base,
    solver: {
      ...base.solver,
      timeStep: Math.max(base.solver.timeStep, 2e-5),
      outputInterval: Math.max(base.solver.outputInterval, 2e-4),
    },
  };

  let current: CalibrationParams = {
    pressureRatio: 1,
    dampingRatio: 1,
    polytropicRatio: 1,
    orificeRatio: 1,
  };

  const evaluate = (candidate: CalibrationParams) => {
    const result = simulateLanding(applyRatios(fastParams, candidate));
    return scoreParams(result, target);
  };

  let bestScore = evaluate(current);
  const history: { iter: number; score: number }[] = [];

  const keys: (keyof CalibrationParams)[] = [
    'pressureRatio',
    'dampingRatio',
    'polytropicRatio',
    'orificeRatio',
  ];

  for (let iter = 1; iter <= iterations; iter++) {
    const step = initialRange * Math.pow(0.5, iter - 1);

    for (const key of keys) {
      let improved = true;
      let guard = 0;
      while (improved && guard < 3) {
        improved = false;
        guard++;

        for (const direction of [1, -1]) {
          const candidate: CalibrationParams = {
            ...current,
            [key]: current[key] * (1 + direction * step),
          };
          if (candidate[key] <= 0.05) continue;

          const score = evaluate(candidate);
          if (score < bestScore - 1e-9) {
            bestScore = score;
            current = candidate;
            improved = true;
            break;
          }
        }
      }
    }

    history.push({ iter, score: bestScore });
    options.onProgress?.(iter, current, bestScore);
  }

  return { best: current, score: bestScore, history };
}

/* ------------------------------------------------------------------ */
/* 导出                                                               */
/* ------------------------------------------------------------------ */

/** 生成 CSV 文本 */
export function exportCSV(times: number[], columns: ExportColumn[]): string {
  const header = ['Time', ...columns.map(c => c.name)].join(',');
  const lines = [header];

  const rowCount = Math.min(times.length, ...columns.map(c => c.values.length));
  for (let i = 0; i < rowCount; i++) {
    const cells = [times[i].toPrecision(8), ...columns.map(c => c.values[i].toPrecision(8))];
    lines.push(cells.join(','));
  }
  return lines.join('\n');
}

/** 触发浏览器下载 */
export function downloadFile(content: string, filename: string): void {
  const blob = new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/** 将 ODE 结果转为 ABAQUS 可导入的 CSV 文本 */
export function odeToAbaqusFormat(result: SimulationResult): string {
  return exportCSV(
    result.timeHistory.map(p => p.time),
    [
      { name: 'U2_wheel', values: result.timeHistory.map(p => p.wheelDisplacement) },
      { name: 'A2_fuselage', values: result.timeHistory.map(p => p.fuselageAcceleration) },
      { name: 'RF2', values: result.timeHistory.map(p => p.strutForce) },
      { name: 'CF2_tire', values: result.timeHistory.map(p => p.tireVerticalForce) },
    ]
  );
}
