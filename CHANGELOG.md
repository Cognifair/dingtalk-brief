# Changelog

## v1.2.0 — 2026-11-12

- `push-dingtalk.py`：新增 `--at-mobile` / `--at-userid` / `--at-all`，可在群里 @ 指定成员（正文自动补 `@号码`，只传字段会出现“看不见的 @”）
- `push-dingtalk.py`：读取正文兼容 BOM；**空消息保护**——正文少于 20 字符直接拒绝发送，避免模板提取失败时往群里发空卡片
- `push-dingtalk.py`：失败时返回结构化 error，不再只抛异常
- `dida-task.py`：任务文件读取改为 `utf-8-sig`，PowerShell 写出的 BOM 文件不再报 `Unexpected UTF-8 BOM`
- 新增 `scripts/dida-fanout.py`：同一批任务推送到多个滴答账号，账号表只存环境变量名；每账号独立去重、失败隔离、串行限速
- 新增 `examples/dida-accounts.example.json`
- 工作流补充三条规则：群 0 条时先复核再下结论；小组作业必须写清课程/内容/交付方式/截止；关键信息在未解析图片里时，明确要信息并建「补图信息」待办（截止当天）
- 推送章节新增硬规则：临时文案、改过的广告、用户刚给的内容，**先把完整正文给用户确认，得到明确同意再发**
- 清理仓库中的 `__pycache__` 构建产物

## v1.1.1 — 2026-10-20

- 修复 Windows 中文控制台下脚本打印含 emoji 的任务名时报 `gbk codec` 错误：输出统一按 UTF-8 写出

## v1.1.0 — 2026-10-20

- 新增 `scripts/prepare-cache.py`：唤端 → 等同步稳定 → 停服务 → 重解密 → 重启，一条命令拿到最新快照
- 新增 `scripts/dida-task.py`：通过滴答官方 MCP 建任务，支持未完成+已完成去重、`--dry-run`、`projects`、`today`
- 工作流第 5 步改为「交付、推送、建任务」同一轮完成，两者互不阻塞
- 摘要结构新增「先对表」：截止时间早于当前时刻的一律进【已过期/需核实】
- README 增加自动刷新、滴答任务、定时任务编排说明

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
