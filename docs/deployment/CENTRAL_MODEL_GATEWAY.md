# 统一远端模型调用

## 推荐拓扑

```text
Desktop A ─┐
Desktop B ─┼─ HTTPS/LAN ─> Core API ─┬─> Interviewer ─> ECNU Chat
Desktop C ─┘                         └─> Qwen3-Omni OpenAI API
```

只有 Core API 和 Interviewer 读取模型地址、模型名和 API Key。桌面端不直接访问
ECNU 或 Qwen，也不保存任何模型凭据。

## 服务端配置

在运行 Core API 的服务器上配置：

```dotenv
DATABASE_PATH=/srv/interview-helper/data/interview_helper.db
INTERVIEWER_BASE_URL=http://127.0.0.1:8001

# 如果 Core API 与 Omni 在同一服务器，使用服务器内部地址，不使用客户端 SSH 隧道。
VLM_BASE_URL=http://127.0.0.1:8002/v1
VLM_API_STYLE=openai
VLM_API_KEY=<server-secret>
VLM_MODEL=Qwen3-Omni-30B-A3B-Instruct
VLM_USE_AUDIO_IN_VIDEO=true
VLM_TIMEOUT_SECONDS=900
```

在运行 Interviewer 的服务器上配置 ECNU：

```dotenv
MODEL_PROVIDER=ecnu
ECNU_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1
ECNU_MODEL=ecnu-reasoner
ECNU_API_KEYS=<server-secret-key-list>
```

`MODEL_PROVIDER=ecnu` 时不会调用 Claude 兼容的 `URL1`/`URL2`。这些备用配置可以
保留在服务器密钥系统中，但不应下发到桌面端。

## 桌面端配置

所有客户端只配置同一个 Core API 地址：

```dotenv
VITE_USE_STUB=false
VITE_API_BASE_URL=https://<core-api-domain>/api/v1
```

如果只在校园网或 VPN 内使用，也可以使用服务器局域网地址。不要填写
`127.0.0.1`，除非 Core API 确实运行在每台客户端本机。

## 网络入口

要彻底避免每台电脑分别建立 SSH 隧道，必须为 Core API 提供一个所有客户端都能
访问的统一入口。推荐优先级：

1. Nginx/Caddy HTTPS 反向代理到服务器 `127.0.0.1:8000`。
2. 在可信校园网/VPN 中映射一个宿主机端口到 Core API。
3. 无法开放端口时才让每台电脑分别建立 SSH 隧道。

只暴露 Core API。Omni 的 OpenAI API 端口、Interviewer 端口和数据库端口应继续
保持内网可见。

## Omni 请求协议

Core API 的 `openai` 模式调用：

```text
POST <VLM_BASE_URL>/chat/completions
Authorization: Bearer <server-secret>
```

视频以 OpenAI-compatible 内容块发送：

```json
{
  "model": "Qwen3-Omni-30B-A3B-Instruct",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "video_url",
          "video_url": {
            "url": "data:video/webm;base64,<video-bytes>"
          }
        },
        {
          "type": "text",
          "text": "分析模拟面试回答并返回结构化 JSON"
        }
      ]
    }
  ],
  "modalities": ["text"],
  "mm_processor_kwargs": {
    "use_audio_in_video": true
  }
}
```

## 多 GPU

Qwen3-Omni 30B 通常由远端推理服务负责模型级并行。若一个模型实例跨四张 GPU，
应在远端 vLLM/vLLM-Omni 启动配置中设置四卡 tensor parallel 或对应 stage
配置。Core API 的 1–4 个 worker 控制的是并发请求数，不会替代模型服务器本身的
多卡部署。

如果需要四个独立模型副本并行处理四段视频，则应在远端启动四个副本，并由反向
代理或模型网关进行负载均衡；单个模型实例忽略 `X-GPU-ID` 时，Core API 无法从
客户端强制指定 CUDA 设备。

## 凭据安全

- `.env` 已被 Git 忽略；只提交 `.env.example`。
- 生产环境优先使用 systemd `EnvironmentFile`、Docker secrets 或集群 Secret。
- 不在桌面端、前端构建变量、日志或接口响应中放置模型 API Key。
- 曾经通过聊天、截图或公开日志发送过的密码和 Key 应立即轮换。
