# 四人协作总览

## 分工原则

四个人不是按“前端、后端、算法、另一个算法”模糊分工，而是按四个可以独立验收的产品模块分工。每个人都有自己的代码目录、输入、输出和验收标准。

| 人员 | 模块 | 负责的最终结果 | 不负责 |
| --- | --- | --- | --- |
| 1 | Desktop Mac App | 用户能在 macOS 上输入 JD、录制、上传、看报告 | 模型调用、数据库状态推断、最终评分逻辑 |
| 2 | Core API | 数据、状态、文件、任务和错误在各种失败情况下保持一致 | Prompt、音视频算法、UI |
| 3 | Interviewer AI | 根据岗位与环节生成问题，并对 transcript 做内容评分 | 文件上传、用户会话、视频指标 |
| 4 | Multimodal | 从媒体得到 transcript、音频指标、有限视频指标和时间证据 | 业务数据库、问题生成、招聘或心理判断 |

## 依赖关系

```text
负责人 1 Desktop Mac App ──Public API──> 负责人 2 Core API
                                      │
                                      ├──Internal API──> 负责人 3 Interviewer AI
                                      └──Internal API──> 负责人 4 Multimodal
```

## 每个人的交付物

### 负责人 1：Desktop Mac App

- Tauri + React 工程和页面路由。
- macOS 摄像头/麦克风权限、录制、预览、重录、上传进度。
- Core API Client 和错误状态 UI。
- Intel Mac、Apple Silicon Mac 各一次完整演示。

### 负责人 2：Core API

- OpenAPI 和公共接口。
- 数据库模型、迁移、状态机、幂等和文件存储。
- 两个内部 AI Client 和分析任务编排。
- Job 轮询、重试、删除和恢复。

### 负责人 3：Interviewer AI

- JD/岗位要求/面试环节到问题集的 Prompt。
- 结构化 JSON 校验和模型适配器。
- transcript 到内容评分的 Prompt 和评测集。
- 模型超时、坏 JSON 和版本记录。

### 负责人 4：Multimodal

- ffmpeg 解码、ASR、时间片段。
- 语速、停顿、填充词和视频质量指标。
- 缺失音频/视频时的降级结果。
- 指标单元测试和无敏感信息的样本评测集。

## 接口变更规则

1. 任何人先修改 `docs/contracts/`，不能先改自己的代码再通知别人。
2. 调用方和提供方各审查一次。
3. 先改 Stub 和契约测试，再改真实实现。
4. 不允许跨模块直接读数据库、共享内部类型或复制模型密钥。
5. 每日同步“完成、接口、阻塞、今天”，由 Core API 负责人维护集成状态。
