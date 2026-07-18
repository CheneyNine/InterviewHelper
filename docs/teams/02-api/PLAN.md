# 负责人 2：Core API 计划

## 目标

成为系统的唯一业务入口和编排层：保存状态与文件，执行业务规则，调用两个 AI 模块，聚合稳定的 Public API。Core API 的价值不是“把 App 请求转发给模型”，而是保证面试会话、答案、任务、文件和报告在失败与重试时仍然一致。

详细职责见 [`CORE_API_GUIDE.md`](CORE_API_GUIDE.md)。

## 目录所有权

- 主写：`services/api/**`、`infra/**`
- 共同维护：`packages/contracts/**`、`docs/contracts/**`
- 禁止把业务持久化逻辑放进 AI 服务。

## 数据表

- `interviews`：JD、locale、question_count、status、last_error、timestamps。
- `questions`：interview_id、order、type、prompt、competencies JSON、expected_signals JSON。
- `answers`：question_id、media_uri、content_type、duration_ms、status、timestamps。
- `jobs`：type、resource_id、status、progress、error JSON、timestamps。
- `answer_analyses`：answer_id、transcript JSON、content JSON、delivery JSON、版本信息。

## 必须实现

- 完整 Public API、输入验证、状态机和标准错误。
- multipart 媒体上传；文件名由服务生成，绝不信任用户文件名。
- 内部 HTTP Client 设置连接/响应超时并透传 `X-Request-ID`。
- 幂等创建 Interview 和 Answer。
- 分析编排：Multimodal → transcript → Content Evaluation → 聚合。
- 删除 Interview 时清理关联数据和媒体。

## 与其他模块的交互

- 为 App 提供稳定 Public API 和第一天可用 Stub。
- 调用 Interviewer AI 的两个 Internal API。
- 调用 Multimodal 的一个 Internal API，只传受控媒体 URI。
- AI 返回不合法 JSON 时转换为 `MODEL_BAD_RESPONSE`，不能将原始异常直接泄露给 App。

## 第一版交付顺序

1. 建立模型、迁移和状态机单元测试。
2. 实现所有 Public API 的固定结果 Stub。
3. 实现文件上传和本地存储。
4. 接入两个 Internal Stub。
5. 实现后台分析编排与失败重试。
6. 替换成真实服务并完成删除流程。

## 验收

- OpenAPI 可访问，示例与共享契约一致。
- 重复幂等请求不会生成重复数据或文件。
- 服务重启后已完成数据仍可查询。
- 一个 AI 模块停机不会导致 API 进程崩溃。
- 删除测试验证数据库记录和媒体都不可再访问。
- App 断网重试不会产生重复 Interview 或 Answer。
- 任意一个 AI 服务失败时，Core API 仍能查询原始会话并提供重试入口。
