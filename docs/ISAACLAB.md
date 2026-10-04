# Isaac Lab / Isaac Sim 仿真实施与运行

## 1. 决策与版本

用户指定 Isaac Lab 或 Isaac Sim。本项目采用 **Isaac Lab 接口 + Isaac Sim/PhysX**，不另设 MuJoCo/PyBullet 主线。当前源码查阅基线固定为 **Isaac Lab v2.3.0 / Isaac Sim 5.1**，这不是“最新版本”的断言；NVIDIA 发布说明明确了该版本关系。其他版本需独立兼容性记录，不能盲用浮动 main。[S01]

当前容器只有 CPU Python/Torch，没有 isaaclab/isaacsim/CUDA；下面接口已经编写并做语法检查，**未在 Kit 中运行**。启动器缺依赖会明确报错，不回退成假仿真。CPU测试通过不能证明 USD 可下载、PhysX contact callback 在所用GPU模式下完整或机器人能站稳。

## 2. 已写入的仿真链路

`AppLauncher → SimulationContext → Go2 Articulation + 动态 RigidObject → PhysX 原始接触回调 → 每步状态 → trace.jsonl → episode.json → evaluator/audit`。

使用 Isaac Lab 内置 `UNITREE_GO2_CFG`，不复制第三方资产；对象为柱体/盒体几何代理，不声称真实瓶子惯量/材质已建模。墙和地面固定，杆/瓶/块具有质量与摩擦并可受碰撞移动。碰撞检测请求 CCD，机器人请求 self-collision 开启；请求参数不等于已经通过实际验收。[S02][S03]

相机可选前向320×240深度，输出 `distance_to_image_plane`，ROS光学坐标为+Z前、+X右、+Y下，四元数按 wxyz。必须用相同帧的相机位姿和时间；当前记录的位姿是**仿真真值**。虽然相机安装在机体上，当前控制仍是 oracle，不得标作完整机载感知闭环。[S04]

`stand` 仅施加默认关节目标，用于观察资产/静置漂移；不会自动产生行走。`policy-route` 用保守机身路线给外部速度策略命令，需要单独提供 checkpoint 和严格48维观测协议。它不是全身规划算法，也没有内置本项目训练权重。

## 3. 从新机器运行

先按 NVIDIA 官方步骤安装匹配版本与驱动并完成官方示例，再运行本项目。以下路径由本机设置，不能照搬其他项目 conda 路径。

```bash
cd /path/to/quadruped-clutter-traversal
python -m unittest discover -s tests -v
python scripts/check_project.py
python -m qct.workflow doctor
python -m qct.workflow scene --seed 0 --split calibration --count 0 --output runs/empty.json
python -m qct.workflow scene --seed 1 --split calibration --count 2 --output runs/two_objects.json

export ISAACLAB_PATH=/path/to/IsaacLab
"$ISAACLAB_PATH/isaaclab.sh" -p scripts/run_isaaclab.py \
  --scene runs/empty.json --output runs/empty_stand --mode stand --duration 5
"$ISAACLAB_PATH/isaaclab.sh" -p scripts/run_isaaclab.py \
  --scene runs/two_objects.json --output runs/two_objects_stand --mode stand --duration 5 --enable_cameras
```

每个输出目录只能新建，不覆盖已有实验。第一轮先看 `run.json` 中的 joint/body/collision inventory、版本、CCD/selfcollision配置、可见性与足部实际路径；任何初始化异常都先解决，不能把程序退出说成完成任务。

默认没有足端路径别名，不猜测“整个calf接地就是foot接地”。创建 `local_foot_aliases.json`：键为实际 USD 足碰撞体或独立foot刚体的完整路径，值为基准允许的四个canonical足名称。若foot是calf上的子碰撞体，只能映射该子体，不能映射整段calf。接触原始actor/collider路径一直保存。[S05]

## 4. 运动策略的接入契约

只接受已审核的 TorchScript 策略，且 JSON spec 明确：

- `schema_version=qct.policy.v1`；`observation_layout=lin3_ang3_gravity3_command3_q12_dq12_previous12`。
- 完整12关节名称/顺序、48个观测缩放、12个动作缩放、12个默认关节角、控制周期、训练一致的正数`action_clip`和实际策略SHA256。
- `exported_normalizer_included=true`：导出策略包含正确归一化（或训练明确使用恒等归一化），不能随便把此字段设true以通过检查。

