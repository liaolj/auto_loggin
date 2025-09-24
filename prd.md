下面是把**已确认的 MVP 需求**与**Python+Playwright 技术方案**整合后的**技术开发文档**。它既可用于团队评审，也可直接指导实现与验收。

# anyrouter.top 自动签到（Python + Playwright）技术开发文档（MVP）

## 0. 术语

* **授权/登录**：通过 GitHub OAuth 完成身份确认并在 anyrouter.top 建立会话。
* **签到**：登录态下触发 anyrouter.top 的每日打卡动作。
* **时段**：每日早/中/晚三次计划执行窗口。
* **MVP**：最小可用版本（能跑通、可验收）。

---

## 1) 目标与范围

### 1.1 目标

* 使用**单一 GitHub 账号**，在**早/中/晚三次**计划时段自动完成 anyrouter.top 当日签到。
* 成功当日仅发 **1 封成功邮件**；**每次失败**都发失败邮件。
* 历史记录按**条数**滚动保留。

### 1.2 范围

* **In**：授权绑定/校验、三时段计划触发、登录与签到、幂等判定、邮件通知、历史记录（按条数滚动）、授权撤销与清理。
* **Out**：绕过站点/平台规则、自动处理验证码/强风控、除邮件外的其他通知渠道、多账号支持。

---

## 2) 业务规则与验收对象

### 2.1 业务规则

1. **时区**：`Asia/Singapore`。
2. **计划时段（每日三次）**：早/中/晚固定时刻触发（默认 09:00 / 14:00 / 21:00，可配）。
3. **成功判定**：站点可验证的“成功/已签到”标识（接口响应或 DOM 文案）。
4. **幂等**：当日已签到时，其后时段执行记为“已签到（幂等成功）”，**不再发送成功邮件**。
5. **通知策略**：

   * 成功：当日**首次成功** → 发送 **1 封成功邮件**；
   * 失败：任一时段失败 → **立即发送失败邮件**；
   * 人工介入（验证码/风控/授权失效）：仅邮件提示。
6. **历史记录**：每次触发与结果均写入；超过上限按先入先出删除旧记录。
7. **安全**：本地凭据**无需**口令/二次确认；支持随时撤销授权并清理本地凭据（记录审计事件）。

### 2.2 用户故事（MVP）

* 我能完成**首次 GitHub 授权绑定**并看到授权有效。
* 系统在**早/中/晚**三个时段**自动尝试签到**。
* 当日任一时段成功后，后续时段**幂等成功**，仅记录不再发成功邮件。
* 我收到**成功/失败邮件**（按上面的通知规则）。
* 我可以查看**最近 N 条**历史与**当日状态**。
* 我可以**撤销授权并清理凭据**。

---

## 3) 技术方案总览

* **语言/库**：Python + Playwright（Chromium）。
* **运行形态**：CLI 工具（`authorize` / `signin` / `schedule` / `status` / `revoke`）。
* **会话策略**：一次**人工授权**（headed 浏览器）→ 导出 `storage_state.json` → 定时签到使用 headless 复用会话。
* **结果判定**：优先基于**网络响应**（JSON/状态码）；无可用响应时回退**DOM 文案**。
* **调度**：三次/日；二选一

  * OS 级（cron / systemd timer）
  * 应用内（APScheduler）
* **通知**：SMTP 发邮件（当日仅 1 封成功；每次失败都发）。
* **数据持久**：

  * 历史：CSV（滚动按条数上限）。
  * 状态：`daily_state.json`（当日唯一成功邮件/统计）；`storage_state.json`（会话）。

---

## 4) 系统架构与模块

### 4.1 模块与文件

```
anyrouter-auto/
  ├─ app/
  │  ├─ cli.py                 # 命令入口
  │  ├─ config.py              # 配置加载（TOML/ENV）
  │  ├─ runner.py              # 执行编排：授权检查→登录→签到→记录→通知
  │  ├─ auth.py                # authorize（导出 storage_state）/ revoke（清理）
  │  ├─ signin.py              # Playwright 自动化与结果判定
  │  ├─ selectors.py           # 站点选择器与判定规则（可配置）
  │  ├─ history.py             # CSV 历史与 daily_state.json 管理
  │  ├─ notify.py              # SMTP 邮件发送与模板
  │  ├─ scheduler.py           # APScheduler（可选）
  │  └─ utils.py               # 时间/重试/异常分类等
  ├─ config.sample.toml        # 示例配置
  └─ README.md
```

### 4.2 架构与流程图

