#!/usr/bin/env python3
"""Generate params.json with Chinese annotations (design defaults + inversion)."""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
inv = json.load(open(os.path.join(HERE, "inversion_report.json")))

# docx design values (Table 1 / Table 2 of 计算输入参数.docx)
P = 97500.0          # Pa (97.5 kPa)
rho_a = 1.188        # kg/m3
vy = 220.0
gamma = 1.4
Rgas = 287.05
T0 = P / (rho_a * Rgas)
c0 = math.sqrt(gamma * P / rho_a)
e0 = P / (gamma - 1.0)


def leaf(value, unit, note, editable=True, extra=None):
    d = {"值": value, "单位": unit, "说明": note, "可调": editable}
    if extra:
        d.update(extra)
    return d


params = {
    "_文件说明": {
        "用途": "减速伞 ALE 流固耦合仿真参数文件；由 make_kfile.exe 读取并生成新的 LS-DYNA .k 输入文件",
        "编码": "UTF-8 JSON；修改“值”后重新运行 make_kfile.exe 即可",
        "单位制": "kg-m-s（与原 K 文件一致）",
        "参数来源": "伞衣/伞绳/来流默认值来自《计算输入参数.docx》；流域/卡片参数从原 Parachute_0903.k 反演得到",
    },

    "canopy": {
        "_分组说明": "伞衣（织物膜）几何与材料 —— 《计算输入参数》表1",
        "n_gores": leaf(16, "", "伞衣幅数（拓扑计数；随模板网格固定，修改需要重新生成网格）", False),
        "n_weft_bands": leaf(10, "", "纬向带条数（折叠褶皱横向加强带数量；模板网格固定）", False),
        "cone_angle_deg": leaf(
            25.0, "°", "伞衣锥角（半锥角基准按模板反演外轮廓角 %.2f°；按 tan 比例对初始折叠半径做缩放）"
            % inv["folded_envelope_full_cone_angle_deg"]),
        "fabric_thickness": leaf(0.001, "m", "伞衣（膜）厚度 = 1 mm，写入 *SECTION_SHELL 的 t1~t4"),
        "fabric_density": leaf(800.0, "kg/m3", "伞衣织物密度，写入 *MAT_FABRIC 的 RO"),
        "fabric_E": leaf(5.0e8, "Pa", "伞衣经向弹性模量 EA，写入 *MAT_FABRIC"),
        "fabric_nu": leaf(0.15, "", "伞衣泊松比 PRBA"),
        "fabric_EB": leaf(0.0, "Pa", "伞衣纬向弹性模量 EB（0=仅经向承力；运行时自动加 0.001·EA 稳定项）"),
        "eb_fraction": leaf(0.05, "", "运行时纬向模量比 EB/EA（T5J 设置；由 run_parachute.exe 的 --eb-frac 生效）"),
        "tension_only_membrane": leaf(True, "", "是否为仅受拉膜（松弛纤维方向不承力；--tension-only-membrane）"),
    },

    "suspension_lines": {
        "_分组说明": "伞绳几何与材料 —— 《计算输入参数》表1",
        "n_lines": leaf(16, "", "伞绳根数（=幅数；模板固定16根）", False),
        "line_segments": leaf(10, "段", "每根伞绳的梁单元分段数（模板固定10段）", False),
        "line_length": leaf(1.500, "m", "伞绳长度 = 1500 mm（对伞绳链节点坐标做参数化缩放）"),
        "line_density": leaf(1200.0, "kg/m3", "伞绳密度，写入 *MAT_PLASTIC_KINEMATIC 的 RO"),
        "line_E": leaf(2.0e9, "Pa", "伞绳弹性模量 E"),
        "line_nu": leaf(0.35, "", "伞绳泊松比（原 K 反演值）"),
        "line_yield": leaf(1.0e9, "Pa", "伞绳屈服应力 SIGY"),
        "line_area": leaf(5.0e-5, "m2", "伞绳截面积；*SECTION_BEAM 按等效正方形边长 ts=tt=sqrt(A) 写入"),
    },

    "inflow_air": {
        "_分组说明": "来流条件与空气物性 —— 《计算输入参数》表2（理想气体）",
        "Vx": leaf(0.0, "m/s", "来流 x 向速度（模型轴向为 y，一般为0）"),
        "Vy": leaf(220.0, "m/s", "来流 y 向速度（轴向来流）；同时写入速度曲线与恒定来流运行参数"),
        "Vz": leaf(0.0, "m/s", "来流 z 向速度（一般为0）"),
        "air_density": leaf(rho_a, "kg/m3", "空气密度 ρ，写入 *MAT_NULL RO"),
        "ambient_pressure": leaf(P, "Pa", "环境压力 P = 97.5 kPa；作为 EOS 初压与 CONTROL_ALE 参考压力 PREF"),
        "gamma": leaf(gamma, "", "比热比 γ（EOS_LINEAR_POLYNOMIAL：p=(γ-1)ρe，c4=c5=γ-1=0.4）", False),
        "R_specific": leaf(Rgas, "J/(kg·K)", "空气比气体常数（用于由 P、ρ 反算温度）", False),
        "air_mu": leaf(1.0e-3, "Pa·s", "空气动力粘度（*MAT_NULL 的 MU，近似值）"),
        "air_pc": leaf(-1.0e-3, "", "*MAT_NULL 压力截断 PC"),
        "_派生量": {
            "环境温度_T": leaf(round(T0, 2), "K", "T = P/(ρR) 自动计算", False),
            "声速_c0": leaf(round(c0, 2), "m/s", "c0 = sqrt(γP/ρ) 自动计算", False),
            "来流马赫数": leaf(round(vy / c0, 4), "", "Ma = Vy/c0 自动计算", False),
            "EOS初始内能_e0": leaf(round(e0, 1), "J/kg", "e0 = P/(γ-1) = P/0.4 自动计算", False),
        },
    },

    "velocity_curve": {
        "_分组说明": "*DEFINE_CURVE 11 来流速度-时间表（纵轴为速度倍率/速度，单位 s,m/s）",
        "lcid": leaf(11, "", "曲线 ID（BOUNDARY_PRESCRIBED_MOTION_SET 引用）", False),
        "ramp_time": leaf(0.040, "s", "速度线性爬升到 Vy 的时间（0.04 s 内升至 220 m/s）"),
        "hold_end": leaf(0.080, "s", "恒速段结束时间点（曲线表用）"),
        "table_end_time": leaf(3.0, "s", "曲线表末点时间"),
        "use_constant_velocity_at_runtime": leaf(
            True, "", "运行 run_parachute.exe 时用 --constant-vel Vy 直接恒速（忽略曲线爬升，T5J 做法）"),
    },

    "fluid_domain_in_k": {
        "_分组说明": "K 文件内置 ALE 流体域（结构化正六面体盒，包围圆柱；求解器 auto 网格仅用其范围）",
        "y0": leaf(round(inv["fluid_y0"], 5), "m", "流体域上游（入口）y 坐标（反演值）"),
        "y1_native": leaf(round(inv["fluid_y1"], 5), "m", "K 内置流体域下游 y 坐标（反演值）"),
        "R_native": leaf(round(inv["fluid_R"], 5), "m", "K 内置流体域半径（反演值，外接正方形盒半宽）"),
        "cx": leaf(0.0, "m", "流域 x 向中心（反演≈-1e-4，规整为0）"),
        "cz": leaf(0.0, "m", "流域 z 向中心"),
        "box_nx": leaf(20, "", "生成用结构化盒网格 x 向单元数（auto 模式不参与求解，仅定义范围/入口/无反射面）"),
        "box_ny": leaf(40, "", "生成用结构化盒网格 y 向单元数"),
        "box_nz": leaf(20, "", "生成用结构化盒网格 z 向单元数"),
    },

    "solver_cards_in_k": {
        "_分组说明": "写入新 K 文件的 LS-DYNA 控制卡参数",
        "title": leaf("Parametric Parachute  CHUTE  kg-m-s", "", "*TITLE 标题行"),
        "endtim": leaf(0.050, "s", "*CONTROL_TERMINATION 计算终止时间"),
        "tssfac": leaf(0.8, "", "*CONTROL_TIMESTEP 时间步缩放因子 TSSFAC"),
        "bulk_q1": leaf(1.5, "", "*CONTROL_BULK_VISCOSITY 二次体黏 Q1"),
        "bulk_q2": leaf(0.06, "", "线性体黏 Q2"),
        "hg_ihq": leaf(1, "", "*CONTROL_HOURGLASS IHQ 沙漏类型"),
        "hg_qh": leaf(0.1, "", "沙漏系数 QH（同时用于膜四边形）"),
        "shell_theory": leaf(5, "", "*CONTROL_SHELL THEORY 壳公式（5=Belytschko-Tsay）"),
        "shell_bwc": leaf(2, "", "BWC 翘曲控制"),
        "shell_wrpang": leaf(20.0, "°", "壳单元翘曲角阈值"),
        "clis_nquad": leaf(2, "", "CONSTRAINED_LAGRANGE_IN_SOLID 耦合点数 NQUAD"),
        "clis_ctype": leaf(11, "", "耦合类型 CTYPE（罚函数）"),
        "clis_direc": leaf(2, "", "耦合方向 DIREC（仅法向压缩）"),
        "clis_pfac": leaf(0.1, "", "罚刚度系数 PFAC"),
        "clis_ileak": leaf(2, "", "泄漏控制类型 ILEAK（2=启用）"),
        "clis_pleak": leaf(0.1, "", "泄漏系数 PLEAK"),
        "clis_frcmin": leaf(0.3, "", "最小激活体积比 FRCMIN"),
        "contact_enabled_in_k": leaf(True, "", "是否把 *CONTACT_AUTOMATIC_SINGLE_SURFACE 卡写入 K（T5J 运行时由 --no-contact 关闭）"),
    },

    "solver_run_settings": {
        "_分组说明": "run_parachute.exe（求解器）命令行调控参数 —— 由随包 run_solver.bat 自动使用",
        "mesh_mode": leaf("auto", "auto/native", "流体网格模式：auto=按流域参数自动建笛卡尔网格（推荐）"),
        "nx": leaf(30, "", "auto 流体网格 x 向单元数"),
        "ny": leaf(40, "", "auto 流体网格 y 向单元数"),
        "nz": leaf(30, "", "auto 流体网格 z 向单元数"),
        "domain_radius": leaf(0.5, "m", "运行时流域半径（扩大到0.5m消除伞衣阻塞；0=用K内置半径）"),
        "y1_extension": leaf(0.4, "m", "运行时下游流域延长量（尾流发展空间）"),
        "cfl": leaf(0.5, "", "流体 CFL 稳定系数"),
        "omega": leaf(0.2, "", "FSI 罚耦合欠松弛系数"),
        "cdamp": leaf(1.0, "", "FSI 声阻抗阻尼系数"),
        "fsi_mach_cap": leaf(0.3, "", "注入流场速度增量的马赫数上限"),
        "vent_radius": leaf(0.04, "m", "顶部通气孔加强环半径（0=关闭）"),
        "bend_scale": leaf(1, "", "边铰弯曲刚度放大（1=物理弯曲刚度）"),
        "bend_damp": leaf(0, "", "弯曲铰粘性阻尼比"),
        "struct_damping": leaf(100, "1/s", "结构质量比例阻尼"),
        "struct_damping_vmax": leaf(30, "m/s", "智能阻尼门限：节点速度高于此值阻尼关闭、低于60%全开（0=恒阻尼）"),
        "contact_enabled": leaf(False, "", "运行时是否启用伞衣自接触（T5J 关闭以加速）"),
        "vtk_every": leaf(0.005, "s", "VTK 中间状态输出间隔（0=只输出最终态）"),
        "endtime": leaf(0.050, "s", "运行终止时间（命令行 --endtime）"),
        "generate_report": leaf(True, "", "算完自动生成 HTML 计算报告（--generate-report）"),
    },

    "output": {
        "_分组说明": "生成器输出设置",
        "output_k_filename": leaf("Parachute_generated.k", "", "生成的 K 文件名（与 Parachute_0903.k 同格式，可直接给求解器计算）"),
        "results_dirname": leaf("results", "", "求解结果输出目录名"),
    },

    "_inversion_reference": {
        "_说明": "从原 Parachute_0903.k 反演得到的只读基线值，供核对；几何缩放以此为基准",
        "伞衣节点数": inv["canopy_nodes"],
        "伞衣四边形数": inv["shell_quads"],
        "伞绳梁单元数": inv["beams"],
        "伞绳链+方向节点数": inv["beam_only_nodes"],
        "伞衣顶环半径_m": round(inv["apex_ring_radius"], 5),
        "伞裙连接点半径_m": round(inv["skirt_attach_radius"], 5),
        "伞裙连接点y_m": round(inv["skirt_attach_y"], 5),
        "反演伞绳长度_m": round(inv["line_length_m"], 4),
        "折叠外轮廓全锥角_deg": round(inv["folded_envelope_full_cone_angle_deg"], 2),
        "K内置流域": {"y0": round(inv["fluid_y0"], 5), "y1": round(inv["fluid_y1"], 5),
                  "R": round(inv["fluid_R"], 5)},
    },
}

with open(os.path.join(HERE, "params.json"), "w", encoding="utf-8") as fh:
    json.dump(params, fh, ensure_ascii=False, indent=2)
print("params.json written:", os.path.getsize(os.path.join(HERE, "params.json")), "bytes")
