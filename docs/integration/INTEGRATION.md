# 四模块联调计划

## 1. 联调原则

- 每个模块先对 Stub 完成契约测试，再与真实模块联调。
- 任何人不能要求其他模块读取自己的内部数据库或内部 Python/TypeScript 类型。
- 跨模块只传 `docs/contracts/API_CONTRACT.md` 中定义的数据。
- Core API 负责人担任第一轮集成负责人，但无权单方面改字段。

## 2. 并行开发所需 Stub

### API 给 Mac App 的 Stub

API 负责人第一个工作日提供：创建会话、查询会话、上传回答、查询 Job、查询报告。分析可以固定延迟 3 秒后返回示例数据。Mac App 不需要等待真实模型即可开发。

### Interviewer AI Stub

AI 负责人提供固定 5 题和固定内容评分。Core API 可通过 `INTERVIEWER_BASE_URL` 切换 Stub/真实服务。

### Multimodal Stub

多模态负责人先对任意合法媒体返回一段固定 transcript 和 delivery 数据。Core API 可通过 `MULTIMODAL_BASE_URL` 切换 Stub/真实服务。

## 3. 推荐合并顺序

1. 契约、状态机与 Docker Compose 基础。
2. Core API Stub + Mac App 文字流程。
3. Mac App 真实录制上传 + API 文件持久化。
4. Interviewer AI 真实问题生成。
5. Multimodal 真实转写与音频指标。
6. Interviewer AI 真实内容评分。
7. 报告聚合、删除与错误重试。

## 4. 端到端验收场景

### Happy path

1. 输入至少 100 字 JD。
2. 30 秒内看到 5 道问题。
3. 录制并上传一段 30 秒 WebM。
4. Job 从 `QUEUED` 进入 `RUNNING`，最终 `SUCCEEDED`。
5. 分析页同时展示 transcript、内容反馈和表达反馈。
6. 完成全部问题后能看到总报告。

### Failure path

- 上传 `.txt` 返回 `415 UNSUPPORTED_MEDIA_TYPE`。
- 同一 `Idempotency-Key` 重传不会创建两条 Answer。
- Multimodal 停机时 Job 最终失败，Mac App 显示重试入口。
- 视频中无人脸时音频与内容结果仍然可用。
- 删除 Interview 后其查询接口返回 404，媒体不可访问。

## 5. 每日同步格式

每人每天只同步以下四项：

```text
完成：已合并或可演示的功能
接口：新增/变更/等待确认的契约
阻塞：需要哪个负责人提供什么
今天：下一项可验收结果
```

## 6. Definition of Done

- 实现符合 v1 契约。
- 正常、失败、边界场景至少各有一个测试。
- README 包含启动命令和环境变量。
- 不提交密钥或真实用户媒体。
- 日志无敏感内容。
- 另一位组员在新环境能按文档运行。
