# AnyRouter 自动签到 CLI (MVP)

本项目按照 `prd.md` 与 `plan.md` 中的 MVP 要求构建，提供自动化的 GitHub 授权、签到与历史记录骨架。当前版本实现了计划 P1–P3 的核心能力：项目结构、配置加载、授权导出与签到流程。

## 快速开始

1. **安装依赖**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **准备配置**

   拷贝 `config.sample.toml` 为 `config.toml` 并按需修改：

   ```bash
   cp config.sample.toml config.toml
   ```

3. **首次授权**

   运行下列命令打开带界面的浏览器，完成 GitHub OAuth 并保存会话：

   ```bash
   python -m app.cli authorize
   ```

4. **触发签到**

   ```bash
   python -m app.cli signin --slot=morning
   ```

   签到结果会写入 `data/history.csv`，终端会输出成功/已签/失败状态。

5. **查看历史**

   ```bash
   python -m app.cli status --last 20
   ```

6. **撤销授权**

   ```bash
   python -m app.cli revoke
   ```

## 目录结构

```
app/
  cli.py          # CLI 命令入口
  config.py       # TOML 配置解析与加载
  auth.py         # 授权与撤销逻辑（Playwright headed）
  signin.py       # 签到流程（Playwright headless）
  runner.py       # 调度封装
  history.py      # CSV 历史写入
  selectors.py    # 关键字匹配辅助
  notify.py       # 邮件发送占位
  scheduler.py    # 调度占位
config.sample.toml # 示例配置
requirements.txt   # 依赖
```

## 未来计划

* P4：完成 `daily_state.json` 与邮件通知策略。
* P5：历史滚动、状态查询增强以及调度常驻。
* P6+：失败分类细化、自动重试、文档交付等。

详情请参考仓库根目录的 `plan.md` 与 `prd.md`。
