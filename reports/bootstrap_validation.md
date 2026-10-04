# 初始化验证报告

验证日期：2026-10-04。环境：Python 3.13.5，当前工作容器。此报告已在公开仓库初始化提交前重新执行测试后更新；结果仅限本地软件。

## 已执行

| 项目 | 命令 | 实际结果 |
|---|---|---|
| 评测器单元测试与 CLI 测试 | `python -m unittest discover -s tests -v` | **38 tests，全部通过**；原始输出见 [bootstrap_unittest.log](bootstrap_unittest.log) |
| 本地项目一致性 | `python scripts/check_project.py` | PASS：相对链接、JSON、人工样例语义、文献及论文主张标识 |
| 历史建库脚本语法 | `bash -n scripts/publish_github.sh` | 退出码 0 |
| 历史建库脚本默认预览 | `bash scripts/publish_github.sh` | 退出码 0；仍显示旧 private 建库计划；无本地 Git 或远端写操作，当前仓库不使用此脚本发布 |
| 人工成功摘要 | `python -m qct evaluate examples/synthetic_episode_success.json --config configs/benchmark_v0_1.json` | strict_success=true；real_robot_recorded_success=null |
| 人工接触摘要 | `python -m qct evaluate examples/synthetic_episode_contact.json --config configs/benchmark_v0_1.json` | non_disturbing_success=true；strict_success=false |
| 常见凭据模式扫描 | 对待提交 UTF-8 文件检查 GitHub token、API key、私钥头模式 | 无匹配；不是全面安全审计 |

两个 CLI 的完整输出见 [成功样例](synthetic_success_evaluation.json) 和 [接触样例](synthetic_contact_evaluation.json)。这些都是人工构造的测试数据，不是机器人运动结果。

## 测试覆盖的关键语义

正常足端支撑不误判；脚/腿/机身/自碰撞等禁止接触被拒绝；轻碰而不碰倒不是严格成功；物体扰动使用全回合最大值；回合/接触/物体监测缺失时不臆测成功；已观测失败不被缺测覆盖；真值、机载、仿真与真机轨道隔离；空场标定输入受支持；无穷、NaN、超范围数值、重复/缺失对象、未来事件、版本冲突和格式错误被处理。

## 仓库范围与没有执行的内容

已读取用户创建的公开仓库 kisisjrlly/quadruped-clutter-traversal，默认分支 main，具备写入权限；用户已明确授权公开提交。README、协作规则、状态与维护文档已经同步该决定。原始参考截图和其他项目文件没有纳入待提交文件。

本报告是提交前验证记录。是否已提交到远端，必须以 GitHub 的实际 commit 和 main 读回为准，不能由本报告推断。没有运行历史发布脚本的 --apply，也不借其私有仓库预览证明本次公开提交。

没有物理引擎、机器人模型或控制器，没有 GPU 训练，没有传感器数据，没有真机实验。没有验证碰撞监测的真实灵敏度，也没有审核摘要背后的原始证据。Hash 只做格式校验，不是证明数据真实。

没有配置或执行 GitHub Actions CI，没有创建 PR、issue、Projects 看板或定时任务。只验证了本报告注明的 Python 版本；未对全部 Python >=3.10 环境做矩阵测试。该软件层测试通过不意味着严格成功率已经测得，更不意味着论文假设已证实。
