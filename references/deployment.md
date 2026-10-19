# 从零搭一条本地只读链路

本技能不附带解密器，也不自动发现账号。可用的链路是：**本机已登录的钉钉客户端 → 本地缓存数据库 → 只读 HTTP 服务 → 白名单桥接**。

> 这条链路读取的是你自己机器上的缓存副本。使用前先确认组织政策允许，并理解它会生成**整个账号**（不只是所选群）的明文数据库副本。

## 1. 准备

- Windows 10/11，钉钉 PC 客户端已登录
- Python 3.9+（推荐用独立虚拟环境）
- 一个隔离的工作目录，例如 `D:\dingtalk-brief`

## 2. 部署导出器

本项目以 [dingtalk-chat-exporter](https://github.com/idealistichacker/dingtalk-chat-exporter) 作为参考实现（上游 MIT）。把仓库 clone 到工作目录后：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

首次启动会要求定位账号数据目录并解密。解密后的数据库通常落在项目的 `data/decrypted/` 下，**这是明文敏感文件**，不要提交、外发或截图。

## 3. 加固服务

最低要求：

- 只监听 `127.0.0.1`，不转发端口，不做局域网共享
- 关闭任意来源 CORS，拒绝跨站读写与非本机 Host
- 文件读取限制在账号缓存目录内，拒绝任意路径
- 关闭自动同步（自动同步会导出全部会话）；需要刷新时单独授权

上游服务默认端口 `8090`。启动后先确认：

```powershell
Invoke-WebRequest http://127.0.0.1:8090/api/conversations?limit=1 -UseBasicParsing
```

## 4. 白名单

复制 `examples/allowed_groups.example.json` 为 `allowed_groups.json`，只填你要读的群：

```json
{
  "schema_version": 1,
  "groups": [
    {"cid": "12345678901", "title": "示例群"}
  ]
}
```

`cid` 是群的数字 ID，可在服务返回的会话列表里看到。白名单只是 Agent 入口的限制，**底层服务仍能看到整个账号**，它不是系统级隔离。

## 5. 挂上桥接

把 `scripts/agent_read.py` 和 `allowed_groups.json` 放在同一目录，然后：

```powershell
python agent_read.py scope          # 看配置
python agent_read.py groups         # 列白名单内的群
python agent_read.py messages --cid 12345678901 --since 1792339200000 --until 1792399116000 --limit 500
```

时间参数是 **Unix 毫秒**，语义为 `since < created_at <= until`。分页按最新窗口返回，`offset` 每次加 `limit`，末页可能重叠，必须按 `(cid, id)` 去重。

## 6. 保持新鲜

本地缓存是「客户端同步到哪就算哪」：客户端没开、没联网，缓存就不会更新。

- 需要最新数据时，先确认钉钉客户端在运行并完成同步
- 重新解密会覆盖明文副本，属于敏感操作，单独授权后再做
- 简报里始终写明**缓存快照时间**，不要让读者误以为是实时数据

## 7. 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 连接被拒绝 | 服务没起或端口不对 | 先确认进程与 `127.0.0.1:8090` |
| `total=0` | 时间窗内没缓存、客户端未同步 | 核对时间戳与客户端状态，不要断言群内无消息 |
| 群不在列表 | 不在白名单 | 按本次授权修改配置，不要临时放开全部群 |
| 解密失败 | 客户端版本变化、账号不匹配 | 升级导出器或换匹配的账号目录，不要猜测 |
