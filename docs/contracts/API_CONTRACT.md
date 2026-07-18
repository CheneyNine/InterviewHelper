# API 与数据契约 v1

这是四个模块共同遵守的唯一接口真相源。实现代码可以生成 OpenAPI，但不得与本文档冲突。

## 1. 通用规则

- Public Base URL：`/api/v1`
- Internal Base URL：`/internal/v1`
- JSON 字段使用 `snake_case`。
- 时间使用 ISO 8601 UTC，例如 `2026-07-17T20:30:00Z`。
- ID 是 UUID 字符串。
- Public POST 接受 `Idempotency-Key`；同一键和相同请求体必须返回同一资源。
- 每个响应带 `X-Request-ID`，内部调用必须透传该值。
- 未注明的字段一律不可依赖；新增字段必须保持向后兼容。

## 2. 核心类型

### Interview

```json
{
  "id": "0b02b3d8-1854-4c95-a407-93d4ed6e8256",
  "job_description": "We are looking for...",
  "locale": "zh-CN",
  "question_count": 5,
  "status": "QUESTIONS_READY",
  "created_at": "2026-07-17T20:30:00Z",
  "updated_at": "2026-07-17T20:30:12Z"
}
```

### Question

```json
{
  "id": "45047222-a0b0-45b9-8f57-91f5589759e7",
  "interview_id": "0b02b3d8-1854-4c95-a407-93d4ed6e8256",
  "order": 1,
  "type": "behavioral",
  "prompt": "请讲述一次你处理高优先级线上故障的经历。",
  "competencies": ["problem_solving", "ownership"],
  "expected_signals": ["明确个人行动", "量化影响", "复盘措施"]
}
```

`type` 仅允许：`behavioral`、`technical`、`situational`。

### Answer

```json
{
  "id": "e742b2ae-9db0-4796-a8dc-1e8b6584ee3d",
  "question_id": "45047222-a0b0-45b9-8f57-91f5589759e7",
  "status": "PROCESSING",
  "duration_ms": 87320,
  "media_content_type": "video/webm",
  "created_at": "2026-07-17T20:40:00Z"
}
```

### Job

```json
{
  "id": "c8b47af2-4391-4c23-905c-4ec0c48c3324",
  "type": "ANSWER_ANALYSIS",
  "status": "RUNNING",
  "resource_id": "e742b2ae-9db0-4796-a8dc-1e8b6584ee3d",
  "progress": 0.4,
  "error": null,
  "created_at": "2026-07-17T20:40:01Z",
  "updated_at": "2026-07-17T20:40:18Z"
}
```

## 3. Public API：Mobile App 只调用这些接口

### `POST /api/v1/interviews`

创建会话并同步返回；问题生成由后台启动。

Request：

```json
{
  "job_description": "string，20 到 12000 字符",
  "locale": "zh-CN",
  "question_count": 5
}
```

Response：`201 Created`

```json
{
  "interview": { "id": "uuid", "status": "GENERATING_QUESTIONS" },
  "job": { "id": "uuid", "type": "QUESTION_GENERATION", "status": "QUEUED" }
}
```

### `GET /api/v1/interviews/{interview_id}`

Response：`200 OK`

```json
{
  "interview": { "id": "uuid", "status": "QUESTIONS_READY" },
  "questions": [],
  "answers": []
}
```

状态尚未就绪时数组可以为空，但字段必须存在。

### `POST /api/v1/questions/{question_id}/answers`

Content-Type：`multipart/form-data`

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `media` | file | 是 | `video/webm`、`video/mp4` 或 `audio/webm` |
| `duration_ms` | integer | 是 | 1000 到 600000 |
| `recorded_at` | string | 是 | ISO 8601 UTC |

最大文件大小由配置控制，开发默认 100 MB。Response：`202 Accepted`

```json
{
  "answer": { "id": "uuid", "status": "PROCESSING" },
  "job": { "id": "uuid", "type": "ANSWER_ANALYSIS", "status": "QUEUED" }
}
```

### `GET /api/v1/jobs/{job_id}`

用于每 2 秒轮询。Response 为 `Job`。`progress` 在 `0.0` 到 `1.0` 之间，无法计算时为 `null`。

### `GET /api/v1/answers/{answer_id}/analysis`

任务未完成返回 `409 ANALYSIS_NOT_READY`。成功返回：

