/**
 * 起落架落震动力学 - 类型定义
 */

/** 几何参数 */
export interface GeometryParams {
  /** 支柱外径 (mm) */
  outerDiameter: number;
  /** 支柱壁厚 (mm) */
  wallThickness: number;
  /** 支柱长度 (mm) */
  strutLength: number;
  /** 轮胎半径 (mm) */
  tireRadius: number;
}

/** 工况参数 */
export interface LoadCaseParams {
  /** 着陆重量 (kg) */
  landingWeight: number;
  /** 下沉速度 (m/s) */
  sinkSpeed: number;
  /** 俯仰角 (deg) */
  pitchAngle: number;
}

/** 油气缓冲器参数 */
export interface ShockAbsorberParams {
  /** 初始气室压力 (MPa) */
  initialGasPressure: number;
  /** 气室体积 (cm³) */
  gasVolume: number;
  /** 多变指数 */
  polytropicIndex: number;
  /** 阻尼系数 (N·s/m) */
  dampingCoefficient: number;
  /** 阻尼孔面积 (mm²) */
  orificeArea: number;
}

/** 轮胎参数 */
export interface TireParams {
  /** 垂直刚度 (N/m) */
  verticalStiffness: number;
  /** 轮胎阻尼 (N·s/m) */
  damping: number;
  /** 摩擦系数 */
  frictionCoefficient: number;
}

/** 求解器设置 */
export interface SolverParams {
  /** 总仿真时长 (s) */
  totalTime: number;
  /** 时间步长 (s) */
  timeStep: number;
  /** 输出间隔 (s) */
  outputInterval: number;
}

/** 完整仿真输入参数 */
export interface SimulationParams {
  geometry: GeometryParams;
  loadCase: LoadCaseParams;
  shockAbsorber: ShockAbsorberParams;
  tire: TireParams;
  solver: SolverParams;
}

/** 时间历程单点 */
export interface TimeHistoryPoint {
  /** 时间 (s) */
  time: number;
  /** 缓冲器力 (N) */
  strutForce: number;
  /** 缓冲器压缩量 (m) */
  strutCompression: number;
  /** 机身竖向加速度 (m/s²，向下为正) */
  fuselageAcceleration: number;
  /** 轮胎垂直力 (N) */
  tireVerticalForce: number;
  /** 轮心位移 (m，向下为正) */
  wheelDisplacement: number;
  /** 机身位移 (m，向下为正) */
  fuselageDisplacement: number;
  /** 机身速度 (m/s) */
  fuselageVelocity: number;
  /** 轮心速度 (m/s) */
  wheelVelocity: number;
}

/** 仿真结果 */
export interface SimulationResult {
  /** 峰值缓冲器力 (N) */
  peakLoad: number;
  /** 峰值出现时刻 (s) */
  peakLoadTime: number;
  /** 最大压缩量 (m) */
  maxCompression: number;
  /** 最大机身加速度绝对值 (m/s²) */
  maxFuselageAcceleration: number;
  /** 求解耗时 (ms) */
  solveTime: number;
  /** 时间历程 */
  timeHistory: TimeHistoryPoint[];
  /** 本次求解使用的参数 */
  params: SimulationParams;
}
