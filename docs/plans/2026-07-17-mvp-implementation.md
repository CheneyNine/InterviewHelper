# InterviewHelper MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 四人并行实现 JD 生成问题、逐题音视频回答、离线多模态分析和训练报告的最小可演示闭环。

**Architecture:** 单仓库中由 Mobile App 调用 Core API；Core API 持久化状态并编排两个内部 AI 服务。模块通过版本化 HTTP/JSON 契约隔离，先用 Stub 完成联调，再逐一替换真实模型。

**Tech Stack:** React Native + Expo/TypeScript、Expo Router、TanStack Query、Zustand、FastAPI/Python、SQLAlchemy、SQLite→PostgreSQL、HTTPX、ffmpeg、Docker Compose。

---

## 里程碑 0：当天完成契约冻结

### Task 1: 初始化仓库与质量门禁

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `.github/workflows/ci.yml`

**Steps:**

1. 初始化 Git，并创建受保护的 `main` 分支。
2. 添加 Python、Node、媒体文件和密钥忽略规则。
3. 添加不含真实密钥的环境变量样例。
4. CI 先运行 Markdown 链接检查，随后由各模块添加测试命令。
5. 提交 `chore: initialize MVP monorepo`。

### Task 2: 将契约变成可执行 Schema

**Files:**
- Create: `packages/contracts/openapi.yaml`
- Create: `packages/contracts/schemas/question.json`
- Create: `packages/contracts/schemas/content-evaluation.json`
- Create: `packages/contracts/schemas/media-analysis.json`
- Test: `packages/contracts/tests/test_examples.py`

**Steps:**

1. 从 `docs/contracts/API_CONTRACT.md` 提取三个 JSON Schema。
2. 为文档中的成功示例写校验测试并先观察失败。
3. 完成 Schema，使所有成功示例通过。
4. 添加缺字段、越界评分和非法状态的失败样例。
5. 提交 `feat: add executable API contracts`。

## 里程碑 1：两天内跑通无模型闭环

### Task 3: Core API Stub

**Files:**
- Create: `services/api/app/main.py`
- Create: `services/api/app/routes/interviews.py`
- Create: `services/api/app/routes/answers.py`
- Create: `services/api/app/routes/jobs.py`
- Test: `services/api/tests/test_public_api.py`

**Steps:**

1. 为创建会话、查询会话、上传回答、查询 Job 和查询报告写失败测试。
2. 实现内存版数据存储和固定 5 题。
3. Job 在测试配置中立即完成，在开发配置中延迟 3 秒。
4. 验证错误响应和幂等行为。
5. 提交 `feat(api): add public MVP stub`。

### Task 4: Mobile App 纵向流程

**Files:**
- Create: `apps/mobile/app/index.tsx`
- Create: `apps/mobile/app/interview/[id]/index.tsx`
- Create: `apps/mobile/app/interview/[id]/report.tsx`
- Create: `apps/mobile/src/lib/api.ts`
- Test: `apps/mobile/src/lib/api.test.ts`

**Steps:**

1. 为 Public API Client 写响应解析和错误测试。
2. 完成 JD 表单并创建 Interview。
3. 完成问题显示和文本占位回答。
4. 完成 Job 轮询和报告展示。
5. 用 Core API Stub 录制一次端到端屏幕演示。
6. 提交 `feat(mobile): complete stub interview flow`。

## 里程碑 2：第四天完成真实录制与两个内部 Stub

### Task 5: 媒体录制和上传

**Files:**
- Create: `apps/mobile/src/components/AnswerRecorder.tsx`
- Create: `apps/mobile/src/hooks/useAnswerRecorder.ts`
- Create: `services/api/app/storage/media.py`
- Test: `services/api/tests/test_media_upload.py`

**Steps:**

1. 测试 API 拒绝非法 MIME、超大和空文件。
2. 实现安全文件名、本地写入和元数据持久化。
3. 实现真机录制、重录、本地预览和 multipart 上传。
4. 用 iOS/Android 生成的真实媒体跑上传测试。
5. 提交 `feat: record and upload interview answers`。

