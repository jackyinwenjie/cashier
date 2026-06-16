---
alwaysApply: true
scene: git_message
---

在此处编写规则，自定义 AI 生成提交信息的风格。

---

## Git 分支与推送规则

**强制流程：dev → main → push**

1. 日常开发始终在 `dev` 分支进行
2. 提交代码时：
   - 先在 `dev` 分支提交（`git add` + `git commit`）
   - 然后切换到 `main` 分支，合并 `dev` 的代码（`git checkout main && git merge dev`）
   - 从 `main` 分支推送到远程（`git push origin main`）
   - 推送完成后切回 `dev` 分支继续开发
3. **禁止将 `dev` 分支推送到 GitHub**，远程只保留 `main` 分支
