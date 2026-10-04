# 给本地 Codex：第1轮交付后的下一步

只操作 `kisisjrlly/quadruped-clutter-traversal`，公开main，保留远端历史和本地改动，不force push。先读AGENTS、STATUS、RESEARCH_PLAN_V2、ISAACLAB、EXPERIMENTS_V2。

## 已有代码先验证

```bash
python -m unittest discover -s tests -v
python scripts/check_project.py
python -m qct.workflow doctor
python -m qct.workflow scene --seed 0 --split calibration --count 0 --output runs/empty.json
python -m qct.workflow plan runs/empty.json
```

当前CPU组件已经有回归测试；不要把人工测试轨迹当仿真结果。无需重写生成器、评测器或另起MuJoCo主线。

## P0：在本地Isaac环境完成接口与物理验收

记录操作系统/GPU/显存/驱动/Isaac Lab/Sim版本、官方Go2资产可用性与许可。按ISAACLAB.md先跑empty stand，然后一杆一瓶。修复实际接口错误后加集成回归，不因脚本通过py_compile就停止。

检查 `run.json` 的实际joint/body/collider路径。将真正foot collider映射到canonical足，不将calf全部映射foot。确认相机光学朝向、遮挡、depth类型、帧时间，检查静置物品漂移。保存完整state/contact原始记录和版本。

## P1：建立可审计M1物理fixture

实现可控仿真故意接触：foot、calf、thigh、base、wall、self；区分脚正常地面支撑。补做净力抵消/低冲量/细杆跨采样/暂停/退出/初始接触状态验证。独立核查碰撞网格覆盖和CCD/报告缓冲容量。数据要从真实物理引擎采集，不手写JSON代替。

当前runner硬性保持contact calibration未验证且t0未求解，因此strict认证无法通过。这是已知保护，不是应删掉的“阻碍”。在独立物理fixture通过后设计calibration manifest绑定物理配置、资产版本、范围、证据hash和完整监测，形成新commit；同时完善包络越界、跳跃/支撑、附件监测。

## P2：强oracle全身/跟踪基线

当前A*只规划圆形机身；foot swing只检查足端，capsule线性扫掠不替代真实关节轨迹。下一步从实际USD几何建立FK/IK和保守全连杆覆盖，集成慢速跟踪，验证一条完整body+feet轨迹。只有几何与实际跟踪误差足够小，才进入密集布局和感知闭环。

需要训练低层时先审核M1 gate，再用 `isaac_baseline_train.py`。其任务是上游平地速度控制；不能把训练完成写成QCT障碍能力完成。若需要精确落足跟踪，按DTC类参照设计并另行记录。

## P3：感知和论文实验

现有VoxelMemory是CPU参考，不是最终NVM或完整感知系统。接入经过估计的位姿、同步深度、缺测/年龄信息，建立oracle与sensed严格隔离；再做H1/H2和SemLoco等强对照。禁止先写“首次”或虚构成功率。

每次交付更新STATUS、DECISIONS、实验模板与claims，附实际命令、原始记录、测试、仍未完成项。保留历史bootstrap报告。资源或机器人型号不明时只问必要问题，不继承无人机项目配置；不连接真机电机。