### Task 6: 内部服务 Stub 与编排

**Files:**
- Create: `services/interviewer/app/main.py`
- Create: `workers/multimodal/app/main.py`
- Create: `services/api/app/clients/interviewer.py`
- Create: `services/api/app/clients/multimodal.py`
- Test: `services/api/tests/test_analysis_orchestration.py`

**Steps:**

1. 写编排成功、超时和坏 JSON 测试。
2. 两个内部服务返回符合 Schema 的固定数据。
3. API 按 Multimodal → Interviewer → 聚合顺序调用。
4. 实现 request_id 透传和标准错误映射。
5. 提交 `feat(api): orchestrate analysis services`。

## 里程碑 3：第七天替换核心真实能力

### Task 7: 真实问题生成和内容评分

**Files:**
- Create: `services/interviewer/app/model_client.py`
- Create: `services/interviewer/prompts/question-v1.md`
- Create: `services/interviewer/prompts/content-v1.md`
- Test: `services/interviewer/tests/test_structured_outputs.py`

**Steps:**

1. 用 Fake ModelClient 测试 JSON 解析和 Schema 拒绝。
2. 实现供应商无关的 ModelClient。
3. 接入一个可用文本模型并设置温度与超时。
4. 非法结构只重试一次，仍失败则返回标准错误。
5. 跑固定评测集并保存 Prompt 版本。
6. 提交 `feat(ai): generate and evaluate interview content`。

### Task 8: 真实转写和音频指标

**Files:**
- Create: `workers/multimodal/app/media.py`
- Create: `workers/multimodal/app/transcribe.py`
- Create: `workers/multimodal/app/audio_metrics.py`
- Test: `workers/multimodal/tests/test_audio_metrics.py`

**Steps:**

1. 为 URI 白名单和 ffmpeg 失败写测试。
2. 抽取 16kHz mono WAV 并接入 ASR。
3. 对人工构造时间片段测试语速、停顿和填充词。
4. 输出 observations 的起止时间和置信度。
5. 用 10 段真实设备样本验证，不提交真实用户数据。
6. 提交 `feat(mm): transcribe and analyze answer delivery`。

## 里程碑 4：第十天完成 Demo 质量

### Task 9: 持久化、删除和恢复

**Files:**
- Create: `services/api/app/db/models.py`
- Create: `services/api/app/db/session.py`
- Create: `services/api/migrations/`
- Test: `services/api/tests/test_delete_and_recovery.py`

**Steps:**

1. 为重启恢复和级联删除写失败测试。
2. 用 SQLAlchemy 替换内存存储。
3. 实现 Interview、媒体和分析结果删除。
4. 验证服务重启后的查询和重试。
5. 提交 `feat(api): persist and delete interview data`。

### Task 10: 端到端与演示验收

**Files:**
- Create: `evals/e2e/test_happy_path.py`
- Create: `evals/e2e/test_failure_paths.py`
- Create: `docs/DEMO.md`

**Steps:**

1. 自动化完整 Happy path。
2. 覆盖不支持媒体、模型停机、无人脸和重复上传。
3. 清理日志中的敏感字段。
4. 在一台新机器按 README 启动并完成演示。
5. 冻结 Demo 使用的模型、Prompt 和配置版本。
6. 提交 `test: verify MVP end-to-end flow`。

## 四人并行节奏

| 天 | Mobile App | Core API | Interviewer AI | Multimodal |
| --- | --- | --- | --- | --- |
| 1 | 页面 Mock | Public Stub | Internal Stub | Internal Stub |
| 2 | 接 Public Stub | 文件接口 | 评测集/Prompt | ffmpeg/样本 |
| 3-4 | 真机录制上传 | 持久化/编排 | 真实问题生成 | ASR |
| 5-7 | 报告/错误态 | 真实服务联调 | 内容评分 | 音频指标 |
| 8-10 | E2E/体验 | 删除/恢复 | 稳定性 | 降级/性能 |

计划实施时，每个 Task 使用独立 PR；先合并契约，再合并依赖该契约的模块。
