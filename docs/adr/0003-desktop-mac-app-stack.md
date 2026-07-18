# ADR-0003：MVP 使用 Tauri 2 + React 构建 Mac App

## Status

Accepted for MVP

## Context

产品交付形态是电脑 App，第一优先平台为 macOS。团队已有 TypeScript/HTTP 模块规划，需要快速实现 JD 输入、摄像头/麦克风录制、上传和报告展示。未来可能支持 Windows，但当前不需要同时维护多个原生 UI。

## Decision

使用 Tauri 2 + React + Vite + TypeScript。Mac App 的业务界面和 API Client 使用 React；Tauri 负责 `.app` 打包与系统窗口；Rust 只承载必要的原生命令。录制优先使用 WebKit WebView 中的 `getUserMedia` 和 `MediaRecorder`，复杂原生媒体能力留到后续。

## Consequences

### Positive

- 复用 TypeScript 组件和 API 类型，四人协作成本较低。
- 打包体积和资源占用通常低于 Electron。
- 将来可以复用 React 代码构建 Windows/Linux 版本。
- 摄像头/麦克风权限、`.app` bundle 和 entitlements 有明确边界。

### Negative

- macOS WebKit 与 Chromium 的媒体 API 行为可能不同，必须用真实 Mac 验证。
- 需要配置 `Info.plist`、entitlements、签名和权限说明。
- 若以后需要深度音视频采集，可能增加 Swift/Rust 原生插件。

## Alternatives Considered

### Electron + React

生态和媒体 API 调试经验较多，但包体积、内存占用和 Mac 原生感通常不如 Tauri；MVP 没有必须使用 Chromium 的功能，因此暂不选择。

### SwiftUI + AVFoundation

Mac 原生权限和摄像头/音频能力最好，但会引入 SwiftUI、Swift 网络层和 TypeScript 前端两套实现，四人并行速度较慢；暂不选择。

### React Native macOS

可以共享 React Native 生态，但 macOS 目标和桌面窗口/媒体能力的集成复杂度高于 Tauri；暂不选择。