```mermaid
flowchart TD
  subgraph S[调度层]
    C1[Cron/Timer]:::node -->|命令行| R1[cli signin --slot=morning]
    C2[APScheduler]:::node -->|应用内触发| R2[runner.call_signin(slot)]
  end

  subgraph E[执行层]
    A[加载配置/时区] --> B{授权有效?}
    B -- 否 --> B1[失败: 授权失效] --> N1[发失败邮件] --> H
    B -- 是 --> P[Playwright(headless) 复用 storage_state]
    P --> L[打开 anyrouter.top]
    L --> Q{会话有效?}
    Q -- 否 --> B1
    Q -- 是 --> D[尝试签到: 点击按钮/调用接口]
    D --> J{成功 or 已签到?}
    J -- 是 --> K[写历史 + 当日唯一成功邮件判定]
    J -- 否 --> F[分类失败] --> N1
    K --> H[更新 daily_state 并结束]
  end
  classDef node fill:#1f2937,stroke:#94a3b8,color:#e5e7eb,rx:8,ry:8;
```

---

## 5) 关键流程（需求级 → 技术落地）

### 5.1 一次性授权 `authorize`

* 启动 **headed** 浏览器 → 打开 anyrouter → 引导点 GitHub 登录 → 用户完成 GitHub 登录/2FA → 回到 anyrouter（检测头像/标记）→ **导出 `storage_state.json`**。
* 若服务器无 UI：在本地授权后复制 `storage_state.json` 至服务器相同路径。

### 5.2 定时签到 `signin`

* 启动 **headless** 浏览器 + 传入 `storage_state.json`。
* 若直接被带到 GitHub 登录页 → 视为**授权失效**。
* 否则，执行签到动作：

  * 优先监听 **接口响应**（如 `/api/checkin`）；判定 `success`/`already` 字段或 message。
  * 无法监听时回退 **DOM 文案**（关键字配置在 `selectors`）。
* 写入 CSV 历史；根据 `daily_state.json` 决定是否发送当日唯一成功邮件。

### 5.3 幂等与当日唯一成功邮件

* `daily_state.json` 字段：`date`、`has_success_mail_sent`、`first_success_time`、`fail_count_today`。
* 日期变更自动重置；“已签到”记为幂等成功，不再发成功邮件。

### 5.4 调度（任选其一）

* **cron 示例**（Asia/Singapore）

  ```
  # 09:00 / 14:00 / 21:00
  0 9  * * * /usr/bin/python -m app.cli signin --slot=morning
  0 14 * * * /usr/bin/python -m app.cli signin --slot=noon
  0 21 * * * /usr/bin/python -m app.cli signin --slot=evening
  ```
* **systemd timer**：定义三个 `*.timer` 对应 `*.service`，ExecStart 调用 `signin --slot=...`。
* **APScheduler**：`schedule` 子命令内以 `CronTrigger` 注册三条任务，进程常驻。

---

## 6) 配置文件规范（TOML 草案）

`config.sample.toml`

```toml
[app]
timezone = "Asia/Singapore"
history_max_rows = 2000
data_dir = "./data"                # 保存 CSV / state 文件

[schedule]
morning = "09:00"
noon    = "14:00"
evening = "21:00"

[mail]
smtp_host = "smtp.example.com"
smtp_port = 465
username  = "bot@example.com"
password  = "APP_PASSWORD"
from      = "anyrouter-bot <bot@example.com>"
to        = "you@example.com"

[selectors.dom]
login_with_github = "text=Sign in with GitHub"
checkin_button    = ["text=签到", "text=Check in"]  # 支持多候选，按顺序匹配
success_keywords  = ["签到成功","已签到","Checked in", "Check-in successful"]
failure_keywords  = ["失败","错误","failed"]

[selectors.api]
checkin_path_contains = "/api/checkin"  # 若有
success_keys          = ["success","message"]
already_keywords      = ["already","已签到"]
```

> 选择器与判定规则独立成配置，站点微调时仅改配置，无需改代码。

---

## 7) 数据模型与文件

### 7.1 历史记录 CSV（逐行追加，超上限 FIFO）

字段：

```
timestamp_local,date,slot,stage,result,err_category,err_summary,http_status,duration_ms,mail_sent
```

* `result`：`success` / `already` / `failure`
* `err_category`：`network|dns|tls|timeout|http4xx|http5xx|auth_invalid|risk_control|unknown`
* `mail_sent`：`none|success|failure`

### 7.2 当日状态 `daily_state.json`

```json
{
  "date": "2025-09-24",
  "has_success_mail_sent": true,
  "first_success_time": "2025-09-24T09:03:15+08:00",
  "fail_count_today": 1
}
```

### 7.3 会话 `storage_state.json`

* 由 Playwright `context.storage_state()` 导出；只存放 cookie/localStorage 等会话信息。

---

## 8) CLI 接口规范

