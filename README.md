# Quadruped Clutter Traversal
## 密集易扰动障碍环境中的四足机器人精细穿越

目标：仅依靠机载感知，协调身体和四条腿，在狭窄通道内穿过随机混合的细杆、立木条、低块和瓶罐，尽量不接触、不扰动物品，最终形成有强基线与真机证据的论文。

**当前：第1轮研究/工程迭代；112项CPU测试通过。Isaac Lab/Isaac Sim接口已编写但尚未运行验证；没有训练权重、全身自主穿越结果或真机结果。** 数值路径、相机录制和软件测试不等于实现最终能力。完整状态见 [STATUS](STATUS.md)。

仓库为用户明确授权的独立公开 `kisisjrlly/quadruped-clutter-traversal`，直接维护main；不fork、不向上游发PR、不force push。原始启动提交保留在历史。狗参考截图未上传，单帧不证明完整成功或动物内部认知机制。

## 研究与开发入口

| 文档 | 内容 |
|---|---|
| [17项相关工作](docs/RELATED_WORK.md) | SemLoco、NVM、DTC、全身规划等强先例与差距，不预设首次 |
| [研究方案v2](docs/RESEARCH_PLAN_V2.md) | 最终能力、形式化问题、候选机制、接口和M0–M5门槛 |
| [Isaac Lab实施](docs/ISAACLAB.md) | 固定参考版本、动态对象、接触、相机、运行/训练入口及限制 |
| [实验协议v2](docs/EXPERIMENTS_V2.md) | 强基线、消融、数据权限、unknown、统计与真机门槛 |
| [本地Codex入口](docs/CODEX_START_HERE.md) | 下一步具体实施和必须完成的物理验收 |
| [来源账本](references/verified_sources.json) | 17项论文的原始来源、核查深度、未复现状态 |
| [验证报告](reports/iteration1_validation.md) | 实际执行命令、CPU结果、未执行的Isaac/真机部分 |

## 已有代码

`qct.scene`：可重建场景和hash；`geometry/planning`：原始体距离、保守capsule界、机身A*、落足/足端摆动候选；`perception`：光学深度反投影及带时效的CPU局部体素记忆；`contacts/recording`：接触归因、逐步原始证据和摘要重算；`statistics`：分轨道批量统计，unknown保留分母。

`qct.sim`：Isaac单环境动态场景/Go2参考资产/PhysX接触/可选深度录制；`stand`为站立诊断，`policy-route`需另行提供契约一致的速度策略。全部当前Isaac模式为oracle；感知记忆尚未接入actor，全连杆FK/IK与稳定跟踪仍需补齐。

## CPU运行

核心只依赖Python标准库，Python>=3.10。本轮实际本地版本3.13.5。

```bash
python -m unittest discover -s tests -v
python scripts/check_project.py
python -m qct.workflow doctor
python -m qct.workflow scene --seed 0 --split calibration --count 0 --output runs/empty.json
python -m qct.workflow plan runs/empty.json
python -m qct evaluate examples/synthetic_episode_success.json --config configs/benchmark_v0_1.json
```

人工fixture不是仿真轨迹。生成布局的可行性仍标unknown；A*无路不证明四足无法跨过。新文件/输出目录拒绝覆盖已有实验。

## Isaac运行

接口参考Isaac Lab v2.3.0与Isaac Sim5.1，不声称最新；实际版本需审核。Go2只是仿真参考，不认定用户已有对应真机。

```bash
export ISAACLAB_PATH=/path/to/IsaacLab
"$ISAACLAB_PATH/isaaclab.sh" -p scripts/run_isaaclab.py \
  --scene runs/empty.json --output runs/empty_stand --mode stand --duration 5
```

有深度录制需求时加`--enable_cameras`。先按[实施文档](docs/ISAACLAB.md)审核实际足碰撞体、self-collision、物体静置漂移和回调覆盖，不能把未标定的“没有接触记录”当作通过。上游平地训练入口是低层基线工具，**不是完整密集障碍学习环境**。

## 科研与权属

精细全身规划、三维记忆、规划+学习和保护地面物品均已有重要先例；候选贡献必须由公平比较和消融决定。硬件/传感器/预算/投稿目标未确认，不继承其他无人机项目配置。没有真机电机下发程序。公开仓库不自动代表新开源许可证；第三方资产和权重许可需单独审核，不上传来源不明素材。
