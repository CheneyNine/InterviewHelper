# 面试分析数据契约（八维评分）

## 评分模型

所有分数在后端使用 `0～1`，桌面端展示时乘以 100。八个评分方向固定为：

| 分组 | key | 含义 | 权重 |
|---|---|---|---:|
| 表现维度 | `visible_expression` | 神情与镜头表现 | 0.10 |
| 表现维度 | `content_and_fluency` | 回答内容与流畅程度 | 0.15 |
| 表现维度 | `tone_and_voice` | 语气与声音表现 | 0.10 |
| 表现维度 | `answer_structure` | 回答结构与题目呈现 | 0.15 |
| 回答质量 | `relevance` | 题目相关性 | 0.15 |
| 回答质量 | `technical_depth` | 专业准确性与技术深度 | 0.15 |
| 回答质量 | `evidence_and_contribution` | 证据与个人贡献 | 0.10 |
| 回答质量 | `role_fit` | 岗位匹配度与业务理解 | 0.10 |

综合分是有效维度按权重重新归一化后的加权平均。证据不足返回 `null`，不能当作 0 分。

## Core API 返回给桌面端

### `GET /api/v1/answers/{answer_id}/analysis`

桌面端需要加载：

- `answer_id`
- `question`：题目及参考答题思路
- `reference_answer`：参考答案结构
- `actual_answer`：用户语音转写文本
- `transcript`：带时间段的转写
- `content.overall_score`
- `content.dimension_scores`：八个 key 的分数
- `content.dimension_analysis`：八个维度的总结、证据、建议和限制
- `content.strengths`
- `content.improvements`
- `content.transcript_evaluation`：只基于转写文本的分析
- `content.reference_comparison`：与参考答案对照的分析
- `delivery.metrics`、`delivery.observations`、`delivery.unavailable_reasons`
- `video`：可观察的视频证据
- `observable_state`：证据充分性和限制

桌面端不需要加载 `raw_multimodal_report`；它仅用于后端审计、重放和问题排查。

### `GET /api/v1/interviews/{interview_id}/report`

桌面端需要加载：

- `interview_id`
- `question_count`、`completed_count`
- `overall_score`
- `dimension_scores`：八维雷达图数据
- `summary`：综合整体表现总结，其中包含跨题重复趋势
- `strengths`
- `priority_improvements`
- `practice_plan`
- `dimension_analysis`：八维整体解释（可用于雷达图旁的摘要）
- `answer_analyses`：逐题详情入口
- `disclaimer`、`limitations`

跨题趋势不再单独作为字段或页面模块，由 `summary`、`strengths` 和 `priority_improvements` 综合表达。

## 仅后端保留的数据

以下数据用于模型调用、追踪、审计或故障排查，不直接进入桌面端主要界面：

- 原始视频和媒体二进制内容
- `raw_multimodal_report`
- 模型名称、Prompt 版本、请求追踪 ID
- VLM 原始观察帧信息
- 内部任务队列状态和 GPU 路由信息
- 数据库内部的更新时间、幂等键和错误堆栈

## 内部 Interviewer API

- `POST /internal/v1/content-evaluations`：生成八维综合评分和单题反馈
- `POST /internal/v1/transcript-evaluations`：只分析语音转写文本
- `POST /internal/v1/reference-comparisons`：将转写与参考答案进行对照
- `POST /internal/v1/interview-reports:generate`：生成整场总结、优势、改进和八维整体说明

## 兼容原则

旧的 `content_score`、`delivery_score` 和旧版 `dimensions` 不再作为桌面端主评分字段。数据库中已有历史分析可以继续读取，但新生成结果统一使用 `overall_score`、`dimension_scores` 和 `dimension_analysis`。
