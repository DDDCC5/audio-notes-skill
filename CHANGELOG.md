# 更新记录

## 未发布修复 — 2026-09-21
- 修复 Windows cp1252/严格编码终端打印中文时的 UnicodeEncodeError；仅终端日志进行安全转义，原文和输出文件仍完整保存为 UTF-8。
- 增加 4 项编码回归测试，包含严格 cp1252 下实际运行 CLI 子进程，合计 35 项。
- CI 显式使用 UTF-8，并关闭 fail-fast，让六组系统/Python 组合独立运行。
- 更新官方 checkout/setup-python Actions，移除旧 Node 20 运行时依赖。

## 0.1.0 — 2026-09-18
- 新增场景自适应 SKILL.md 与七类模板。
- 提供 TXT/Markdown/SRT/VTT 导入、结果骨架、来源校验和三稿渲染。
- 提供 OpenAI 与 faster-whisper 可选转写路径、固定长度音频切分和检查点恢复。
- 增加 MIT 许可、免责声明、隐私边界和 Agent 能力说明。
- 提供虚构示例、离线单元测试和跨平台 CI 配置。
- 首版不包含说话人分离、无损重叠去重、独立 LLM 总结服务或 Word/PDF 导出。
- 实际验证范围见 VALIDATION.md。
