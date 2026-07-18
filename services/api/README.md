# Core API

该服务负责 Public API、Job 状态、题目/回答/分析结果保存和两个 AI 服务的编排。
Interview、题目、视频切片、分析结果、后台 Job 和最终报告均保存到 SQLite。

```bash
cd services/api
pip install -r requirements.txt
INTERVIEWER_BASE_URL=http://127.0.0.1:8001 \
VLM_BASE_URL=http://127.0.0.1:8002 \
  uvicorn app.main:app --reload --port 8000
```

常用配置：

```text
DATABASE_PATH=./data/interview_helper.db
MAX_MEDIA_BYTES=209715200
VLM_API_STYLE=openai
VLM_MODEL=Qwen3-Omni-30B-A3B-Instruct
VLM_TIMEOUT_SECONDS=900
VLM_USE_AUDIO_IN_VIDEO=true
VLM_GPU_IDS=0,1,2,3
```

- 当 `VLM_API_STYLE=recording` 时，调用兼容旧逻辑的
  `POST /recording-analyses`。
- 当 `VLM_API_STYLE=openai` 时，调用
  `POST /v1/chat/completions`，将数据库视频作为
  OpenAI-compatible `video_url` 发送给 Qwen3-Omni。
- `VLM_GPU_IDS` 显式指定 VLM 可用卡，最多使用前 4 张；只有一张卡时填写 `0`。
- 未设置时，Core API 会读取 `CUDA_VISIBLE_DEVICES`；仍未设置时用 `nvidia-smi`
  选择空闲显存不少于 80% 的卡。
- Core API 为每个并行请求发送 `X-GPU-ID` 请求头；旧 `recording` 模式还会发送
  `gpu_id` 表单字段。VLM 服务若支持按请求路由，可据此选择 worker；标准 vLLM
  通常由服务端自身负责 tensor parallel 和调度。
- Core API 所在机器没有 GPU 时仍启动一个调度 worker，交由远端 VLM 自行选择设备。

回答上传完成后，视频已经进入数据库，随即返回 `202`。后台 worker 会继续分析，
因此桌面端可以直接切换到下一题或其他项目。服务异常重启后，状态为 `QUEUED` 或
`RUNNING` 的回答分析 Job 会自动恢复。

Public API：

```text
POST /api/v1/interviews
GET  /api/v1/interviews/{interview_id}
GET  /api/v1/jobs/{job_id}
POST /api/v1/questions/{question_id}/answers
GET  /api/v1/answers/{answer_id}/analysis
GET  /api/v1/interviews/{interview_id}/report
```

VLM 完成报告后，也可将单题 JSON 送入以下内部适配接口；Core API 会自动映射逐字稿、语音/视频证据和限制，再调用 Interviewer 单题评估：

```text
POST /internal/v1/reports:ingest
```

整场报告首次生成后会写入 `interview_reports` 表，后续读取直接返回数据库缓存。

多台电脑共用同一远端模型时，不应在每台电脑配置模型 Key 或 SSH 隧道。推荐把
Core API 和 Interviewer 服务部署到远端服务器，只对客户端暴露 Core API；模型
端口与密钥保留在服务器内部。完整拓扑见
[`../../docs/deployment/CENTRAL_MODEL_GATEWAY.md`](../../docs/deployment/CENTRAL_MODEL_GATEWAY.md)。
