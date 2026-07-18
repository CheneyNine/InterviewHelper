# Core API MVP

该服务负责 Public API、Job 状态、题目/回答/分析结果保存和两个 AI 服务的编排。

```bash
cd services/api
pip install -r requirements.txt
INTERVIEWER_BASE_URL=http://127.0.0.1:8001 \
  uvicorn app.main:app --reload --port 8000
```

Public API：

```text
POST /api/v1/interviews
GET  /api/v1/interviews/{interview_id}
GET  /api/v1/jobs/{job_id}
POST /api/v1/questions/{question_id}/answers
GET  /api/v1/answers/{answer_id}/analysis
GET  /api/v1/interviews/{interview_id}/report
```

VLM 完成报告后，将单题 JSON 送入以下内部适配接口；Core API 会自动映射逐字稿、语音/视频证据和限制，再调用 Interviewer 单题评估：

```text
POST /internal/v1/reports:ingest
```

这是 MVP 的内存实现，重启会丢失 Interview、Job 和分析结果；接入数据库和对象存储前只用于联调。
