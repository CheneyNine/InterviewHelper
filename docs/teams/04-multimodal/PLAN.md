# 负责人 4：Multimodal 分析计划

## 目标

从一段回答媒体中提取可解释、带时间证据的转写与表达指标；缺失模态时优雅降级。

## 目录所有权

- 主写：`workers/multimodal/**`
- 共同维护：`evals/multimodal/**`、Internal 契约。
- 不访问业务数据库、不生成内容评分、不判断心理状态。

## MVP 指标

### 必做音频

- transcript 与时间片段。
- words_per_minute。
- pause_ratio。
- filler_count，中文至少支持“嗯、呃、然后、就是”。
- 长停顿和异常快速语段的时间证据。

### 可选视频

- offscreen_face_ratio：画面中检测不到人脸的帧比例。
- head_motion：仅作为相对运动量，不映射到情绪。
- 视频无法分析时写入 `unavailable_reasons`，不得使整题失败。

## 实现约束

- 使用 ffmpeg 统一抽取 16kHz mono WAV。
- 视频以低帧率采样，MVP 建议 2 FPS，避免逐帧大模型推理。
- 时间统一为相对回答开始的毫秒。
- URI 只允许 API 配置的本地根目录或允许域名，防止 SSRF/任意文件读取。
- 临时文件用独立临时目录并在任务结束后清理。

## 与其他模块的交互

- 只实现 `POST /internal/v1/media-analyses`。
- 返回 transcript 和 delivery，不返回 content。
- 所有观察必须包含 code、时间段、confidence 和中性描述。
- 不输出“焦虑、不自信、撒谎、性格”等标签。

## 第一版交付顺序

1. 对任意合法 WebM 返回固定 Stub。
2. ffmpeg 解码与文件安全校验。
3. 接入 ASR，输出 transcript segments。
4. 实现音频指标与单元测试。
5. 实现可选人脸可见率；失败时降级。
6. 用至少 10 段不同设备录制的样本验证。

## 验收

- macOS 真机录制的 WebM 或 MP4 可正常处理。
- 纯音频文件仍能完成分析。
- 无人脸视频不会导致 500。
- 指标范围、时间段和单位符合契约。
- 恶意 `file:///etc/...` 或非允许域名 URI 被拒绝。
- 日志不包含 transcript 全文或媒体 URI 的查询密钥。
