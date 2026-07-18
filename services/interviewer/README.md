# Interviewer AI

负责人 3 的工作区。开始前阅读 [`../../docs/teams/03-interviewer-ai/PLAN.md`](../../docs/teams/03-interviewer-ai/PLAN.md) 和 [`../../docs/contracts/API_CONTRACT.md`](../../docs/contracts/API_CONTRACT.md)。

该服务当前已实现“根据 JD 生成问题”的第一版：

```bash
cd services/interviewer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

环境变量从仓库根目录 `.env` 读取：

```env
VAPI=your-bearer-token
URL=https://your-openai-compatible-host/v1
MODEL=your-model-name
MODEL_API_STYLE=auto
VAPI_ASSISTANT_ID=  # 只有 Vapi Chat Responses 需要时填写
MODEL_TIMEOUT_SECONDS=60
```

`URL` 可以是 API Base URL，也可以是完整的 `/chat/completions`、`/chat/responses` 或 `/messages` URL。若 OpenAI-compatible 网关只填写域名，服务会自动补全 `/v1/chat/completions`；`MODEL_API_STYLE` 支持 `auto`、`openai`、`responses`、`anthropic`，服务会自动补全路径。

调用示例：

```bash
curl -X POST http://localhost:8001/internal/v1/question-sets:generate \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: demo-request-001' \
  -d '{
    "job_title": "电商算法实习生",
    "job_description": "负责推荐与流量分发算法，支持直播业务和用户商品匹配。",
    "job_requirements": "机器学习基础扎实，熟悉算法与数据结构，有推荐、搜索或大模型项目经验。",
    "interview_stage": "技术面",
    "question_count": 5,
    "locale": "zh-CN"
  }'
```

模型输出会先经过 Pydantic 校验；如果 JSON、题目数量或 `order` 不符合要求，服务会自动发起一次修复请求，第二次仍失败则返回 `502 MODEL_BAD_RESPONSE`。
