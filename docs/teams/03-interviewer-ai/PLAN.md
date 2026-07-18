# 负责人 3：Interviewer AI 计划

## 目标

提供稳定、可评测的文本能力：从 JD 生成问题，并根据题目与 transcript 评价回答内容。

## 目录所有权

- 主写：`services/interviewer/**`
- 共同维护：`evals/interviewer/**`、Internal 契约。
- 不访问业务数据库、不读取音视频、不生成最终总报告。

## 两个能力

### Question Generation

- 提取岗位目标、核心能力和可验证成果。
- 生成恰好 `question_count` 道题。
- 至少覆盖 behavioral、technical/situational 中的两类。
- 问题不重复，每题给出 competencies 和 expected_signals。

### Content Evaluation

- 只根据 JD、问题、期望信号和 transcript 评分。
- 四个固定维度：relevance、specificity、structure、impact。
- 每条优点和改进都要能在 transcript 中找到依据。
- transcript 过短或无意义时允许返回 `null` 评分和理由。

## 模型适配

- 业务逻辑只依赖 `ModelClient` 接口。
- 环境变量配置模型名称、Base URL、API Key 和超时。
- Prompt 放入版本化文件，例如 `prompts/question-v1.md`。
- 模型输出先经过 JSON Schema 校验，再返回给 API。

## 与其他模块的交互

- 只实现 `POST /internal/v1/question-sets:generate`。
- 只实现 `POST /internal/v1/content-evaluations`。
- 服务不得把模型供应商错误原样返回；用标准 Internal 错误并保留 request_id。
- 任何字段变化先通知 API 负责人并修改共享契约。

## 第一版交付顺序

1. 固定 JSON Stub 服务。
2. 建 10 个 JD 和 20 个回答的最小评测集。
3. 接入一个文本模型完成问题生成。
4. 接入内容评分并做 Schema 重试一次。
5. 固定 Prompt 版本，记录评测结果。

## 验收

- 相同输入连续运行 3 次都返回合法结构。
- 问题数量始终准确、无明显重复。
- 不因 transcript 语言为中文而输出英文反馈。
- 引用证据确实存在于 transcript。
- 模型不可用时在超时范围内返回标准错误。
