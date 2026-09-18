# GitHub 发布指南

## 发布前
1. 确认目标账号/组织、仓库名称、公开或私有。建议仓库名 audio-notes-skill。
2. 核对 LICENSE 的版权主体；目前使用 `Audio Notes Skill contributors`，不是已核验的个人法定名称。
3. 仅发布解压得到的项目目录，不上传聊天附件、音频、私人工作目录、密钥或转写检查点。
4. 阅读 VALIDATION.md，首版标为预览版本，不声称全部转写能力已实测。

## 无 Git 的网页方式
- 在 GitHub 新建仓库，选择已确认的可见性。
- 使用 Add file → Upload files 上传**解压后的文件**；单独上传 ZIP 不便于 Agent 发现 SKILL.md。
- 必须让 SKILL.md 位于仓库根目录；不要多套一层目录。
- 浏览器可能遗漏以点开头的 `.github/` 和 `.gitignore`，请检查；必要时通过 GitHub 编辑器补建。
- 可把项目 ZIP 另外作为 Release 附件。

## Git / GitHub CLI 方式（安装并授权后）
先在你自己的终端运行 `gh auth login` 完成授权，不把密码或 token 发进聊天。以下命令中的 OWNER 和可见性需先确认，不能原样盲目执行。

```text
git init
git add .
git diff --cached --stat
git commit -m "Initial audio-notes skill" -m "Co-authored-by: Chatbox <chatbox@chatboxai.com>"
gh repo create OWNER/audio-notes-skill --public --source . --remote origin --push
```

这是新建仓库示例，不适用于覆盖现有仓库。若已有仓库，先检查远程与工作区，再用新分支提交，不强制推送。由 Chatbox 创建工作分支时使用 `chatbox/` 前缀。

本项目不附带自动发布脚本，避免误公开、覆盖仓库或将私人目录一并上传。发布操作应在用户确认目标后执行。