```json
{
  "answer_id": "uuid",
  "transcript": {
    "text": "我当时首先……",
    "language": "zh-CN",
    "segments": [
      { "start_ms": 0, "end_ms": 1840, "text": "我当时首先", "confidence": 0.93 }
    ]
  },
  "content": {
    "overall_score": 0.76,
    "dimensions": {
      "relevance": 0.84,
      "specificity": 0.72,
      "structure": 0.70,
      "impact": 0.66
    },
    "strengths": ["明确说明了个人行动"],
    "improvements": ["补充结果的量化数据"],
    "evidence": [
      { "claim": "个人行动清晰", "quote": "我负责回滚并协调数据库检查" }
    ]
  },
  "delivery": {
    "metrics": {
      "words_per_minute": 168.2,
      "pause_ratio": 0.19,
      "filler_count": 7,
      "offscreen_face_ratio": 0.08
    },
    "observations": [
      {
        "code": "FAST_SPEECH_SEGMENT",
        "start_ms": 32000,
        "end_ms": 46000,
        "confidence": 0.81,
        "message": "这一时间段语速明显快于本题平均值。"
      }
    ],
    "suggestions": ["回答结论后停顿一秒，再补充背景。"],
    "unavailable_reasons": []
  }
}
```

### `GET /api/v1/interviews/{interview_id}/report`

所有已提交答案完成后返回 `200`；否则返回 `409 REPORT_NOT_READY`。

```json
{
  "interview_id": "uuid",
  "summary": "回答与岗位总体相关，结果量化仍可加强。",
  "overall_content_score": 0.74,
  "top_strengths": ["个人职责表达清楚"],
  "priority_improvements": ["用数字说明影响", "降低长句中的语速"],
  "answer_analyses": [
    { "question_id": "uuid", "answer_id": "uuid", "analysis_url": "/api/v1/answers/uuid/analysis" }
  ],
  "disclaimer": "这些结果是训练建议，不是心理、医学或招聘结论。"
}
```

### `DELETE /api/v1/interviews/{interview_id}`

删除业务记录和关联原始媒体。成功返回 `204 No Content`。MVP 可以异步清理文件，但 API 返回后用户必须无法继续访问资源。

## 4. Internal API：只有 Core API 调用

### `POST /internal/v1/question-sets:generate`

Interviewer AI 提供。

```json
{
  "request_id": "uuid",
  "job_title": "电商算法实习生",
  "job_description": "string",
  "job_requirements": "string",
  "interview_stage": "技术面",
  "locale": "zh-CN",
  "question_count": 5
}
```

Response：

```json
{
  "questions": [
    {
      "order": 1,
      "type": "behavioral",
      "prompt": "string",
      "purpose": "string",
      "competencies": ["ownership"],
      "expected_signals": ["string"],
      "follow_up_questions": ["string"]
    }
  ],
  "model": "configured-model-name",
  "prompt_version": "question-v1"
}
```

### `POST /internal/v1/content-evaluations`

Interviewer AI 提供。不得接收视频文件。

```json
{
  "request_id": "uuid",
  "job_description": "string",
  "question": {
    "prompt": "string",
    "competencies": ["ownership"],
    "expected_signals": ["string"]
  },
  "transcript": "string",
  "locale": "zh-CN"
}
```

返回 Public `AnswerAnalysis.content` 对象，外加 `model` 和 `prompt_version`。

### `POST /internal/v1/media-analyses`

Multimodal 提供。MVP 中 `media_uri` 是仅内部可访问的绝对路径或短期签名 URL。

```json
{
  "request_id": "uuid",
  "answer_id": "uuid",
  "media_uri": "file:///data/uploads/answer.webm",
  "media_content_type": "video/webm",
  "duration_ms": 87320,
  "locale": "zh-CN"
}
```

返回：

```json
{
  "transcript": {
    "text": "string",
    "language": "zh-CN",
    "segments": []
  },
  "delivery": {
    "metrics": {},
    "observations": [],
    "suggestions": [],
    "unavailable_reasons": []
  },
  "analyzer_version": "multimodal-v1"
}
```

## 5. 契约变更流程

1. 提交只修改契约的 PR。
2. 调用方和提供方各一人批准。
3. 先更新 Stub 和契约测试。
4. 再合并真实实现。
5. 删除或改名字段必须创建 `/v2`，不能直接破坏 v1。
