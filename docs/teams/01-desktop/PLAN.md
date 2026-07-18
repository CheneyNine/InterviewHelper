# 负责人 1：桌面端 Mac App 计划

## 技术栈选择

采用 Tauri 2 + React + Vite + TypeScript，第一版只发布 macOS `.app`。

- Tauri 2：使用系统 WebView 打包桌面应用，体积和启动开销比 Electron 更小，也保留以后 Windows/Linux 的可能性。
- React + Vite：团队可以复用 TypeScript、组件和 API Client 开发经验。
- 浏览器媒体 API：在 Tauri 的 macOS WebKit WebView 中使用 `getUserMedia`、`MediaRecorder` 录制摄像头和麦克风。
- TanStack Query：服务器状态、Job 轮询和缓存。
- Zustand：录制状态、当前题目、上传状态等本地状态。
- Rust/Tauri Commands：MVP 只用于安全文件路径、系统权限和必要的原生能力；不要把业务逻辑放进 Rust。

## macOS 权限和打包

- `src-tauri/Info.plist` 必须声明 `NSCameraUsageDescription` 和 `NSMicrophoneUsageDescription`。
- `src-tauri/Entitlements.plist` 配置摄像头和音频输入 entitlement。
- 在真实 Mac 上测试权限拒绝、重新授权、外接摄像头和耳机麦克风。
- 使用 `npm run tauri build -- --bundles app` 生成 `.app`。
- MVP 不做 App Store 发布；先用本地 `.app` 或签名后的内部测试包。

## 目标

完成 JD → 问题 → 逐题录制 → 分析等待 → 报告的 Mac 桌面端完整用户流程。

## 目录所有权

- 主写：`apps/desktop/**`
- 可提案：`packages/contracts/**`、`docs/contracts/**`
- 禁止直接修改：`services/**`、`workers/**`

## 页面/路由

```text
apps/desktop/src/
├── pages/JobInput.tsx
├── pages/Interview.tsx
├── pages/AnswerAnalysis.tsx
├── pages/InterviewReport.tsx
├── components/AnswerRecorder.tsx
├── hooks/useAnswerRecorder.ts
├── lib/api.ts
└── store/interviewStore.ts
```

## 必须实现

- 首次进入说明录制用途，并请求 macOS 摄像头和麦克风权限。
- 使用 `getUserMedia` + `MediaRecorder` 录制 30 秒到 10 分钟的音视频。
- 用户点击“确认上传”后才上传；重录不产生服务端 Answer。
- 本地预览、录制计时、停止、重录和上传进度完整可见。
- 网络中断时保留本地临时文件，并允许重新上传；不能重复创建 Answer。
- Job 每 2 秒轮询，窗口失焦时可以暂停轮询，恢复时重新拉取状态。
- 只依赖 Core API Public API，不直接访问 AI 服务。
- 不假设 delivery 中一定有视频指标，严格处理 `null` 和 `unavailable_reasons`。
- 展示“训练建议，不是心理或招聘结论”的提示。

## 与其他模块的交互

- 负责人 2 提供 API Base URL 和开发 Stub。
- 共享契约只从 `packages/contracts` 或生成的 TypeScript 类型导入。
- App 负责 UI 状态，不负责推断 Interview/Answer 状态。
- 媒体字段使用真实 Mac 生成的 MIME；API 不能只按文件扩展名判断。

## 第一版交付顺序

1. Tauri + React 空工程、窗口和 Mock 页面。
2. 接 Core API Stub 跑通纯文本流程。
3. 真实 Mac 权限、摄像头预览和本地录制。
4. multipart 上传、进度、重试和窗口生命周期处理。
5. 接入真实 Job 和报告，完成 Intel Mac 和 Apple Silicon Mac 各一次测试。

## 验收

- macOS 真机能完成权限申请和 30 秒录制。
- 用户能预览、重录和确认上传。
- 重启 App 后能从 API 恢复会话进度。
- 后端返回 409、413、415、503 时都有明确提示。
- 使用固定 Stub 能完成一次全流程演示。
- 执行 `tauri build --bundles app` 能生成可打开的 `.app`。

## 暂不做

- 移动端和 Web 端同步交付。
- 后台持续录制。
- App 内实时视频帧推理。
- 数字人、实时语音通话和 App Store 发布。
