# 第1轮迭代验证报告

日期2026-10-04；本地Python3.13.5，CPU容器。此报告是提交前验证，不自动证明GitHub推送或Actions成功。

| 执行项 | 结果与范围 |
|---|---|
| `python -m unittest discover -s tests -v` | 112项通过；原始输出见iteration1_unittest.log。原有38项保留，新增74项 |
| `python scripts/check_project.py` | 在本报告创建后重新执行：通过相对链接、JSON、fixture、引用/claims检查 |
| `python -m compileall -q qct scripts` | 通过；只验证语法，不导入/运行Isaac |
| `python -m qct.workflow doctor` | isaaclab=false，isaacsim=false；详细输出见iteration1_doctor.json |
| 场景生成/弱A* CLI | calibration空场seed7正常导出；A* found，范围为oracle圆形机身路径，不是四足轨迹 |
| Isaac启动器依赖失败 | 实际调用在缺Isaac Lab时退出码1并明确说明没有执行仿真；没有回退假后端 |
| 安全范围 | 仅源代码/文档/人工软件测试；不含图片、第三方USD、权重、真机网络信息或电机命令 |

新增测试覆盖：场景seed/split/packing/哈希/拒绝覆盖；SDF/四元数/薄杆采样/线性扫掠/支撑多边形；A*预算和足端未知空间；深度无效像素/记忆老化/回合隔离/容量；接触路径方向/足与calf区分/自碰撞/未知分类；物体全程最大扰动/缺帧/缺测/终止/trace与摘要篡改；统计分组/未知分母；策略顺序/normalizer/hash契约。测试里的人工轨迹不是仿真结果。

没有执行：NVIDIA GPU/Kit物理运行、USD资产下载与完整几何审计、传感器与接触标定、Isaac站立/步行/穿越、PPO或其他训练、权重导出、真机试验。所有论文机制和能力主张仍待验证。新增CI只是配置；远端执行需另查Actions结果。

已知工程限制：当前Isaac runner未标定且t0接触未求解，故不能严格认证通过；其边界/起跳/支撑/附件覆盖未全验收。局部记忆未接actor，几何模块未建立真实机器人全连杆FK/IK及动态可行轨迹。上游平地训练入口不是QCT密集障碍环境。

所有Isaac代码只是按官方v2.3接口编写并语法检查，可能存在仅本地GPU运行才能暴露的接口或物理问题。不得把112项CPU回归写成“112项仿真测试”。下一验收按docs/CODEX_START_HERE.md执行。
