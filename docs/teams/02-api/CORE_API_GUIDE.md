# Core API 具体职责说明

Core API 是 App 与两个 AI 模块之间的“业务控制层”。负责人 2 不需要训练模型，但必须保证所有模块能安全、可重复、可恢复地协作。

## 1. Core API 负责什么

### A. 面试会话管理

- 接收岗位名称、职位描述、职位要求、面试环节和题目数量。
- 创建唯一 `interview_id`。
- 调用 Interviewer AI 生成问题并保存为 `questions`。
- 控制会话状态：`GENERATING_QUESTIONS`、`QUESTIONS_READY`、`IN_PROGRESS`、`ANALYZING`、`COMPLETED`、`FAILED`。
- 防止同一会话重复生成或覆盖已确认的问题。

### B. 回答与媒体管理

- 接收 App 上传的音频/视频文件。
- 校验 MIME、大小、时长和文件是否可解码。
- 生成服务端文件名和 `answer_id`，不信任 App 上传的文件名。
- 保存媒体元数据和受控 `media_uri`，不把原始文件塞进数据库。
- 处理断网重试和 `Idempotency-Key`，保证重复上传不会产生重复 Answer。

### C. 任务编排

- 为问题生成和回答分析创建 `Job`。
- 依次调用 Multimodal：媒体 → transcript/delivery。
- 再调用 Interviewer AI：JD + question + transcript → content evaluation。
- 聚合两个结果为 `AnswerAnalysis`。
- 根据所有题目的完成情况生成 `InterviewReport`。
- 给 App 提供可轮询的 `GET /jobs/{job_id}`。

### D. 失败、重试和恢复

- 统一把内部异常转换成共享错误码，不把 API Key、模型原始响应或文件路径返回给 App。
- 对网络超时、服务暂时不可用执行有限重试。
- 对模型坏 JSON执行一次修复或重试。
- 服务重启后仍能从数据库恢复未完成 Job。
- 允许用户只重试失败的单题，不重新录制其他题。

### E. 数据与隐私边界

- Core API 是数据库、ID、状态和原始媒体地址的唯一所有者。
- 不在日志中记录 JD 全文、回答全文、Authorization、签名 URL。
- 实现删除 Interview 的级联清理。
- 只把必要的 transcript、评分、指标返回给 App。

## 2. Core API 不负责什么

- 不设计 Prompt，不选择面试题内容。
- 不直接调用 VAPI、Claude 或其他模型供应商。
- 不从视频判断“焦虑”“不自信”等心理状态。
- 不在 App 内实现最终评分逻辑。
- 不让 Interviewer AI 或 Multimodal 直接连接业务数据库。

## 3. 典型请求链路

```text
App
  │ POST /interviews
  ▼
Core API 创建 Interview + Job
  │ POST /internal/v1/question-sets:generate
  ▼
Interviewer AI 返回 QuestionSet
  │ Core API 校验并保存
  ▼
App 展示问题并上传 Answer
  │ POST /questions/{id}/answers
  ▼
Core API 保存媒体 + 创建分析 Job
  │ POST /internal/v1/media-analyses
  ▼
Multimodal 返回 transcript + delivery
  │ POST /internal/v1/content-evaluations
  ▼
Interviewer AI 返回 content
  │ Core API 聚合
  ▼
App 轮询 Job 并展示 AnswerAnalysis/Report
```

## 4. 负责人 2 的最小代码目录

```text
services/api/app/
├── main.py                 # FastAPI 入口
├── routes/
│   ├── interviews.py       # 会话、问题、报告
│   ├── answers.py          # 上传和答案
│   └── jobs.py             # 状态轮询和重试
├── db/
│   ├── models.py           # Interview/Question/Answer/Job/Analysis
│   └── session.py          # 数据库连接与事务
├── clients/
│   ├── interviewer.py      # 内部 AI Client
│   └── multimodal.py       # 内部多模态 Client
├── storage/
│   └── media.py            # 本地/MinIO 存储抽象
└── domain/
    ├── state_machine.py    # 状态转移
    ├── orchestration.py    # 分析流程
    └── errors.py           # 共享错误映射
```

## 5. Core API 负责人每天可交付的结果

- 第一天：Public API Stub 和状态机测试。
- 第二天：数据库模型、创建会话和问题查询。
- 第三天：媒体上传、MIME/大小校验和幂等键。
- 第四天：两个 Internal Stub 的调用编排。
- 第五天：失败重试、Job 轮询和报告聚合。
- 第六天：删除、恢复、日志脱敏和 App 联调。

## 6. Core API 验收问题

负责人 2 必须能回答：

1. App 重复点击提交会不会创建两条答案？
2. Multimodal 超时后用户怎么重试？
3. API 重启后未完成任务如何恢复？
4. 一个题目分析失败时，其他题目是否仍然可见？
5. 用户删除会话后，原始视频和分析结果是否都不可访问？
