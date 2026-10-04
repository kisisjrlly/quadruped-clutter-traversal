# GitHub 仓库与后续维护

## 已确认的仓库与授权

- 仓库：`kisisjrlly/quadruped-clutter-traversal`。
- 默认分支：`main`；可见性：**Public（公开）**。
- 仓库由项目发起人创建。2026-10-04 在得知公开影响后，明确授权“保持公开、直接提交”。
- 本次初始化保留用户的 Initial commit，直接向本仓库 main 提交；不 fork、不向其他仓库开 PR、不 force push、不修改可见性。

提交前读取的原始 main：`58ad432144a907009bc91ad4ce0b0086d3b7b89e`。它只包含用户创建的简短 README；本版本扩充该首页并加入启动包。实际初始化提交以 Git 历史与 main 读回结果为准，不能把本文件当作远端成功的独立证明。

## 首次获取

```bash
git clone https://github.com/kisisjrlly/quadruped-clutter-traversal.git
cd quadruped-clutter-traversal
python -m unittest discover -s tests -v
python scripts/check_project.py
```

已有克隆时，先检查 `git remote -v`、`git status` 和当前分支，再执行 `git pull --ff-only`。存在本地改动或分叉时先核对并保留工作，不自动 reset、清理或覆盖。

## 历史脚本说明

`scripts/publish_github.sh` 保留的是首次启动包中的“新建独立私有仓库”脚本，不是当前仓库的更新脚本。现在仓库已存在，**不要执行 `--apply`**。默认预览不写入任何本地或远端资源。保留该历史脚本不表示当前仓库仍是私有，也不改变本次明确授权。

日常更新使用已有仓库和正常 Git 提交流程。不要向助手发送 PAT、密码或机器人网络凭据；也不要为了推送改变全局身份或关闭安全设置。

## 发布与证据规则

每次写入前核对精确 owner/repo、branch、当前 SHA、visibility 和 fork 状态。新提交必须基于实际读取的父提交；main 已有他人新提交时重新读取并合并，不强制覆盖。提交后读取 main，核对 commit 和文件内容，再报告成功。

本地测试结果只证明对应软件测试通过，不代表 GitHub Actions、仿真、真机或论文结果。公开仓库不代表自动提供开源许可证；原始参考截图、私人数据、密钥、视频、权重和第三方资产不得默认上传。

## 维护节奏

每次实现：更新 STATUS，附命令/结果；重要方法变更记 ADR；每次实验使用模板并把证据挂到 claims；相关工作在立项、确定方法、正式测试和投稿前重查，避免把旧结论当实时事实。

当前 issue 模板可用于后续创建任务。没有创建 GitHub Projects 看板，也没有自动建立定时维护任务。
