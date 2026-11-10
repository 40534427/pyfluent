/**
 * 起落架落震动力学 - 2自由度灰盒 ODE 求解器
 *
 * 模型：
 *   M1·ẍ1 = M1·g - F_strut
 *   M2·ẍ2 = M2·g + F_strut - F_tire
 *
 *   δ  = x1 - x2            （缓冲器压缩量）
 *   F_strut = F_gas + F_damp
 *     F_gas  = P0·(V0/(V0 - A_p·δ))^n · A_p
 *     F_damp = C·δ̇ + 0.5·ρ·Cd·(A_p²/A_o²)·δ̇·|δ̇| · A_p
 *   F_tire = k_t·δ_t + c_t·δ̇_t   （δ_t > 0 时）
 *
 * 积分器：四阶 Runge-Kutta，固定步长
 */

import type {
  SimulationParams,
  SimulationResult,
  TimeHistoryPoint,
  GeometryParams,
  LoadCaseParams,
} from './types';

const G = 9.81;            // 重力加速度 (m/s²)
const RHO_OIL = 850;       // 液压油密度 (kg/m³)
const CD_ORIFICE = 0.7;    // 阻尼孔流量系数

/** 单点状态向量：[x1, v1, x2, v2] */
type StateVector = [number, number, number, number];

interface DerivedModel {
  m1: number;         // 弹性支撑质量 (kg)
  m2: number;         // 非弹性支撑质量 (kg)
  pistonArea: number; // 活塞有效面积 (m²)
  gasPressure: number;// 初始气压 (Pa)
  gasVolume: number;  // 初始气室体积 (m³)
  polytropic: number; // 多变指数
  damping: number;    // 线性阻尼系数 (N·s/m)
  orificeArea: number;// 阻尼孔面积 (m²)
  tireK: number;      // 轮胎刚度 (N/m)
  tireC: number;      // 轮胎阻尼 (N·s/m)
  strokeMax: number;  // 最大行程 (m)
}

/** 由原始参数推导计算所用的物理量 */
function deriveModel(p: SimulationParams): DerivedModel {
  const totalMass = Math.max(p.loadCase.landingWeight, 1);

  // 单个主起落架承担约 45% 的着陆重量，其中 3% 为轮组非弹性质量
  const m1 = totalMass * 0.45;
  const m2 = totalMass * 0.03;

  // 活塞有效面积：由内径（外径 - 2×壁厚）确定
  const innerDiameter = Math.max(
    p.geometry.outerDiameter - 2 * p.geometry.wallThickness,
    5
  );
  const pistonArea = Math.PI / 4 * Math.pow(innerDiameter / 1000, 2);

  return {
    m1,
    m2,
    pistonArea,
    gasPressure: p.shockAbsorber.initialGasPressure * 1e6,
    gasVolume: p.shockAbsorber.gasVolume * 1e-6,
    polytropic: Math.max(1.0, p.shockAbsorber.polytropicIndex),
    damping: p.shockAbsorber.dampingCoefficient,
    orificeArea: Math.max(p.shockAbsorber.orificeArea * 1e-6, 1e-8),
    tireK: p.tire.verticalStiffness,
    tireC: p.tire.damping,
    // 行程上限取支柱长度的一半
    strokeMax: Math.max(p.geometry.strutLength * 0.5 / 1000, 0.02),
  };
}

/** 缓冲器力 (N) */
function strutForce(delta: number, deltaRate: number, m: DerivedModel): number {
  const d = Math.max(delta, 0);
  const dr = deltaRate;

  let force = 0;

  // 气弹簧力：绝热压缩，气室体积不允许小于初始体积的 2%
  if (d > 0) {
    const volume = Math.max(m.gasVolume - m.pistonArea * d, m.gasVolume * 0.02);
    const ratio = m.gasVolume / volume;
    force += m.gasPressure * Math.pow(ratio, m.polytropic) * m.pistonArea;
  }

  // 阻尼力：仅在缓冲器实际被压缩时产生（δ > 0），回弹阶段阻尼较弱
  if (d > 0 && dr > 0) {
    force += m.damping * dr;
    force += 0.5 * RHO_OIL * CD_ORIFICE *
      Math.pow(m.pistonArea / m.orificeArea, 2) *
      m.pistonArea * dr * dr;
  } else if (d > 0 && dr < 0) {
    force += m.damping * 0.5 * dr;
    force -= 0.5 * RHO_OIL * CD_ORIFICE * 0.5 *
      Math.pow(m.pistonArea / m.orificeArea, 2) *
      m.pistonArea * dr * dr;
  }

  // 行程末端缓冲（触底）
  if (d > m.strokeMax) {
    force += 5e7 * (d - m.strokeMax);
  }

  return Math.max(force, 0);
}

/** 轮胎力 (N)：地面位于 x = 0，轮心向下的位移即轮胎压缩量 */
function tireForce(x2: number, v2: number, m: DerivedModel): number {
  if (x2 <= 0) return 0;
  const compression = x2;
  const rate = Math.max(v2, 0);
  return Math.max(m.tireK * compression + m.tireC * rate, 0);
}

