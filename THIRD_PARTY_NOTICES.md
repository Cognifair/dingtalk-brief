# 第三方声明

本技能构建在以下开源项目之上，按其许可证要求保留声明。

## dingtalk-chat-exporter

- 仓库：https://github.com/idealistichacker/dingtalk-chat-exporter
- 用途：本地读取链路（钉钉 V2/V3 加密缓存解密、本地只读 HTTP 服务、会话与消息接口）基于该项目设计实现。
- 关系说明：`scripts/agent_read.py` 是按上述服务的 HTTP 接口独立编写的精简客户端，没有复制上游源码；本仓库其余内容（四象限结构、质量规则、部署文档、推送脚本）为原创。
- 许可证：MIT

```text
MIT License

Copyright (c) 2026 DingTalk Exporter Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
