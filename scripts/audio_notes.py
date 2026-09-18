#!/usr/bin/env python3
"""Audio Notes support CLI. No automatic LLM summarization or implicit uploads."""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse

VERSION = "0.1.0"
DISCLAIMER = ("本内容由 AI 基于所提供材料整理，可能存在转写、归属或理解错误。"
              "请核验关键数字、引用、决策和行动。AI 分析不代表原始发言或参与者共识，"
              "不替代专业意见或人工决策。处理范围与限制见下文。")
ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def tool(name):
    configured = os.getenv("AUDIO_NOTES_" + name.upper())
    found = configured or shutil.which(name)
    if not found or not Path(found).is_file():
        raise ValueError(f"缺少 {name}；请设置 PATH 或 AUDIO_NOTES_{name.upper()}。")
    return str(found)


def run_process(args):
    # No shell; input filenames cannot inject shell commands. Do not log paths or content.
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise ValueError("音频工具执行失败；请检查文件格式、磁盘和工具配置。未输出可能含私人路径的日志。")
    return p.stdout


def probe(path):
    data = json.loads(run_process([tool("ffprobe"), "-v", "error", "-show_entries",
                                  "format=duration", "-of", "json", str(Path(path).resolve())]))
    seconds = float(data["format"]["duration"])
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("无法确定有效音频时长。")
    return seconds


def timestamp(seconds):
    if seconds is None:
        return "无时间戳"
    whole = int(seconds)
    return f"{whole // 3600:02d}:{whole // 60 % 60:02d}:{whole % 60:02d}"


def segment(sid, text, start=None, end=None, speaker=None):
    return {"id": sid, "text": text, "start": start, "end": end, "speaker": speaker}


def source_document(input_hash, kind, provider, segments, duration=None,
                    status="complete", processed=None, failed=None, warnings=None):
    return {"schema_version": "1.0", "input_sha256": input_hash, "input_kind": kind,
            "provider": provider, "duration_seconds": duration,
            "processing": {"status": status, "processed_ranges": processed or [],
                           "failed_ranges": failed or [], "warnings": warnings or []},
            "segments": segments}


def source_markdown(source):
    heading = "用户提供的摘要记录（非录音全文）" if source.get("input_kind") == "summary_only" else "忠实转写稿／原始文字记录"
    lines = ["# " + heading, "", "> " + DISCLAIMER, "",
             "这不是经人工校对的逐字稿；文字输入未做音频核验。", "",
             "处理状态：" + source["processing"]["status"], ""]
    for w in source["processing"]["warnings"]:
        lines += ["- 限制：" + w]
    for r in source["processing"]["failed_ranges"]:
        lines += [f"- 未完成：{timestamp(r['start'])}–{timestamp(r['end'])}"]
    for s in source["segments"]:
        who = s.get("speaker") or "说话人未识别"
        lines += ["", f"## {s['id']} · {timestamp(s.get('start'))} · {who}", "", s["text"]]
    return "\n".join(lines) + "\n"


def persist_source(out, source):
    save(Path(out) / "source.json", source)
    Path(out, "transcript-source.md").write_text(source_markdown(source), encoding="utf-8")


