"""验证 Claude Agent SDK + MiniMax 的四件事（只用极小输入，不含任何论文内容）。
用法: /Volumes/ExtSSD2601/Docfit/.venv/bin/python -I spike.py
结果写入 results.json（不含密钥）。"""
import asyncio, json, os, tempfile, time
from pathlib import Path
from claude_agent_sdk import (ClaudeAgentOptions, ClaudeSDKClient, ResultMessage,
                              SystemMessage, query)

def load_env():
    kv = {}
    for line in Path.home().joinpath(".config/docfit/agent.env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1); kv[k.strip()] = v.strip().strip('"').strip("'")
    key, url, model = kv["DOCFIT_MINIMAX_API_KEY"], kv["DOCFIT_MINIMAX_BASE_URL"], kv["DOCFIT_MINIMAX_MODEL"]
    env = {"ANTHROPIC_BASE_URL": url, "ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": key,
           "ANTHROPIC_MODEL": model, "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
           "ANTHROPIC_DEFAULT_OPUS_MODEL": model, "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
           "CLAUDE_CODE_SUBAGENT_MODEL": model, "ENABLE_TOOL_SEARCH": "false",
           "API_TIMEOUT_MS": "300000", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    return env, model

ENV, MODEL = load_env()
CWD = tempfile.mkdtemp(prefix="sdk-spike-")  # 空目录：不含任何项目文件
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "string"},
    "verdict": {"type": "string", "enum": ["保留", "填写", "删除"]}},
    "required": ["id", "verdict"]}}}, "required": ["items"]}
TASK = ("对下列三个对象各给一个判断，只能是 保留/填写/删除：\n"
        "a: 湖南农业大学\nb: （一号黑体加粗）\nc: ×××")

def opts(**kw):
    base = dict(model=MODEL, env=ENV, cwd=CWD, setting_sources=[], max_turns=4)
    base.update(kw); return ClaudeAgentOptions(**base)

def digest(msgs):
    out = {"init": None, "result": None}
    for m in msgs:
        if isinstance(m, SystemMessage) and m.subtype == "init":
            d = m.data
            out["init"] = {k: d.get(k) for k in ("tools", "skills", "slash_commands", "agents",
                           "plugins", "mcp_servers", "memory_paths", "model") if k in d}
            out["init_keys"] = sorted(d.keys())
        if isinstance(m, ResultMessage):
            out["result"] = {"subtype": m.subtype, "is_error": m.is_error,
                "num_turns": m.num_turns, "duration_ms": m.duration_ms,
                "structured_output": getattr(m, "structured_output", None),
                "usage": m.usage, "text": (m.result or "")[:200]}
    return out

async def run_query(prompt, options):
    msgs = []
    async for m in query(prompt=prompt, options=options): msgs.append(m)
    return digest(msgs)

async def t1_structured_and_zero_tools():
    r = {}
    for name, o in {"tools=[]": opts(tools=[], output_format={"type": "json_schema", "schema": SCHEMA})}.items():
        t = time.time()
        try: r[name] = await asyncio.wait_for(run_query(TASK, o), 240)
        except Exception as e: r[name] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
        r[name]["wall_s"] = round(time.time() - t, 1)
    return r

async def t2_followup_same_session():
    r = {}
    t = time.time()
    try:
        async with ClaudeSDKClient(opts(tools=[], output_format={"type": "json_schema", "schema": SCHEMA})) as c:
            await c.query(TASK); m1 = [m async for m in c.receive_response()]
            await c.query("反馈：把 b 改为 删除，a 和 c 保持你上一轮的判断不变。")
            m2 = [m async for m in c.receive_response()]
        r = {"turn1": digest(m1)["result"], "turn2": digest(m2)["result"]}
    except Exception as e: r = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    r["wall_s"] = round(time.time() - t, 1); return r

async def t3_context_isolation():
    t = time.time()
    try:
        d = await asyncio.wait_for(run_query("只回答：好的", opts(tools=[])), 180)
        d["wall_s"] = round(time.time() - t, 1); return d
    except Exception as e: return {"error": f"{type(e).__name__}: {str(e)[:300]}"}

def brief(d):
    i = d.get("init") or {}
    return {"tools": i.get("tools"), "n_skills": len(i.get("skills") or []), "skills": (i.get("skills") or [])[:6],
            "n_slash": len(i.get("slash_commands") or []), "agents": i.get("agents"),
            "memory_paths": bool(i.get("memory_paths")),
            "in_tokens": (d.get("result") or {}).get("usage", {}).get("input_tokens"),
            "cache_read": (d.get("result") or {}).get("usage", {}).get("cache_read_input_tokens")}

async def iso(label, **kw):
    env = dict(ENV); env.update(kw.pop("extra_env", {}))
    o = ClaudeAgentOptions(model=MODEL, env=env, cwd=CWD, setting_sources=[], max_turns=2, tools=[], **kw)
    try: d = await asyncio.wait_for(run_query("只回答：好的", o), 120); return label, brief(d)
    except Exception as e: return label, {"error": f"{type(e).__name__}: {str(e)[:200]}"}

async def followup_strong():
    o = opts(tools=[], output_format={"type": "json_schema", "schema": SCHEMA})
    async with ClaudeSDKClient(o) as c:
        await c.query(TASK); m1 = digest([m async for m in c.receive_response()])
        await c.query("反馈：只把 c 改为 保留。a 和 b 必须与你上一轮完全相同。")
        m2 = digest([m async for m in c.receive_response()])
    return {"turn1": m1["result"]["structured_output"], "turn2": m2["result"]["structured_output"]}

async def main():
    out = {}
    for label, kw in [
        ("A baseline setting_sources=[]", {}),
        ("B skills=[]", {"skills": []}),
        ("C disable-slash-commands", {"extra_args": {"disable-slash-commands": None}}),
        ("D C + no auto-memory env", {"extra_args": {"disable-slash-commands": None}, "extra_env": {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}}),
        ("E D + system_prompt custom", {"extra_args": {"disable-slash-commands": None}, "extra_env": {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}, "system_prompt": "你是文档对象分类助手。"}),
    ]:
        k, v = await iso(label, **kw); out[k] = v; print(k, flush=True)
    out["followup_strong"] = await followup_strong()
    Path(__file__).with_name("results2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str))
asyncio.run(main())
