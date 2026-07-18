# ADR-0001：模块化单仓库与 Core API 编排

## Status

Accepted for MVP

## Context

四名开发者需要并行工作，并在约十天内完成可演示闭环。完全单体容易发生文件冲突；微服务和消息队列会增加部署与排错成本。

## Decision

使用单仓库、四个清晰目录。Web 只调用 Core API，Core API 通过内部 HTTP 调用两个 AI 服务。第一版任务可进程内后台执行，保留以后替换 Redis 队列的边界。

## Consequences

### Positive

- 责任清晰，可用 Stub 并行开发。
- 一个 Docker Compose 即可本地运行。
- 模型可替换，不影响 Web API。

### Negative

- 仍需维护三个 Python 进程。
- Core API 是编排单点，需要充分测试。

## Alternatives Considered

- 单一进程：启动最快，但四人容易互相阻塞且模型代码污染业务层。
- 完整微服务 + Redis/Kafka：扩展性更强，但超出 MVP 需要。
