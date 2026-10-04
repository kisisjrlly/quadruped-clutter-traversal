# 论文计划

工作题目：Contact-Sensitive Quadruped Traversal through Dense Mixed-Height Clutter。题目可改，当前无论文结果/录用承诺。

完整问题、架构、假设和阶段见 [研究方案 v2](RESEARCH_PLAN_V2.md)，文献审查见 [相关工作](RELATED_WORK.md)。

论文主线应是：统一可审计任务 → 近邻差异 → 经实验证明的具体机制 → 强基线 → 等预算消融 → 真机泛化和失败。仅有一段狗风格演示不够；仅加记忆或碰撞惩罚也不足。

必备表：到达/无扰动/无禁止接触及unknown；按身体部位和场景因素的错误；观测/定位/跟踪误差；速度/时延/训练与显存预算。所有尚未测量的值为unavailable，不填0。

`paper/claims.csv`是结论账本，软件测试不能升级成仿真能力，仿真能力不能升级成真机验证。不选定具体期刊级别，待机制与实验结果再评估。
