# 录音智整 · Audio Notes Skill

一个供 Agent 调用的场景自适应录音整理 Skill。输入录音或完整文字稿，输出**分层纪要、整理版全文、忠实转写稿、结构化 JSON**。默认区分原文事实与 AI 分析，关键内容可追溯。

**版本：0.1.0（首版预览）** · MIT · 无需独立总结 API · 中文说明

> 这不是一键独立总结程序。总结由宿主 Agent 完成；Python 脚本提供转写、分段、检查点和校验。请先看 [能力验证状态](VALIDATION.md)。

## 下载与安装到 Agent
1. 下载仓库 ZIP 并解压，或克隆仓库。
2. 将**整个目录**（不是只有 SKILL.md）放到宿主支持的 skills 目录。不同 Agent 目录不同，见 [兼容说明](references/agent-compatibility.md)。
3. 让 Agent 使用 `audio-notes`，上传录音或完整文字记录。
4. 仅处理文字稿时无需安装 Python、FFmpeg、转写服务。Agent 仍须有能力读取全部资料并写出文件。

没有 Skill 自动发现机制时，可让 Agent 阅读本目录的 `SKILL.md` 并按指令工作；这不等于该平台已完成原生集成。

### 调用示例
- “使用 audio-notes 整理这份访谈全文，输出中文纪要和两版全文。”
- “这是一场项目复盘，重点保留争议、决策依据和明确待办。”
- “本地转写这个音频；不要发送给在线转写服务。总结 Agent 的数据处理方式也请先说明。”
- “把这段中英混说课程整理成中文学习笔记，英文术语保留。”

## 默认输出
```
work/
  source.json               原始记录与处理范围（中间产物，也应妥善保护）
  result.json               Agent 填写的全部结构化成果
  summary.md                一分钟速览 + 详细纪要 + AI 分析
  transcript-clean.md       整理版全文
  transcript-source.md      保留原话的转写/输入全文
```
对文字稿只能保证保留输入，不能声称音频已经核验。对只有摘要的输入不会反向编造全文。时间、说话人未知时不补造。

## 分层安装
建议 Python 3.10+。以下命令在项目根目录执行，虚拟环境激活方式请根据系统选择。
```
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python scripts/audio_notes.py doctor
```
### 文字稿和校验（Python 标准库即可）
```
python scripts/audio_notes.py import-text --input notes.txt --out work
python scripts/audio_notes.py skeleton --source work/source.json --out work/result.json
```
`skeleton` 只生成草稿骨架，**不会生成纪要或整理稿**。接着让 Agent 按 SKILL.md 填写 result.json，再执行：
```
python scripts/audio_notes.py validate --source work/source.json --result work/result.json
python scripts/audio_notes.py render --source work/source.json --result work/result.json --out work
```
输入 TXT/MD/SRT/VTT 须为 UTF-8；字幕导入保留时间与字幕正文，非完整保留字幕文件格式。原始文件不变。PDF/DOCX 请由 Agent 先提取为文字。

### 在线转写（可选，可能收费）
```
python -m pip install -e ".[online]"
```
通过本机安全方式设置 `OPENAI_API_KEY` 环境变量，不在聊天中提供，不提交到仓库。
```
python scripts/audio_notes.py transcribe --input recording.m4a --out work --provider openai --confirm-upload
```
`--confirm-upload` 是调用方在**用户已知情同意后**传入的开关，不是用户同意的技术证明。脚本默认 endpoint 为 `https://api.openai.com/v1`，默认模型 `whisper-1`，使用带分段时间的响应。自定义 HTTPS 服务需 `--base-url` 指定并另外 `--confirm-custom-endpoint`；不读取环境中的 base URL，避免隐式改道。OpenAI 兼容服务必须真正兼容此模型/参数/响应，未做普遍兼容保证。

### 本地转写（可选）
```
python -m pip install -e ".[local]"
python scripts/audio_notes.py transcribe --input recording.wav --out work --provider local --model small --allow-model-download
```
默认 CPU + INT8，不自动下载模型。模型已缓存时不用下载开关；指定 `--model` 本地模型目录可减少外网依赖。下载开关必须在用户同意模型下载后使用。`--device cuda --compute-type float16` 是可选高级配置，需自行匹配驱动与依赖。

**音频切分需要 FFmpeg/ffprobe 在 PATH 中**。请从可信渠道安装，本项目不会自动安装。faster-whisper 自身通过 PyAV 解码，但我们的长音频切分层使用 FFmpeg。

### 长录音与恢复
默认按 300 秒切成 16kHz 单声道 PCM WAV（约 9.6MB/段），串行转写，避免常见在线单文件大小限制。`--chunk-seconds` 允许 30–600 秒。不设置总录音时长上限；磁盘、内存、网络、服务限额仍构成实际限制。
```
python scripts/audio_notes.py transcribe --input recording.m4a --out work --provider local --model small
```
再次执行相同命令会复用成功检查点；失败段重新尝试。参数或源文件变化时拒绝复用，须另用输出目录。检查点包含原文，需保护。首版采用无重叠固定时长切分，边界词可能识别不完整，务必抽查边界；不承诺自动无损衔接或跨段说话人对齐。

FFmpeg/ffprobe 可用 `AUDIO_NOTES_FFMPEG`、`AUDIO_NOTES_FFPROBE` 指向本地可执行文件。路径只能由用户/宿主可信配置，不从录音内容读取。

## 隐私与限制
- 在线转写上传到明确服务商；费用和留存按其政策，脚本不估造价格。
- 本地转写不代表总结也本地执行，云端 Agent 可能接收文字稿。
- 首版内置两个转写适配器均**不提供说话人分离**；原生宿主有该能力时可保留结果，但须谨慎跨段映射。
- 语音识别错误、漏词、错分人物仍需人工核验；招聘等高影响场景不能自动决策。
- 私人原始资料不纳入公开仓库。`work/`、`.env`、音频等被 Git 忽略，但忽略规则不等于隐私保证；发布前仍须检查。
- 目前仅提供 Markdown/JSON；Word/PDF、更多服务商、说话人分离为后续扩展，不假装已有。

## 开发与测试
```
python -m unittest discover -s tests -v
python -m pip install -e ".[dev]"
```
`dev` 额外安装 JSON Schema 检查库。未安装时仍有标准库语义校验，命令会明确提示未执行完整 Schema 校验。CI 覆盖 Windows、macOS、Linux 的离线单元测试，不调用付费服务，也不下载语音模型。

参阅 [DISCLAIMER.md](DISCLAIMER.md)、[PRIVACY.md](PRIVACY.md)、[SECURITY.md](SECURITY.md)、[LICENSE](LICENSE)。
