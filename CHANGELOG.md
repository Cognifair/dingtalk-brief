# Changelog

## v1.0.1 — 2026-10-19

- 明确来源：本地读取链路基于 [dingtalk-chat-exporter](https://github.com/idealistichacker/dingtalk-chat-exporter)（MIT）开发
- 新增 `THIRD_PARTY_NOTICES.md`，保留上游版权与 MIT 许可证全文
- README、SKILL.md、部署文档补充归属说明

## v1.0.0 — 2026-10-19

首个公开版本。

- 四象限摘要结构：紧急且重要 / 重要但不紧急 / 不重要但紧急 / 不重要不紧急，另附「已过期/需核实」与「未覆盖与风险」
- 只读桥接 `scripts/agent_read.py`：白名单 + 固定时间窗 + 分页去重，不暴露远程地址与 token
- 钉钉群机器人推送 `scripts/push-dingtalk.py`：Markdown 卡片、可选关键词、`--dry-run`
- 简报质量规则：相对日期按消息时区解析、新旧通知冲突保留依据、发送者不等于负责人
- 媒体规则：本地缓存优先、缺图如实标注、云端 OCR 单独授权
- 部署文档：从零搭建本地读取链路、加固清单与常见问题