def parse_time(value):
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def import_text(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    segments = []
    warnings = ["用户提供文字稿，未通过原始音频核验。"]
    if path.suffix.lower() in (".srt", ".vtt"):
        blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
        pattern = re.compile(r"((?:\d+:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d+:)?\d{2}:\d{2}[.,]\d{3})")
        for block in blocks:
            lines = block.splitlines()
            for i, line in enumerate(lines):
                m = pattern.search(line)
                if m:
                    body = "\n".join(lines[i + 1:])
                    if body.strip():
                        start, end = parse_time(m[1]), parse_time(m[2])
                        if end < start:
                            raise ValueError("字幕时间顺序错误。")
                        segments.append(segment(f"S{len(segments)+1:06d}", body, start, end))
                    break
        warnings += ["字幕格式元数据未保留；字幕正文与时间戳保留，源文件未修改。"]
    elif path.suffix.lower() in (".txt", ".md", ".markdown"):
        # Keep every nonempty line verbatim, including meaningful whitespace and Markdown.
        for line in text.splitlines():
            if line.strip():
                segments.append(segment(f"S{len(segments)+1:06d}", line))
        warnings += ["空行仅作排版未保存到分段数组；所有非空行内容保留。"]
    else:
        raise ValueError("仅直接导入 UTF-8 TXT/MD/SRT/VTT；其他文档请先由宿主提取。")
    if not segments:
        raise ValueError("没有可导入的文字；请检查编码或字幕格式。")
    return source_document(digest(path), "text", "user_text", segments, warnings=warnings)


def skeleton(source):
    return {"schema_version": "1.0", "status": "draft", "title": "待 Agent 填写",
            "language": "zh-CN", "scenes": ["general"], "source": copy.deepcopy(source),
            "overview": [], "topics": [], "decisions": [], "actions": [], "chapters": [],
            "quotes": [], "analysis": [], "uncertainties": [], "clean_segments": []}


def collect_validation_errors(result, source=None):
    errors = []
    required = ("schema_version", "status", "title", "language", "scenes", "source", "overview",
                "topics", "decisions", "actions", "chapters", "quotes", "analysis",
                "uncertainties", "clean_segments")
    if not isinstance(result, dict):
        return ["result 必须为对象。"]
    for key in required:
        if key not in result:
            errors.append("缺少字段：" + key)
    if errors:
        return errors
    if result["schema_version"] != "1.0":
        errors.append("不支持的 schema_version。")
    if result["status"] not in ("complete", "partial"):
        errors.append("结果仍为草稿或状态无效。")
    for key in ("title", "language"):
        if not isinstance(result[key], str) or not result[key].strip():
            errors.append(key + " 必须为非空文字。")
    if not isinstance(result["scenes"], list) or not result["scenes"]:
        errors.append("scenes 必须为非空数组。")
    src = result["source"]
    if source is not None and src != source:
        errors.append("source 与原始 source.json 不一致；禁止改写或截断原始记录。")
    if not isinstance(src, dict) or not isinstance(src.get("segments"), list):
        return errors + ["source.segments 无效。"]
    if src.get("processing", {}).get("status") != "complete" and result["status"] == "complete":
        errors.append("源材料未完整处理，结果不能标记 complete。")
    processing = src.get("processing", {})
    if processing.get("status") == "complete" and processing.get("failed_ranges"):
        errors.append("源记录存在失败范围，不能标记 complete。")
    for range_key in ("processed_ranges", "failed_ranges"):
        for span in processing.get(range_key, []):
            if not isinstance(span, dict) or not finite_number(span.get("start")) or not finite_number(span.get("end")) or span["start"] < 0 or span["end"] < span["start"]:
                errors.append("源处理范围非法。")
    if src.get("input_kind") == "summary_only" and not processing.get("warnings"):
        errors.append("仅摘要输入必须明确无法恢复录音全文。")
    valid = {}
    for s in src["segments"]:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not isinstance(s.get("text"), str):
            errors.append("源段落结构无效。")
            continue
        if s["id"] in valid:
            errors.append("源段落 ID 重复：" + s["id"])
        valid[s["id"]] = s
        start, end = s.get("start"), s.get("end")
        if (start is None) != (end is None):
            errors.append("源段落时间必须同时为空或同时存在：" + s["id"])
        if start is not None and (not finite_number(start) or not finite_number(end)
                                  or start < 0 or end < start):
            errors.append("源段落时间非法：" + s["id"])
    if not valid:
        errors.append("没有源段落。")

    def refs(item, label):
        ids = item.get("source_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(x, str) for x in ids):
            errors.append(label + " 缺少来源 ID。")
            return []
        for sid in ids:
            if sid not in valid:
                errors.append(label + " 引用了不存在的段落：" + sid)
        return ids

    def text_field(item, key, label):
        if not isinstance(item.get(key), str) or not item[key].strip():
            errors.append(label + "." + key + " 必须为非空文字。")

    covered = set()
    for key in required[6:]:
        if not isinstance(result[key], list):
            errors.append(key + " 必须为数组。")
            continue
        for index, item in enumerate(result[key]):
            label = f"{key}[{index}]"
            if not isinstance(item, dict):
                errors.append(label + " 必须为对象。")
                continue
            ids = refs(item, label)
            if key == "topics":
                text_field(item, "title", label)
                points = item.get("points", [])
                if not isinstance(points, list) or not points:
                    errors.append(label + " 缺少 points。")
                else:
                    for point in points:
                        if not isinstance(point, dict):
                            errors.append(label + " point 无效。")
                            continue
                        text_field(point, "text", label)
                        refs(point, label)
                        if point.get("kind") not in ("statement", "opinion", "proposal", "decision", "action", "uncertain"):
                            errors.append(label + " point.kind 无效。")
            elif key == "actions":
                text_field(item, "task", label)
                for k in ("owner", "due", "dependency"):
                    if k not in item or (item[k] is not None and not isinstance(item[k], str)):
                        errors.append(label + "." + k + " 应为文字或 null。")
            elif key == "analysis":
                for k in ("observation", "interpretation", "recommendation", "limitations"):
                    text_field(item, k, label)
            elif key == "chapters":
                text_field(item, "title", label)
                text_field(item, "text", label)
                start = item.get("start")
                starts = [valid[x]["start"] for x in ids if x in valid and valid[x].get("start") is not None]
                if start is not None and (not finite_number(start) or not starts or abs(start - min(starts)) > .05):
                    errors.append(label + " 时间必须来自引用源段落的起点，不能估造。")
            else:
                text_field(item, "text", label)
            if key == "quotes":
                quote = item.get("text", "")
                if not quote or not any(quote in valid[x]["text"] for x in ids if x in valid):
                    errors.append(label + " 引用并非源段落中的连续原话。跨段引用请拆分。")
            if key == "clean_segments":
                covered.update(x for x in ids if x in valid)
    if not result["overview"] or not result["topics"] or not result["analysis"]:
        errors.append("默认交付必须包含速览、主题和独立 AI 分析。")
    if not result["clean_segments"]:
        errors.append("缺少整理版全文。")
    if result["status"] == "complete" and set(valid) - covered:
        errors.append("整理稿未覆盖全部源段落；请补齐或将结果标为 partial 并说明。")
    if result["status"] == "partial" and not result["uncertainties"]:
        errors.append("部分结果必须在 uncertainties 中解释未完成范围。")
    if importlib.util.find_spec("jsonschema"):
        import jsonschema
        schema = load(ROOT / "schemas/result.schema.json")
        for err in jsonschema.Draft202012Validator(schema).iter_errors(result):
            errors.append("Schema " + "/".join(map(str, err.path)) + ": " + err.message)
    return errors


def citation(item):
    return "〔" + ", ".join(item.get("source_ids", [])) + "〕"


def render(result, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    source = result["source"]
    lines = ["# " + result["title"], "", "> " + DISCLAIMER, "", "## 基本信息与处理说明", "",
             f"- 输出状态：{result['status']}", f"- 来源：{source['input_kind']} / {source['provider']}",
             "- 场景：" + ", ".join(result["scenes"]), "- 语言：" + result["language"], "",
             "## 一分钟速览", ""]
    for item in result["overview"]:
        lines += ["- " + item["text"] + " " + citation(item)]
    lines += ["", "## 主题详述", ""]
    for item in result["topics"]:
        lines += ["### " + item["title"], ""]
        for p in item["points"]:
            lines += [f"- [{p['kind']}] {p['text']} {citation(p)}"]
        lines += [""]
    for key, title in (("decisions", "明确决策"), ("actions", "明确承诺的后续行动"),
                       ("chapters", "章节导航"), ("quotes", "代表性原话")):
        if not result[key]:
            continue
        lines += ["## " + title, ""]
        for item in result[key]:
            if key == "actions":
                lines += [f"- {item['task']} {citation(item)}",
                          f"  - 负责人：{item['owner'] or '未明确'}；截止：{item['due'] or '未明确'}；依赖：{item['dependency'] or '未明确'}"]
            elif key == "chapters":
                lines += [f"### {timestamp(item.get('start'))} · {item['title']}", "",
                          item["text"] + " " + citation(item), ""]
            else:
                lines += ["- " + item["text"] + " " + citation(item)]
        lines += [""]
    lines += ["## AI 分析与建议", "", "以下是基于材料的 AI 分析，不是参与者已确认的事实、共识或待办。", ""]
    for i, item in enumerate(result["analysis"], 1):
        lines += [f"### 分析 {i}", "", "- 材料观察：" + item["observation"] + " " + citation(item),
                  "- 解读：" + item["interpretation"], "- 建议：" + item["recommendation"],
                  "- 局限：" + item["limitations"], ""]
    lines += ["## 待核实事项与处理限制", ""]
    for item in result["uncertainties"]:
        lines += ["- " + item["text"] + " " + citation(item)]
    for warning in source["processing"]["warnings"]:
        lines += ["- " + warning]
    for failed in source["processing"]["failed_ranges"]:
        lines += [f"- 未完成音频范围：{timestamp(failed['start'])}–{timestamp(failed['end'])}"]
    if not result["uncertainties"] and not source["processing"]["warnings"]:
        lines += ["未列出特定疑义不代表内容已经人工核验。"]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    clean_heading = "摘要整理版（非录音全文）" if source.get("input_kind") == "summary_only" else "整理版全文"
    clean = ["# " + clean_heading, "", "> " + DISCLAIMER, "", "处理状态：" + result["status"], ""]
    for item in result["clean_segments"]:
        clean += [item["text"], "", citation(item), ""]
    (out / "transcript-clean.md").write_text("\n".join(clean), encoding="utf-8")
    (out / "transcript-source.md").write_text(source_markdown(source), encoding="utf-8")
    save(out / "result.json", result)


def check_endpoint(args):
    if args.provider != "openai":
        return
    if not args.confirm_upload:
        raise ValueError("在线转写未获上传确认；在用户知情同意后使用 --confirm-upload。")
    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL 必须是无凭据、无查询参数的 HTTPS 地址。")
    if args.base_url.rstrip("/") != "https://api.openai.com/v1" and not args.confirm_custom_endpoint:
        raise ValueError("自定义服务地址需要独立授权并使用 --confirm-custom-endpoint。")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("请安全设置 OPENAI_API_KEY；不要在聊天或日志输出密钥。")


def make_adapter(args):
    if args.provider == "openai":
        try:
            from openai import OpenAI
        except ImportError:
            raise ValueError("请先安装 online 可选依赖。") from None
        # Explicit endpoint/key; disable retries to reduce accidental duplicate billable calls.
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=args.base_url,
                        max_retries=0, timeout=180.0)

        def transcribe(path):
            with Path(path).open("rb") as f:
                kw = {"model": args.model or "whisper-1", "file": f,
                      "response_format": "verbose_json", "timestamp_granularities": ["segment"]}
                if args.language:
                    kw["language"] = args.language
                result = client.audio.transcriptions.create(**kw).model_dump()
            rows = result.get("segments")
            if rows is None:
                raise ValueError("服务未返回所需分段；不能编造时间戳。")
            return [{"text": r["text"], "start": r["start"], "end": r["end"]} for r in rows]
        return transcribe
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ValueError("请先安装 local 可选依赖。") from None
    model = WhisperModel(args.model or "small", device=args.device, compute_type=args.compute_type,
                         local_files_only=not args.allow_model_download)

    def transcribe(path):
        rows, _ = model.transcribe(str(path), language=args.language, beam_size=5, vad_filter=True)
        return [{"text": r.text, "start": r.start, "end": r.end} for r in rows]
    return transcribe


def transcribe_audio(args):
    check_endpoint(args)
    input_path = Path(args.input)
    if not input_path.is_file():
        raise ValueError("音频文件不存在。")
    if not 30 <= args.chunk_seconds <= 600:
        raise ValueError("chunk-seconds 应在 30–600 秒之间。")
    ffmpeg = tool("ffmpeg")
    duration = probe(input_path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    checkpoints = out / "checkpoints"
    checkpoints.mkdir(exist_ok=True)
    config = {"input_sha256": digest(input_path), "provider": args.provider,
              "model": args.model or ("whisper-1" if args.provider == "openai" else "small"),
              "chunk_seconds": args.chunk_seconds, "duration": duration,
              "language": args.language, "base_url": args.base_url if args.provider == "openai" else None,
              "device": args.device, "compute_type": args.compute_type, "version": VERSION}
    manifest_path = checkpoints / "manifest.json"
    if manifest_path.exists() and load(manifest_path) != config:
        raise ValueError("输入或参数改变，不能复用此目录；请使用新输出目录。")
    if not manifest_path.exists() and (out / "source.json").exists():
        raise ValueError("输出目录已有其他来源记录，请使用新目录。")
    save(manifest_path, config)
    adapter = None
    all_segments, processed, failed = [], [], []
    warnings = ["自动识别未人工核验；不提供说话人分离。",
                "首版固定时长无重叠切分：边界词可能丢失或识别不完整，请抽查。",
                "complete 仅代表所有计划分段执行结束，不代表语音识别无遗漏。"]
    count = math.ceil(duration / args.chunk_seconds)
    for index in range(count):
        start = index * args.chunk_seconds
        length = min(args.chunk_seconds, duration - start)
        checkpoint = checkpoints / f"chunk-{index:06d}.json"
        wav = checkpoints / f"chunk-{index:06d}.wav"
        try:
            if checkpoint.exists() and load(checkpoint).get("status") == "complete":
                rows = load(checkpoint)["segments"]
            else:
                run_process([ffmpeg, "-nostdin", "-v", "error", "-y", "-ss", str(start),
                             "-i", str(input_path.resolve()), "-t", str(length), "-vn", "-ac", "1",
                             "-ar", "16000", "-c:a", "pcm_s16le", str(wav.resolve())])
                if adapter is None:
                    adapter = make_adapter(args)
                raw = adapter(wav)
                rows = []
                for j, r in enumerate(raw):
                    if not isinstance(r.get("text"), str) or not finite_number(r.get("start")) or not finite_number(r.get("end")):
                        raise ValueError("转写分段响应非法。")
                    a, b = r["start"], r["end"]
                    if a < 0 or b < a or b > length + 1.0:
                        raise ValueError("转写时间戳超出分段范围。")
                    if r["text"].strip():
                        rows.append(segment(f"A{index:06d}S{j:06d}", r["text"],
                                            round(start + min(a, length), 3),
                                            round(start + min(b, length), 3)))
                save(checkpoint, {"status": "complete", "segments": rows})
            all_segments.extend(rows)
            processed.append({"start": start, "end": start + length})
            if not rows:
                warnings.append(f"分段 {index} 未识别出文字，可能是静音或识别失败，需核验。")
        except Exception as exc:
            # Never echo provider error bodies, headers, secrets or private filenames.
            failed.append({"start": start, "end": start + length, "reason": type(exc).__name__})
            save(checkpoint, {"status": "failed", "error_type": type(exc).__name__})
            print(f"分段 {index} 失败（{type(exc).__name__}）；为避免重复计费已停止。", file=sys.stderr)
            if index + 1 < count:
                failed.append({"start": (index + 1) * args.chunk_seconds, "end": duration, "reason": "not_attempted"})
            break
        finally:
            # Persist progress after every chunk; raw source file is never altered or deleted.
            status = "complete" if len(processed) == count else "partial"
            unfinished = list(failed)
            if status == "partial" and not unfinished:
                unfinished.append({"start": min((index + 1) * args.chunk_seconds, duration),
                                   "end": duration, "reason": "not_attempted"})
            doc = source_document(config["input_sha256"], "audio", args.provider, all_segments,
                                  duration, status, processed, unfinished, warnings)
            persist_source(out, doc)
    if failed:
        return 2
    print("转写计划执行完成；请检查 source.json 的范围、空段和限制，再让 Agent 总结。")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audio Notes support CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    imp = sub.add_parser("import-text")
    imp.add_argument("--input", required=True)
    imp.add_argument("--out", required=True)
    sk = sub.add_parser("skeleton")
    sk.add_argument("--source", required=True)
    sk.add_argument("--out", required=True)
    for name in ("validate", "render"):
        p = sub.add_parser(name)
        p.add_argument("--result", required=True)
        p.add_argument("--source", required=True)
        if name == "render":
            p.add_argument("--out", required=True)
    tr = sub.add_parser("transcribe")
    tr.add_argument("--input", required=True)
    tr.add_argument("--out", required=True)
    tr.add_argument("--provider", choices=("local", "openai"), required=True)
    tr.add_argument("--model")
    tr.add_argument("--language", help="ISO language code, e.g. zh or en")
    tr.add_argument("--chunk-seconds", type=int, default=300)
    tr.add_argument("--device", default="cpu", choices=("cpu", "cuda", "auto"))
    tr.add_argument("--compute-type", default="int8")
    tr.add_argument("--allow-model-download", action="store_true")
    tr.add_argument("--base-url", default="https://api.openai.com/v1")
    tr.add_argument("--confirm-upload", action="store_true")
    tr.add_argument("--confirm-custom-endpoint", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = {"python": sys.version.split()[0], "version": VERSION,
                      "openai_installed": bool(importlib.util.find_spec("openai")),
                      "local_installed": bool(importlib.util.find_spec("faster_whisper")),
                      "schema_validation": bool(importlib.util.find_spec("jsonschema"))}
            for name in ("ffmpeg", "ffprobe"):
                try:
                    tool(name)
                    result[name] = True
                except ValueError:
                    result[name] = False
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "import-text":
            if Path(args.out, "source.json").exists():
                raise ValueError("已有 source.json，请使用新输出目录以免覆盖。")
            persist_source(args.out, import_text(args.input))
            print("文字导入完成；原文件未修改。")
        elif args.command == "skeleton":
            if Path(args.out).exists():
                raise ValueError("结果文件已存在，拒绝覆盖。")
            save(args.out, skeleton(load(args.source)))
            print("已创建 draft 骨架；请由 Agent 填写，未生成纪要。")
        elif args.command in ("validate", "render"):
            result = load(args.result)
            errors = collect_validation_errors(result, load(args.source))
            if errors:
                print("校验失败：\n- " + "\n- ".join(errors), file=sys.stderr)
                return 2
            if not importlib.util.find_spec("jsonschema"):
                print("语义校验通过；未安装 jsonschema，完整 Schema 校验未执行。")
            else:
                print("Schema 与语义校验通过；不代表事实已核验。")
            if args.command == "render":
                render(result, args.out)
                print("已生成三份 Markdown 和 result.json。")
        elif args.command == "transcribe":
            return transcribe_audio(args)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Show curated ValueErrors only; do not leak arbitrary input paths/contents.
        message = str(exc) if type(exc) is ValueError else "输入、文件或结构异常；请检查本地文件及参数。"
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
