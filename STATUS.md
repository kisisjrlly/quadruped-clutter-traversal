# STATUS

初始化版本：2026-10-04。此文件记录可核验状态，不把计划写成成果。

| 层级 | 状态 | 证据 |
|---|---|---|
| GitHub 仓库 | 用户已创建 kisisjrlly/quadruped-clutter-traversal；Public；main；有写入权限 | 提交前 GitHub 元数据读取；用户明确授权保持公开、直接提交 |
| 初始化版本 | 本版本包含研究文档、评测器、测试与本地验证记录；保留用户 Initial commit | 以包含本文件的 Git commit 及远端 main 的读回结果核验；不以本地文件存在替代推送成功 |
| 任务、路线、实验、维护文档 | 已创建；公开仓库决策已同步 | README 中的相对路径；docs/DECISIONS.md |
| 相关工作 | 启动阶段的初步核查，不是穷尽检索；本次提交未追加文献检索 | docs/RELATED_WORK.md；references/verified_sources.json |
| 评测器和人工测试样例 | 已实现；38 项本地软件测试通过 | reports/bootstrap_validation.md；reports/bootstrap_unittest.log |
| 场景生成/物理引擎/机器人资产 | 未实现、未选定 | docs/CODEX_START_HERE.md 的下一任务 |
| 传感器仿真/实测 | 未实现 | 不得宣称“仅机载视觉已完成” |
| 全身规划/步态控制/策略训练 | 未实现 | 无控制权重、无机器人轨迹 |
| 真机与论文结果 | 未开展 | paper/claims.csv |
| GitHub Actions / Projects | 未配置 CI、未创建 Projects 看板 | 不把本地测试称为远端 CI |

## 下一项：M1 几何与接触最小闭环

确认机器人资产和控制接口；建立含足端、腿段、机身与附件的碰撞模型，加入可检测轻触/移动的障碍，验证一条明确可行的慢速步行动作。先用真值地图做诊断轨道，不宣称部署能力。

## 阻塞/待决策

机器人型号与 SDK 控制权限；传感器覆盖脚下和后腿的能力；可用计算设备；真机场地与安全条件；论文核心机制。均不可从其他项目自动推断。

## 每次更新必须填写

变更目的、文件、Git commit、实际运行命令、测试结果、仍未完成项、下一验收门槛。提交 SHA 从 Git 历史获得，避免在当前提交内编造其自身 SHA。远端推送必须通过 main 读回核验；此状态文件不是持续自动更新的实时监控。
