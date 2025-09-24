# anyrouter.top 自动签到（MVP）实施计划

## 1) 里程碑与交付物

* **M1：骨架就绪**（项目结构 + 配置样例 + 依赖安装脚本）
* **M2：授权闭环**（`authorize` 可导出 `storage_state.json`）
* **M3：签到闭环**（`signin` 可判定 成功/已签/失败 并写入历史）
* **M4：通知闭环**（SMTP 成功/失败邮件逻辑符合“当日仅 1 封成功、失败每次一封”）
* **M5：调度上线**（三时段定时执行；状态查询/撤销可用）
* **M6：验收通过**（覆盖 U1–U8 用例）

---

## 2) 工作分解（WBS）与 DoD

### P0 需求冻结与准备

* 明确**站点选择器/关键词**（签到按钮、成功/已签文案、可监听的接口路径）。
* DoD：产出 `config.sample.toml` 的 selectors 占位符（可运行的默认值）。

### P1 项目骨架 & 配置（M1）

* 建目录：`app/`（cli、config、runner、auth、signin、selectors、history、notify、scheduler、utils）。
* 写 `requirements.txt`、Playwright 安装脚本、`README.md` 初始化步骤。
* DoD：`python -m app.cli --help` 可运行；`config.sample.toml` 可复制为 `config.toml`。

### P2 授权流程（M2）

* `authorize`（headed）：打开 anyrouter → GitHub 登录 → 回站点 → 导出 `storage_state.json`。
* `revoke`：清理会话文件并记录一次“审计事件”到 CSV。
* DoD：授权成功后立刻可在 `storage_state.json` 看到有效 cookie/localStorage；`revoke` 后再次 `signin` 会提示需授权。

### P3 签到流程与判定（M3）

* `signin`（headless + storage\_state）：打开站点 → 若跳 GitHub 登录视为 `auth_invalid`。
* **结果判定优先网络响应**，否则回退 DOM 文案（keywords/regex 来自 `selectors`）。
* 写入 CSV 行（带 `result/err_category/err_summary/http_status/duration_ms`）。
* DoD：本地一次执行能产出“成功/已签/失败”三分支的记录（可通过强行错误或模拟触发）。

### P4 当日状态 & 幂等邮件（M4）

* `daily_state.json`：`has_success_mail_sent/first_success_time/fail_count_today`。
* 邮件策略：**当日首次成功才发成功邮件**；**每次失败都发失败邮件**。
* DoD：在同一自然日多次 `signin`，只收到 1 封成功邮件；失败时每次都有失败邮件。

### P5 历史滚动 & 状态查询（M4）

* CSV 超过 `history_max_rows` 进行 FIFO 截断。
* `status`：展示今日状态（是否发过成功邮件、首次成功时间、失败计数）与最近 N 条历史。
* DoD：制造超限记录后旧行被删除；`status` 输出准确。

### P6 调度集成（M5）

* **首选 OS 级**：提供三条 cron（09:00 / 14:00 / 21:00，Asia/Singapore）。
  备选：`schedule`（APScheduler）常驻。
* DoD：三时段能按时触发（通过日志/邮件/CSV 验证）。

### P7 失败分类与轻量重试（M5）

* 分类：`network|dns|tls|timeout|http4xx|http5xx|auth_invalid|risk_control|unknown`。
* 轻量重试：失败后等待 \~15s 再试 1 次。
* DoD：人为断网/限流等能看到分类与重试一次后仍失败的记录与邮件。

### P8 文档与交接（M6）

* 最终 README（安装、授权、运行、调度、问题排查）。
* 配置说明、邮件模板、运维清单（备份与迁移、重新授权步骤）。
* DoD：按 README 从零环境完成全链路。

---

## 3) 验收清单（对应 MVP 用例 U1–U8）

* **U1 首次授权**：`authorize` 成功，CSV 记一条 `stage=authorize` 审计。
* **U2 早场成功**：记录成功 + **当日 1 封成功邮件**；`has_success_mail_sent=true`。
* **U3 中/晚幂等**：记录“已签到（幂等）”，**不再发成功邮件**。
* **U4 任一失败**：记录失败 + **失败邮件**（含分类）。
* **U5 早失败→中成功**：两封邮件（1 失败 + 1 成功），成功为当日唯一成功邮件。
* **U6 授权失效**：记录 `auth_invalid` + 失败邮件提示“重新授权”。
* **U7 历史滚动**：超 `history_max_rows` 后 FIFO 生效。
* **U8 撤销授权**：清理会话、记录审计；后续执行提示需授权并发失败邮件。

---

## 4) 计划安排（建议节奏）

> 以“块”为单位推进，可在 1–2 个工作日内完成；若要更稳健测试，可再加 1 天观察。

1. **块 A（P1+P2）**：骨架、配置、授权/撤销
2. **块 B（P3+P4）**：签到判定、CSV、当日状态与邮件策略
3. **块 C（P5+P6）**：历史滚动、`status`、调度（cron or APScheduler）
4. **块 D（P7+P8）**：失败分类与重试、文档打磨与移交

---

## 5) 测试计划（最小可执行）

* **授权路径**：正常授权；`revoke` 后再 `signin` 验证告警。
* **结果分支**：

  * 成功：模拟一次真实成功；再跑第二次验证“已签幂等”。
  * 失败：断网/改错选择器 → 产生 `network/unknown`；用无效 `storage_state` → `auth_invalid`。
  * 风控：手动触发验证码场景（若有）→ `risk_control`。
* **邮件策略**：同日多次成功只 1 封；多次失败多封。
* **滚动与状态**：造 2001 条（例）验证 FIFO；`status` 显示正确。
* **调度**：手动把 cron 时间改到近未来 1–2 分钟观察触发与邮件。

---

## 6) 运维与回滚

* **备份**：`config.toml`、`data/history.csv`、`data/daily_state.json`、`storage_state.json`。
* **迁移**：拷贝以上文件至新主机即可；若授权失效，重新 `authorize`。
* **回滚**：保留上一版代码与配置副本；问题时还原目录并恢复备份。

---

## 7) 角色分工（可自拟）

* **开发/实施**：代码与配置实现、选择器校准、调度上线。
* **验收/运维**：跑通 U1–U8、观察 1 天三时段邮件与 CSV 输出、出具验收结论。

---

### 附：cron 示例（Asia/Singapore）

```
0 9  * * * /usr/bin/python -m app.cli signin --slot=morning
0 14 * * * /usr/bin/python -m app.cli signin --slot=noon
0 21 * * * /usr/bin/python -m app.cli signin --slot=evening
```

需要的话，我可以**直接产出项目骨架与配置样例**（不含站点私密选择器），你只要补 SMTP 和 selectors 即可跑通。
