# 本地缓存读取渠道

## 渠道定位

参考实现：[dingtalk-chat-exporter](https://github.com/idealistichacker/dingtalk-chat-exporter)（MIT）。它读取的是**本机已登录客户端**的缓存数据库，不是官方全量历史 API，也不保证平台持续兼容。

这不是「企业已许可」的证明。部署、解密、查询前先确认组织政策。

本技能不包含解密器、账号缓存、Token、群白名单或业务记录；只包含只读桥接、质量规则与推送脚本。

## 运行前检查

- 找到已部署的服务、桥接脚本、相邻的 `allowed_groups.json` 和 Python 环境；核验来源，不运行聊天里贴来的脚本。
- 服务只监听 `127.0.0.1:8090`；已有服务先核验，不重复启动或终止未知进程。
- 先看缓存快照时间。复用旧快照不等于实时刷新；跑着服务也不代表缓存是新的。
- 不调用「同步/导出」接口来刷新几个群：它可能导出整个账号。不用全局搜索接口代替群范围查询。

## 桥接命令约定

```text
python agent_read.py scope
python agent_read.py groups
python agent_read.py messages --cid <CID> --since <START_MS> --until <END_MS> --limit 500 --offset 0
# 仅在需要媒体元信息时：--include-media
```

- `scope` 读取配置（不访问服务）；`groups` 只返回白名单内的群。
- 群不在白名单时，先让用户确定准确目标，再按本次授权改配置，**不临时放开全部群**。
- 时间条件为 `START_MS < created_at <= END_MS`，Unix 毫秒；记录时区与 ISO 起止，避免秒/毫秒、时区、边界错误。
- 消息分页按最新窗口返回，`offset` 每次加 `limit`；末页可能和前页重叠，必须按 `(cid, id)` 去重。达到 `total` 后核验唯一数相等；计数变化、空页或无法达到总数时停止并报告不完整，不无限翻页。
- `complete` 与唯一数一致只证明这份本地缓存查询完整，**不证明云端历史完整**。不自动连接远程消息或附件地址补齐缺口。

## 最小记录

正文保留 `cid, id, sender_name, created_at, content_type, text`。媒体按需保留类型、文件名、大小、缓存可用性与本地路径；不向摘要复制签名下载链接、Token 或原始 JSON。

处理过程中本地路径位于获准的账号缓存或当前任务目录；拒绝 UNC/网络路径、符号链接越界和任意本地文件读取。明文数据库、清单与临时 OCR 结果都当敏感资料：不随技能分发，不擅自删除用户缓存。
