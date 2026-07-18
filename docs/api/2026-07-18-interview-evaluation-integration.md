# 面试评估对接说明

本文给前端、Core API 和 Interviewer 服务使用，描述一次完整模拟面试中会产生哪些报告、哪些接口，以及接口调用时机。

## 一、报告类型

### 1. 单题多模态分析报告

每道题的视频上传并完成 VLM 分析后生成。内容包括：

- 题目和参考答题思路
- 用户实际语音转写（含时间片段）
- 八维评分：四个表现维度 + 四个回答质量维度
- 单题综合分
- 每个维度的分数、证据、说明、建议和限制
- 可观察的视频表现、声音指标和镜头证据
- 优势、不足和下一步建议

八个评分方向固定为：

| 分组 | key | 说明 |
|---|---|---|
| 表现维度 | `visible_expression` | 神情与镜头表现 |
| 表现维度 | `content_and_fluency` | 回答内容与流畅程度 |
| 表现维度 | `tone_and_voice` | 语气与声音表现 |
| 表现维度 | `answer_structure` | 回答结构与题目呈现 |
| 回答质量 | `relevance` | 题目相关性 |
| 回答质量 | `technical_depth` | 专业准确性与技术深度 |
| 回答质量 | `evidence_and_contribution` | 证据与个人贡献 |
| 回答质量 | `role_fit` | 岗位匹配度与业务理解 |

### 2. 转写文本分析报告

只使用语音转文字结果，不使用参考答案，也不判断技术事实是否正确。主要分析：

- 是否切题
- 清晰度
- 流畅度
- 结构完整性
- 原文中的优势、不足、证据和改进建议

### 3. 参考答案对照报告

将用户转写与该题的参考答题思路、逻辑路径和评分标准进行比较。主要包括：

- 参考思路覆盖情况
- 已覆盖的关键点
- 缺失的关键点
- 内容匹配度和正确性判断
- 改进后的答题结构
- 面向下一次回答的具体建议

### 4. 整场综合报告

所有题目分析完成后生成。内容包括：

- 整场综合分
- 八维雷达图分数
- 综合整体表现总结
- 整体优势
- 优先改进项
- 训练计划
- 八个维度的整体解释
- 逐题分析入口
- 分析限制和免责声明

跨题表现趋势不单独作为页面模块，而是合并到“综合整体表现总结”“整体优势”和“优先改进项”中。

## 二、调用链和调用时机

```text
Desktop App
  → Core API
  → Interviewer / VLM
  → Core API 保存分析结果
  → Desktop App 读取报告
```

### 阶段 A：生成面试题

桌面端调用：

```http
POST /api/v1/interviews
```

Core API 创建面试项目和问题生成任务，之后由 Interviewer 调用大模型生成问题、参考答题思路和评分标准。

### 阶段 B：上传单题视频

用户切换题目或结束录制时，桌面端调用：

```http
POST /api/v1/questions/{question_id}/answers
```

Core API 保存视频，返回 `answer_id` 和分析 `job_id`。桌面端通过：

```http
GET /api/v1/jobs/{job_id}
```

轮询任务状态和进度。

### 阶段 C：VLM 分析视频

Core API 内部调用 VLM 服务，获得：

- 语音转写
- 语音指标
- 视频帧和镜头证据
- 可观察表现描述

VLM 结果通过内部接口进入 Core API：

```http
POST /internal/v1/reports:ingest
```

### 阶段 D：生成单题八维综合分析

Core API 将题目、参考答案、转写和 VLM 报告发送给 Interviewer：

```http
POST /internal/v1/content-evaluations
```

该接口负责生成八维评分、单题优势、不足、证据、建议和限制。

### 阶段 E：生成转写文本分析和参考答案对照

Core API 同时调用两个辅助接口：

```http
POST /internal/v1/transcript-evaluations
POST /internal/v1/reference-comparisons
```

前者只看转写文本，后者同时使用转写文本和参考答案。两者结果与单题综合分析一起保存。

### 阶段 F：读取单题报告

桌面端打开某道题的详情时调用：

```http
GET /api/v1/answers/{answer_id}/analysis
```

桌面端主要读取：

- `question`
- `reference_answer`
- `actual_answer`
- `transcript`
- `content.overall_score`
- `content.dimension_scores`
- `content.dimension_analysis`
- `content.transcript_evaluation`
- `content.reference_comparison`
- `delivery`
- `video`

### 阶段 G：生成整场报告

所有回答完成后，桌面端调用：

```http
GET /api/v1/interviews/{interview_id}/report
```

Core API 会：

1. 聚合所有单题八维分数。
2. 计算八维平均分和综合分。
3. 调用 Interviewer：

```http
POST /internal/v1/interview-reports:generate
```

4. 保存整场报告并返回给桌面端。

## 三、评分约定

- 后端分值范围：`0～1`
- 前端展示范围：`0～100`
- 雷达图字段：`dimension_scores`
- 证据不足：分数返回 `null`，不得当作 0 分
- 综合分：对有效维度按权重重新归一化加权平均

## 四、前端不需要处理的数据

以下数据只留在 Core API 或数据库中：

- 原始视频二进制
- `raw_multimodal_report`
- 模型名和 Prompt 版本
- GPU 路由、任务队列内部字段
- 请求追踪 ID、幂等键和内部错误详情

