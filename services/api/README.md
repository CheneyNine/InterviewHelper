# Core API

负责人 2 的工作区。开始前阅读 [`../../docs/teams/02-api/PLAN.md`](../../docs/teams/02-api/PLAN.md) 和 [`../../docs/contracts/API_CONTRACT.md`](../../docs/contracts/API_CONTRACT.md)。

该服务是状态、ID、数据库和媒体位置的唯一所有者。

问题生成联调入口必须是：

```text
Desktop App
  -> POST /api/v1/interviews
Core API
  -> POST {INTERVIEWER_BASE_URL}/internal/v1/question-sets:generate
Interviewer AI
  -> Prompt + model provider
```

`POST /api/v1/interviews` 必须接收并保存 `job_title`、`job_description`、`job_requirements`、`interview_stage`、`question_count` 和 `locale`，再由 Core API 生成 `request_id`/`X-Request-ID` 调用 Interviewer。禁止 Desktop App 直接调用 Interviewer 的 Internal API。