* `authorize`：打开 headed 浏览器完成一次授权并导出 `storage_state.json`。
* `signin --slot {morning|noon|evening}`：执行一次签到（便于 OS 调度）。
* `schedule`：进程内三定时任务（APScheduler）。
* `status [--last N]`：打印最近 N 条历史 + 今日状态。
* `revoke`：清理 `storage_state.json` 与本地授权痕迹（保留历史 CSV），下次执行会提示需重新授权。

---

## 9) 失败分类与处理策略（MVP）

| 分类                      | 判定依据                        | 处理与通知                    |
| ----------------------- | --------------------------- | ------------------------ |
| network/dns/tls/timeout | 请求异常/超时                     | 记失败并发邮件                  |
| http4xx/http5xx         | 响应码                         | 记失败并发邮件                  |
| auth\_invalid           | 跳转至 GitHub 登录页/关键 cookie 缺失 | 记失败并发邮件，提示运行 `authorize` |
| risk\_control           | 出现验证码/异常拦截                  | 记失败并发邮件，提示人工介入           |
| unknown                 | 其他未归类异常                     | 记失败并发邮件（附堆栈摘要）           |

> MVP 轻量重试建议：失败后等待 \~15s 再试 1 次；仍失败则走失败流程。

---

## 10) 邮件模板（占位符版）

### 10.1 成功（当日仅 1 封）

* **Subject**：`[AnyRouter] 签到成功 - {{date}} {{slot}}`
* **Body**：

  * 时间：`{{timestamp_local}}`（{{slot}}）
  * 结果：签到成功（或当日首次成功）
  * 首次成功时间（若为当日首次）：`{{first_success_time}}`
  * 站点返回摘要：`{{message}}`

### 10.2 失败（每次失败都发）

* **Subject**：`[AnyRouter] 签到失败 - {{date}} {{slot}} - {{err_category}}`
* **Body**：

  * 时间：`{{timestamp_local}}`（{{slot}}）
  * 分类：`{{err_category}}`
  * 摘要：`{{err_summary}}`（HTTP: {{http\_status}}）
  * 建议：

    * `auth_invalid` → 请运行 `authorize` 重新授权
    * `risk_control` → 请人工在浏览器完成验证
    * 其他 → 稍后关注是否连续失败超阈

---

## 11) 部署与运行手册（最小步骤）

1. **安装依赖**：Python 3.11+，`pip install playwright` 并执行 `playwright install chromium`。
2. **初始化工程**：拷贝 `config.sample.toml` 为 `config.toml`，按需填写 SMTP、时间等。
3. **首次授权**：`python -m app.cli authorize`（headed）→ 成功后生成 `storage_state.json`。
4. **本地试跑**：`python -m app.cli signin --slot=morning`（观察历史与邮件）。
5. **接入调度**：

   * 选择 **cron/systemd**（推荐）或 **`python -m app.cli schedule`**（APScheduler）。
6. **日常运维**：

   * 查看状态：`python -m app.cli status --last 50`
   * 授权失效：重跑 `authorize`
   * 迁移：复制 `storage_state.json` + `config.toml` + `data/`（CSV/状态）到新环境。

---

## 12) 验收用例（MVP）

| 用例 | 场景      | 期望                                                     |
| -- | ------- | ------------------------------------------------------ |
| U1 | 首次授权绑定  | 状态为“有效”，产生审计记录（历史 CSV 一条 `stage=authorize`）            |
| U2 | 早场成功    | 写成功记录并**发送 1 封成功邮件**；当日状态 `has_success_mail_sent=true` |
| U3 | 中/晚场已签  | 写“已签到（幂等）”；**不再发成功邮件**                                 |
| U4 | 某时段失败   | 写失败记录并**发送失败邮件**                                       |
| U5 | 早失败→中成功 | 早场发失败邮件；中场成功触发**当天唯一成功邮件**                             |
| U6 | 授权失效    | 该时段失败并**发邮件提示需重新授权**                                   |
| U7 | 历史满上限   | 新纪录写入，最旧记录被删除（FIFO）                                    |
| U8 | 撤销授权    | 清理会话并记录审计事件；后续执行提示需重新授权并发失败邮件                          |

---

## 13) 选择器/判定配置（示例）

> 实际以页面为准，以下仅示意。

```toml
[selectors.dom]
login_with_github = "text=Sign in with GitHub"
checkin_button    = ["button:has-text('签到')", "button:has-text(\"Check in\")"]
success_keywords  = ["签到成功","今日已签到","Checked in", "Check-in successful"]
failure_keywords  = ["失败","错误","重试","failed"]

[selectors.api]
checkin_path_contains = "/api/checkin"
success_keys          = ["success","message"]
already_keywords      = ["already","已签到"]
```

---

### 附注

* 本文去除了“非功能性需求”章节，**仅保留 MVP 必需项**以保证文档简洁且需求明确。
* 后续若要增强（多账号、失败降噪、SQLite、容器化等），在此文档基础上增量扩展即可。
