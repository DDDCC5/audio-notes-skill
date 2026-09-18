# 转写路径与配置

## 原生宿主
检查能否真正读取音频、返回全文、时间戳和说话人。如果不能输出全文，不可用直接音频摘要代替。记录 provider=host_native，说明宿主名称与限制。可将宿主返回全文导入；如果原始返回有时间戳，按 source schema 保存，不通过纯文本导入把有效时间丢掉。

## OpenAI 适配器
可选依赖 openai，默认官方 HTTPS endpoint，模型 whisper-1，verbose_json 与 segment 时间戳。上传前确认服务商、录音范围、付费可能性；不读取环境中 base URL。自定义地址另需确认。配置密钥仅通过环境变量，不输出、不进入 source.json。

首版模型参数可指定，但并非所有模型支持 verbose_json/timestamp_granularities。用户换模型前须核对官方参数；不支持则显式失败，不能猜测时间。

SDK 自动重试关闭，不静默回退服务商。失败时仅输出异常类别，避免泄露密钥、私密文件路径或服务商错误正文。如需排障，在用户本地受控环境检查，先脱敏。

## faster-whisper
可选依赖 faster-whisper，默认 small / cpu / int8。已缓存模型优先，不默认下载；allow-model-download 必须经授权。GPU 需对应 CUDA/cuDNN 等环境，未跨设备保证。多语言能力来自模型，不代表项目已验证所有语言。

VAD 可能错误过滤弱语音；边界、重叠说话、噪声和语种切换尤其需要人工抽查。首版不提供说话人分离，也不把内容推断当声纹识别。

## 服务扩展
当前 make_adapter 以 provider 分支隔离本地和在线实现，新增 provider 需：
1. 明确数据去向和费用授权，不允许隐式服务回退；
2. 返回 text/start/end 的分段，或明确无时间戳并扩展契约，不能估造；
3. 记录处理范围、失败、能力及限制；
4. 增加模拟测试和独立真实服务测试状态；
5. 核对第三方许可证、模型协议和数据政策。

参考：https://developers.openai.com/api/docs/guides/speech-to-text
参考：https://github.com/SYSTRAN/faster-whisper
依赖版本和 API 限制会变化，发布升级前需重新核验。
