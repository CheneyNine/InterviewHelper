# Interviewer AI

负责人 3 的工作区。开始前阅读 [`../../docs/teams/03-interviewer-ai/PLAN.md`](../../docs/teams/03-interviewer-ai/PLAN.md) 和 [`../../docs/contracts/API_CONTRACT.md`](../../docs/contracts/API_CONTRACT.md)。

该服务当前已实现两项能力：

1. 根据 JD 生成问题、参考答题思路和题目级评分标准。
2. 根据题目、参考答案、用户回答文本和多模态报告生成综合评估。

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
URL1=https://primary-openai-compatible-host
URL2=https://backup-openai-compatible-host
MODEL=your-model-name
MODEL_API_STYLE=auto
VAPI_ASSISTANT_ID=  # 只有 Vapi Chat Responses 需要时填写
MODEL_TIMEOUT_SECONDS=120
MODEL_FAILOVER_DELAY_SECONDS=15

# 可选：切换到 ECNU 多 Key 轮换模式
MODEL_PROVIDER=ecnu
ECNU_API_KEYS="
main=your-key-1
backup-a=your-key-2
backup-b=your-key-3
"
ECNU_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1
ECNU_MODEL=ecnu-reasoner
```

优先使用 `URL1`，`URL1` 在 `MODEL_FAILOVER_DELAY_SECONDS` 内没有成功返回时启动 `URL2`；第一个返回合法结果的地址获胜。没有 `URL1/URL2` 时兼容旧的 `URL`。两个请求可能同时消耗模型额度，请根据供应商成本把延迟窗口调大。`URL` 可以是 API Base URL，也可以是完整的 `/chat/completions`、`/chat/responses` 或 `/messages` URL；若 OpenAI-compatible 网关只填写域名，服务会自动补全 `/v1/chat/completions`。

当 `MODEL_PROVIDER=ecnu` 时，服务使用 `ECNU_BASE_URL` 和 `ECNU_MODEL`，按 `ECNU_API_KEYS` 中的顺序调用 Key；任一 Key 返回 HTTP 429 后立即切换下一个 Key。支持 JSON 数组、逗号分隔，或上面这种带名称的多行格式。所有 Key 都触发 429 时返回 `MODEL_RATE_LIMITED`。

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

综合评估接口：

```text
POST http://localhost:8001/internal/v1/content-evaluations
```

评估请求中的 `multimodal_report.answer_text` 是用户回答文本，其他字段用于传入语音、表情、动作和时间段观察。服务不接收原始视频，也不直接判断心理状态。
