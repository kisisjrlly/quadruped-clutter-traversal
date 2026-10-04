# 给本地 Codex：从这里开始

## 先确认环境与边界

读取 AGENTS、STATUS、TASK_AND_BENCHMARK、SYSTEM_DESIGN 和 ROADMAP。核对当前目录与 Git remote：只允许写入 kisisjrlly/quadruped-clutter-traversal。该独立仓库已由用户创建，并明确授权保持公开、直接提交 main；禁止 fork、上游 PR、擅改可见性和 force push。开始前读取远端与本地 SHA，保留现有历史和未提交改动。

依次运行：

```bash
python --version
python -m unittest discover -s tests -v
python scripts/check_project.py
python -m qct evaluate examples/synthetic_episode_success.json
python -m qct evaluate examples/synthetic_episode_contact.json
```

人工 fixtures 通过只代表评测逻辑测试通过。不要改文件把它们变成 simulation 或 real_robot 结果。

## 第一次实施任务：M1，不做训练

A. 调查本机可用仿真环境/机器人模型，输出 `reports/platform_audit.md`：已安装版本、可访问资产、许可、控制接口与实际硬件。重要信息缺失就问，不猜。

B. 经选择后只适配一个引擎/机器人，新增真实模块 `qct/sim/` 与 `qct/geometry/`，不先批量创建空模块。建立平地、一杆、一瓶场景；杆和瓶可被扰动，不以固定刚体掩盖碰倒问题。

C. 以 URDF/MJCF 中的全连杆和附件构建碰撞检测。确认足端、小腿、大腿、机身、附件都可归因；检验球/胶囊近似是否过粗。

D. 实现回合采集器：保存完整状态与原始事件，计算全程最大对象位移/旋转，输出与当前 evaluator 一致的摘要；缺测不得默认零。配置 schema 改动需升版本、同步文档和测试。

E. 验证一条安全单步和至少足端、小腿、机身三类故意接触；在细杆高速扫过、低频采样和终止自动 reset 条件下验证不漏记。这里“高速”仅为仿真测试，不用于真机。

F. 生成清晰回放：机器人、障碍、当前四足、选中的摆腿轨迹和接触高亮，默认不画所有调试线。不得以渲染穿模当成功。

## 第一份交付必须包含

单命令可复现的最小场景；所有新模块的单测/集成测试；机器人/场景/代码版本；可行与故意失败样例；未完成与限制；下一步 M2 是否可启动。更新 STATUS、DECISIONS、实验记录。不要声称论文方法完成。

## 暂不做

不启动大规模 RL、不选择多个并行主线、不接真实电机、不采购硬件、不上传大日志/第三方图片、不改现有无人机项目。不要把既有稳定 controller 的 checkpoint 当本项目训练成果。
