# 负责人 3：Interviewer AI 计划

## 目标

提供稳定、可评测的文本能力：从 JD 生成问题和参考答题框架，根据题目、参考答案、用户回答文本和多模态报告评价回答质量。

## 目录所有权

- 主写：`services/interviewer/**`
- 共同维护：`evals/interviewer/**`、Internal 契约。
- 不访问业务数据库、不读取音视频、不生成最终总报告。

## 两个能力

### Question Generation

- 提取岗位目标、核心能力和可验证成果。
- 生成恰好 `question_count` 道题。
- 至少覆盖 behavioral、technical/situational 中的两类。
- 问题不重复，每题给出 competencies、expected_signals、reference_answer 和 evaluation_rubric。
- reference_answer 给出多个合理逻辑切入点，不是唯一标准答案。
- evaluation_rubric 给出维度、权重、强/部分/缺失信号。

### Answer Evaluation

- 根据 JD、题目、reference_answer、evaluation_rubric、用户回答文本和 Multimodal report 评分。
- 内容占 70%，表达占 30%；表达只评估清晰度、结构、节奏和信息传达。
- 每条优点、改进和维度评分都要有回答文本或报告观察证据。
- 不把表情、动作或视线直接解释成情绪、人格、诚实度或心理状态。
- 报告缺失或证据不足时写入 limitations，不编造结论。

## 模型适配

- 业务逻辑只依赖 `ModelClient` 接口。
- 环境变量配置模型名称、Base URL、API Key 和超时。
- Prompt 放入版本化文件，例如 `prompts/question-v1.md`。
- 模型输出先经过 JSON Schema 校验，再返回给 API。

## 与其他模块的交互

- 只实现 `POST /internal/v1/question-sets:generate`。
- 只实现 `POST /internal/v1/content-evaluations`，接收结构化 Multimodal report，不接收视频文件。
- 服务不得把模型供应商错误原样返回；用标准 Internal 错误并保留 request_id。
- 任何字段变化先通知 API 负责人并修改共享契约。

## 第一版交付顺序

1. 固定 JSON Stub 服务。
2. 建 10 个 JD 和 20 个回答的最小评测集。
3. 接入一个文本模型完成问题生成。
4. 接入答案框架生成和综合评分，并做 Schema 重试一次。
5. 固定 Prompt 版本，记录评测结果。

## 验收

- 相同输入连续运行 3 次都返回合法结构。
- 问题数量始终准确、无明显重复。
- 不因回答语言为中文而输出英文反馈。
- 引用证据确实存在于 transcript。
- 同一回答不会因为采用不同但合理的答题路径而被判定为错误。
- 模型不可用时在超时范围内返回标准错误。
