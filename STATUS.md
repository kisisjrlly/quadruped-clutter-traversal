# STATUS — 第1轮迭代

日期：2026-10-04。基于远端已存在的初始化提交 `2ac953f46b8510255769ae41fbdaaed94b3a74e6`；本版本的实际SHA以Git历史/远端main读回为准。

| 项目 | 已实现/证据 | 未完成或不能声称 |
|---|---|---|
| 仿真路线 | 用户指定Isaac；选择Isaac Lab+Sim，参考v2.3.0/5.1 | 没有GPU运行/兼容性验证 |
| 文献调研 | 17项来源与对照；新增SemLoco/NVM/DTC等；核查深度逐项记录 | 非穷尽，不是17项复现 |
| 研究方案/论文协议 | v2主线、H1/H2、强基线、实验和Codex门槛 | 新颖性/有效性尚待实验 |
| 场景与几何 | 确定性动态对象manifest、SDF/capsule、弱A*、足端候选 | 没有动力学witness、真实全连杆IK/规划 |
| 感知参考 | 深度反投影、带年龄和缺测的体素记忆 | 未接actor，非NVM复现，无实测传感器模型 |
| 证据与评测 | 原始trace、逐步接触/对象最大扰动、摘要重算、unknown统计 | 接触仪器未标定，统计不自动满足独立性 |
| Isaac实现 | 动态障碍/Go2/相机/接触回调/单回合runner/外部策略契约 | 只做语法检查，没有站立/穿越成功记录 |
| 训练入口 | M1门槛检查后调用上游Go2平地训练 | 不含QCT密集障碍训练环境；未启动训练、无权重 |
| 本地测试 | 112项CPU测试通过；项目检查/语法检查通过 | 不是物理测试或真机实验 |
| CI | 添加CPU矩阵配置（Python3.10/3.13） | 本文件写入时尚无远端执行结果；不得称CI已通过 |
| 真机/论文 | 目标明确，claims仍hypothesis/unverified | 无真机部署或论文结果 |

## 当前优先级

P0：本地Isaac运行、资产/脚路径/CCD/selfcollisions/深度接口检查。P1：故意接触与时序M1实验。P2：稳定全身oracle跟踪和强基线。P3：机载感知/记忆接入与H1/H2。具体步骤见docs/CODEX_START_HERE.md。

## 验证材料

本轮记录：reports/iteration1_validation.md、reports/iteration1_unittest.log、reports/iteration1_doctor.json。启动期bootstrap记录不覆盖。raw仿真日志尚未产生；不存在“已自动在后台训练”。