`lin/ang`在机身坐标，关节位置减训练默认值，previous是上一原始策略动作，动作映射到绝对关节目标后还受软关节限位。协议不匹配直接失败，不自动填零或猜测排序。当前runner按spec中的`action_clip`裁剪，因此必须与训练/导出约定一致；上游策略需实际核对，不保证任意checkpoint即插即用。

```bash
"$ISAACLAB_PATH/isaaclab.sh" -p scripts/run_isaaclab.py \
  --scene runs/two_objects.json --output runs/oracle_baseline_001 \
  --mode policy-route --policy /path/to/policy.pt --policy-spec /path/to/policy_spec.json \
  --link-map local_foot_aliases.json --duration 30
```

若保守A*无路，程序拒绝让机器人盲走；这只代表该弱基线找不到路线，不代表任务物理无解。低块被投影成不可跨越圆形障碍，所以该基线不是最终能力。

## 5. 训练入口的明确边界

`isaac_baseline_train.py` 调用干净的 v2.3.0 上游 `Isaac-Velocity-Flat-Unitree-Go2-v0`。这是**平地低层速度策略**，不是密集障碍训练环境。M1门槛在 [模板](../configs/m1_gate.example.json) 中，默认全部false；需要实际物理测试和审核者、原始trace目录才能启动。门槛文件是人工审核记录，不是防伪签名，脚本检查不能代替审查。

```bash
"$ISAACLAB_PATH/isaaclab.sh" -p scripts/isaac_baseline_train.py \
  --isaaclab "$ISAACLAB_PATH" --gate /path/to/reviewed_m1_gate.json \
  --num-envs 64 --iterations 1500 --seed 0
```

并行数/迭代只是初始参数，不是显存或收敛保证。上游导出/训练权重必须记录来源和实际哈希；本轮没有训练/导出任何权重。

## 6. 日志与接触观测为何保守

原始JSONL包括header、每个物理步的状态/对象位姿/接触以及terminal。禁止自动reset，结束前写terminal。`episode.json`保留全程最大位移/旋转，不只比较起终点；日志字节哈希与重建摘要校验分开。[S05]

回调捕获FOUND/PERSISTS，即便净力小或相互抵消也不简单丢弃；LOST不是新碰撞。未知机器人碰撞对象使coverage失效，原始路径保留。程序没有接触标定结果，且t=0尚未求解接触，因此当前runner**永不据此认证严格成功**，完整无接触结论维持unknown；观察到禁止接触则仍可确定失败。

其他限制：当前边界检查是所有刚体原点而非完整包络；未单独证明起跳/物体支撑行为监测；深度没有实测噪声模型；相机附件无专门物理碰撞外壳；物体模型和机器人USD依赖没有全部做字节级哈希。这些限制已阻止strict认证，不得在论文中隐去。

## 7. M1 必做验收

空场站立；对象无人接触静置漂移；足端/小腿/大腿/机身分别轻触；墙、自碰撞、foot地面允许接触；同一物理步多个接触；低冲量与细杆跨采样；暂停/窗口退出；重复seed/异步相机；初始接触求解前后记录；GPU物理报告容量和CCD设定；物体倾倒/短时位移后恢复；退出前而非reset后状态。

先用明确可控的仿真注入fixture制作这些验证，保存施加运动、时间戳与传感器输出，不使用人工构造CPU JSON冒充仿真。通过后另开一轮commit引入经审核的calibration证据绑定，不能只给当前代码传一个字符串就宣布监测可靠。

## 8. 官方来源与许可

[S01] Isaac Lab release notes：<https://isaac-sim.github.io/IsaacLab/main/source/refs/release_notes.html>

[S02] v2.3.0 Go2配置：<https://github.com/isaac-sim/IsaacLab/blob/v2.3.0/source/isaaclab_assets/isaaclab_assets/robots/unitree.py>

[S03] v2.3.0资产示例：<https://isaac-sim.github.io/IsaacLab/v2.3.0/source/tutorials/01_assets/run_articulation.html>

[S04] v2.3.0机器人传感器：<https://isaac-sim.github.io/IsaacLab/v2.3.0/source/tutorials/04_sensors/add_sensors_on_robot.html>

[S05] NVIDIA PhysX接触报告接口：<https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/extensions/runtime/source/omni.physx/docs/dev_guide/contact_reports.html>

引用接口与导入库不意味着再分发其USD/权重许可已经审核。本仓库没有把公开可见性当成新开源许可证；未复制论文图、狗截图或上游源文件。版本升级先跑M1回归，保留原结果，不覆盖历史。
