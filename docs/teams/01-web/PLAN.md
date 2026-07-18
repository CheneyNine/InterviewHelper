# 负责人 1：Web 前端计划

## 目标

在不直接了解模型内部实现的情况下，完成 JD → 问题 → 逐题录制 → 分析等待 → 报告的完整用户流程。

## 目录所有权

- 主写：`apps/web/**`
- 可提案：`packages/contracts/**`、`docs/contracts/**`
- 禁止直接修改：`services/**`、`workers/**`

## 页面

1. `/`：JD 输入、语言和问题数量。
2. `/interviews/{id}`：问题列表、当前题、录制与上传。
3. `/interviews/{id}/answers/{answerId}`：单题分析。
4. `/interviews/{id}/report`：整场报告。

## 必须实现

- 使用 `MediaRecorder`，优先 `video/webm`；不支持视频时允许 `audio/webm`。
- 清楚处理摄像头拒绝、麦克风拒绝、录制中断和上传失败。
- 所有 API 类型从共享契约生成或集中定义，页面内不复制接口类型。
- POST 生成 UUID `Idempotency-Key`，网络重试复用同一个键。
- Job 每 2 秒轮询；页面卸载后停止轮询。
- 展示“训练建议，不是心理或招聘结论”的提示。

## 与其他模块的交互

- 只依赖 Core API Public API。
- 向 API 负责人确认浏览器实际产生的 MIME 类型。
- 不假设分析必然包含视频指标；严格处理 `null` 和 `unavailable_reasons`。

## 第一版交付顺序

1. 用 Mock 数据完成四个页面。
2. 接入 API Stub，跑通纯文本流程。
3. 完成 30 秒录制、本地回放和 multipart 上传。
4. 完成 Job 轮询、错误重试和结果展示。
5. 与真实 AI 服务联调，不因字段缺失崩溃。

## 验收

- Chrome 中首次访问能完成权限申请。
- 用户能重录，只有最终确认的视频被上传。
- 刷新页面后能根据 Interview API 恢复进度。
- 后端返回 409、413、415、503 时都有明确提示。
- 使用固定 Stub 能完成一次全流程演示。
