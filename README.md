# Quadruped Clutter Traversal
## 密集易扰动障碍环境中的四足机器人精细穿越

**研究愿景：从“能走到终点”，推进到“依靠机载感知，协调身体和四条腿，在密集随机障碍间穿过，并尽量不接触、不扰动物体”。最终形成可复现的论文成果。**

本项目受到用户在 2026-10-04 提供的狗穿越室内障碍区截图启发。截图不是完整视频，不能据此断言狗已经零接触通过，也不能从单帧推出它的内部感知或控制机制。我们复现的是所期望的任务能力，不是外观、动作动画或未经验证的动物认知解释。

> **当前状态：研究启动包 + 评测逻辑骨架。没有物理仿真、机器人控制器、训练结果或真机实验。**
> 仓库：`kisisjrlly/quadruped-clutter-traversal`；默认分支 `main`；**Public（公开）**。仓库已由项目发起人创建，并于 2026-10-04 明确授权保持公开、直接提交。独立维护，不 fork，不向任何上游发 PR。

### 任务要点

在两侧受限的通道内随机混合摆放细杆、立木条、低矮木块和瓶罐。机器人获得起点与终点区域，仅依靠机载外感知和本体感知，自主协调躯干姿态、四足落点、摆腿轨迹及步态时序。允许慢走、停看、后退重规划；主任务不允许跳过整个区域、推开物品、踩在待保护物品上或中途人工导航。无解时安全停止是安全行为，但不计穿越成功。

### 先阅读什么

| 文件 | 解决的问题 |
|---|---|
| [项目章程](docs/PROJECT_CHARTER.md) | 最终效果是什么，哪些条件已确认，哪些尚未确认 |
| [任务与基准](docs/TASK_AND_BENCHMARK.md) | 什么算同一种场景，什么算成功 |
| [相关工作](docs/RELATED_WORK.md) | 哪些能力已有研究，不能把什么当创新 |
| [研究假设](docs/RESEARCH_HYPOTHESES.md) | 论文需要证明什么，什么结果会推翻设想 |
| [系统设计](docs/SYSTEM_DESIGN.md) | 数据流、模块职责、感知与控制闭环 |
| [路线图](docs/ROADMAP.md) | 分阶段做什么，如何验收，不凭时间承诺进度 |
| [实验协议](docs/EXPERIMENT_PROTOCOL.md) | 公平对比、数据隔离、接触判定与失败审计 |
| [Codex 入口](docs/CODEX_START_HERE.md) | 本地开发首先执行的具体任务 |
| [当前状态](STATUS.md) | 已实现、已测试、未实现分别是什么 |

### 已可运行的内容

只使用 Python 标准库，约定 Python 3.10 或更新版本。以下命令在项目根目录执行：

```bash
python -m unittest discover -s tests -v
python scripts/check_project.py
python -m qct evaluate examples/synthetic_episode_success.json --config configs/benchmark_v0_1.json
python -m qct evaluate examples/synthetic_episode_contact.json --config configs/benchmark_v0_1.json
```

这只是在测试“评测器是否区分碰倒、接触、缺测、特权观测”等情况。`synthetic_fixture` 是人工构造的测试输入，**不是仿真轨迹，更不是真机结果**。评测器不会从摘要自动识别碰撞；原始数据采集、接触监测、轨迹验证和完整性校验仍需实现。

### 推进原则

先定义可测任务并做几何/传感器可行性检查，再实现可解释基线；之后才选择需要学习的部分。最终方法尚未确定，不预设一定要端到端强化学习、教师学生蒸馏、主动视觉或大模型。平台、相机、GPU、预算、时限与投稿 venue 均未确认，不能继承其他无人机项目的配置。

### 获取项目与后续开发

仓库已经创建，不需要重复建库。首次获取：

```bash
git clone https://github.com/kisisjrlly/quadruped-clutter-traversal.git
cd quadruped-clutter-traversal
python -m unittest discover -s tests -v
python scripts/check_project.py
```

已有本地克隆时，先核对 remote、分支、未提交改动，再使用 `git pull --ff-only`；不要覆盖本地工作。后续开发从 [Codex 入口](docs/CODEX_START_HERE.md) 开始。

见 [GitHub 维护说明](docs/GITHUB_SETUP.md)。`scripts/publish_github.sh` 是原始启动包的历史建库脚本，**当前仓库已存在，不再使用其 `--apply` 模式**。本项目首先是代码与文档仓库，尚未创建 GitHub Projects 看板。

### 成果与权属

目前没有论文结果、模型权重和开源许可承诺。第三方代码、机器人资产和图片的许可须逐项审核；未自动复制用户参考截图或论文图到仓库。仓库公开已经作者确认；这不等于自动授予开源许可证。新增数据、图片、视频、第三方资产和许可证仍需单独审核。
