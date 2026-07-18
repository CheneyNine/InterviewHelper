# 负责人 1：移动端 App 计划

## 技术栈选择

采用 React Native + Expo + TypeScript。

- Expo：快速创建 iOS/Android 工程，减少原生配置时间。
- `expo-router`：文件路由，页面和深链结构清晰。
- `expo-camera`：摄像头、麦克风权限和视频录制。
- `expo-file-system` / `expo/fetch`：本地媒体文件和 multipart 上传。
- TanStack Query：服务器状态、Job 轮询和缓存。
- Zustand：录制状态、当前题目、重录状态等本地状态。
- `expo-secure-store`：未来保存登录 token；MVP 不在客户端保存模型 Key。

## 目标

完成 JD → 问题 → 逐题录制 → 分析等待 → 报告的移动端完整用户流程。

## 目录所有权

- 主写：`apps/mobile/**`
- 可提案：`packages/contracts/**`、`docs/contracts/**`
- 禁止直接修改：`services/**`、`workers/**`

## 页面/路由

```text
app/
├── index.tsx                         # 输入岗位信息
├── interview/[id]/index.tsx          # 问题列表与当前问题
├── interview/[id]/record/[questionId].tsx # 录制/重录/上传
├── interview/[id]/analysis/[answerId].tsx # 单题分析
└── interview/[id]/report.tsx         # 整场报告
```

## 必须实现

- 首次进入请求摄像头和麦克风权限，并说明用途。
- 使用 `expo-camera` 录制 30 秒到 10 分钟的音视频。
- 用户点击“确认上传”后才上传；重录不产生服务端 Answer。
- 上传显示进度，切后台或网络中断时给出可重试状态。
- Job 每 2 秒轮询，App 进入后台时停止轮询，回到前台后恢复。
- 只依赖 Core API Public API，不直接访问 AI 服务。
- 不假设 delivery 中一定有视频指标，严格处理 `null` 和 `unavailable_reasons`。
- 展示“训练建议，不是心理或招聘结论”的提示。

## 与其他模块的交互

- 负责人 2 提供 API Base URL 和开发 Stub。
- 共享契约只从 `packages/contracts` 或生成的 TypeScript 类型导入。
- App 负责 UI 状态，不负责推断 Interview/Answer 状态。
- 媒体字段使用真实设备生成的 MIME；API 不能只按文件扩展名判断。

## 第一版交付顺序

1. Expo 空工程、路由和 Mock 页面。
2. 接 Core API Stub 跑通纯文本流程。
3. 真机权限、摄像头预览和本地录制。
4. multipart 上传、进度、重试和 App 生命周期处理。
5. 接入真实 Job 和报告，完成 Android/iOS 各一次演示。

## 验收

- iOS 和 Android 真机都能完成权限申请和 30 秒录制。
- 用户能预览、重录和确认上传。
- 切换页面或重启 App 后，能从 API 恢复会话进度。
- 后端返回 409、413、415、503 时都有明确提示。
- 使用固定 Stub 能完成一次全流程演示。

## 暂不做

- Web 端同步交付。
- 后台持续录制。
- App 内实时视频帧推理。
- 数字人、实时语音通话和推送通知。
