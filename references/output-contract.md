# 输出契约 1.0

`source.json` 是原始记录，`result.json` 内 source 必须与其完全一致。调用 validate/render 必须传入原始 source 文件，防止改写后自证。

## 来源
每段：id / text / start / end / speaker。时间以秒表示；不存在则 start=end=null，speaker 未知为 null。input_sha256 标识输入文件；宿主无法计算时可为 null，并添加 warnings，不能虚构哈希。

processing.status 仅说明导入/转写计划是否完整执行。音频使用 processed_ranges/failed_ranges；文字无音频范围则空数组。warnings 列明未核验、空段、边界等限制。

## 结果
- status：draft / partial / complete。draft 不允许交付为已完成结果。源 partial 则结果不得 complete。
- overview：text + source_ids，一分钟速览的要点。
- topics：title + source_ids + points；每个 point 有 text / kind / source_ids。
- kind：statement（材料中的陈述）、opinion、proposal、decision、action、uncertain。不表示对外事实已证实。
- decisions：text + source_ids，只存明确决策。
- actions：task / owner / due / dependency / source_ids；未知字段 null。
- chapters：title / text / start / source_ids。start 为引用段落中的最早起点，无原始时间则 null。
- quotes：text + source_ids。逐字连续引用至少在一个引用源段落中存在；跨段分开引用。
- analysis：observation / interpretation / recommendation / limitations / source_ids。独立 AI 分析，不要求公开隐藏推理过程。
- uncertainties：text + source_ids，保存冲突、疑义、限制；部分成果需指出未完成范围。
- clean_segments：text + source_ids，整理全文的连续段落。complete 时必须覆盖每一个源段落 ID，但仅有 ID 覆盖不证明语义无遗漏，仍需人工/Agent 审核。

### 例：待办
```json
{"task":"发送样品清单","owner":"发言者乙","due":null,"dependency":null,"source_ids":["S000003"]}
```

禁止额外字段悄悄更改接口。扩展版本时更新 schema_version、Schema、校验器、渲染器和兼容说明。

## 渲染
Markdown 保留关键来源标签，全文稿每段有来源 ID。result.json 保存全部主题点、分析和整理稿的来源关系。当前不生成 HTML 链接锚点或可点击音频播放器；ID 可用于搜索定位，不宣称支持播放跳转。

脚本会检查结构、引用存在、源稿一致、原话匹配及段落覆盖。它不能验证模型是否曲解、有没有漏掉段落里的半句话，也不能证明决策确由有权限的人作出。