/** 状态导数 */
function derivatives(s: StateVector, m: DerivedModel): StateVector {
  const [, v1, x2, v2] = s;
  const delta = s[0] - x2;
  const deltaRate = v1 - v2;

  const fStrut = strutForce(delta, deltaRate, m);
  const fTire = tireForce(x2, v2, m);

  // 向下为正
  const a1 = G - fStrut / m.m1;
  const a2 = G + fStrut / m.m2 - fTire / m.m2;

  return [v1, a1, v2, a2];
}

/** 四阶 Runge-Kutta 单步 */
function rk4(s: StateVector, dt: number, m: DerivedModel): StateVector {
  const k1 = derivatives(s, m);

  const s2: StateVector = [
    s[0] + 0.5 * dt * k1[0], s[1] + 0.5 * dt * k1[1],
    s[2] + 0.5 * dt * k1[2], s[3] + 0.5 * dt * k1[3],
  ];
  const k2 = derivatives(s2, m);

  const s3: StateVector = [
    s[0] + 0.5 * dt * k2[0], s[1] + 0.5 * dt * k2[1],
    s[2] + 0.5 * dt * k2[2], s[3] + 0.5 * dt * k2[3],
  ];
  const k3 = derivatives(s3, m);

  const s4: StateVector = [
    s[0] + dt * k3[0], s[1] + dt * k3[1],
    s[2] + dt * k3[2], s[3] + dt * k3[3],
  ];
  const k4 = derivatives(s4, m);

  return [
    s[0] + dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
    s[1] + dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
    s[2] + dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]),
    s[3] + dt / 6 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3]),
  ];
}

/** 默认参数生成 */
export function createDefaultParams(
  geometry: GeometryParams,
  loadCase: LoadCaseParams
): SimulationParams {
  return {
    geometry: { ...geometry },
    loadCase: { ...loadCase },
    shockAbsorber: {
      initialGasPressure: 6.0,   // MPa
      gasVolume: 420,            // cm³
      polytropicIndex: 1.3,
      dampingCoefficient: 16000, // N·s/m
      orificeArea: 60,           // mm²
    },
    tire: {
      verticalStiffness: 900000, // N/m
      damping: 6000,             // N·s/m
      frictionCoefficient: 0.6,
    },
    solver: {
      totalTime: 0.35,           // s
      timeStep: 1e-5,            // 10 μs
      outputInterval: 1e-4,      // 100 μs
    },
  };
}

/** 运行仿真 */
export function simulateLanding(params: SimulationParams): SimulationResult {
  const started = typeof performance !== 'undefined' ? performance.now() : Date.now();

  const model = deriveModel(params);
  const dt = Math.max(params.solver.timeStep, 1e-7);
  const totalTime = Math.max(params.solver.totalTime, 10 * dt);
  const outputInterval = Math.max(params.solver.outputInterval, dt);

  // 初始条件：轮心刚触地（2mm 预压缩），机身以沉降速度下压，轮心初始速度取 0
  const tirePreCompression = 0.002;
  let state: StateVector = [0, params.loadCase.sinkSpeed, tirePreCompression, 0];

  const timeHistory: TimeHistoryPoint[] = [];
  let peakLoad = 0;
  let peakLoadTime = 0;
  let maxCompression = 0;
  let maxAccel = 0;

  const totalSteps = Math.min(Math.floor(totalTime / dt), 2_000_000);
  let nextOutput = 0;

  const record = (time: number) => {
    const [x1, v1, x2, v2] = state;
    const delta = Math.max(x1 - x2, 0);
    const fStrut = strutForce(x1 - x2, v1 - v2, model);
    const fTire = tireForce(x2, v2, model);
    const accel = G - fStrut / model.m1;

    timeHistory.push({
      time,
      strutForce: fStrut,
      strutCompression: delta,
      fuselageAcceleration: accel,
      tireVerticalForce: fTire,
      wheelDisplacement: x2,
      fuselageDisplacement: x1,
      fuselageVelocity: v1,
      wheelVelocity: v2,
    });

    if (fStrut > peakLoad) {
      peakLoad = fStrut;
      peakLoadTime = time;
    }
    if (delta > maxCompression) maxCompression = delta;
    if (Math.abs(accel) > maxAccel) maxAccel = Math.abs(accel);
  };

  record(0);

  for (let step = 1; step <= totalSteps; step++) {
    state = rk4(state, dt, model);
    const time = step * dt;

    // 数值保护
    if (!Number.isFinite(state[0]) || !Number.isFinite(state[1])) break;

    if (time >= nextOutput - 1e-12) {
      record(time);
      nextOutput += outputInterval;
    }
  }

  const finished = typeof performance !== 'undefined' ? performance.now() : Date.now();

  return {
    peakLoad,
    peakLoadTime,
    maxCompression,
    maxFuselageAcceleration: maxAccel,
    solveTime: finished - started,
    timeHistory,
    params,
  };
}
