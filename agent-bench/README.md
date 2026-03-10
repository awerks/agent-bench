Minimal ReAct-style CLI agent. The agent can run manually or from JSONL benchmark tasks, uses sandboxed local tools and mock APIs, and records JSONL traces for every run.

## Setup

```bash
cd agent-security-research
python3 -m pip install -e .
```

Live Gemini runs need `GEMINI_API_KEY` in the shell or in `../.env` / `.env`.
Set `GEMINI_MODEL` to override the profile default, for example `gemini-2.5-flash`.

### Usage

baseline config

```bash
asr-agent eval \
  --tasks data/attack_tasks.jsonl \
  --config configs/baseline.yaml \
  --planner gemini
```

allow_list defenses

```bash
asr-agent eval \
  --tasks data/attack_tasks.jsonl \
  --config configs/allowlist_confirm.yaml \
  --planner gemini
```

memory defenses

```bash
asr-agent eval \
  --tasks data/attack_tasks.jsonl \
  --config configs/memory_enabled.yaml \
  --planner gemini
```

labeling defenses

```bash
asr-agent eval \
  --tasks data/attack_tasks.jsonl \
  --config configs/labeling_validation.yaml \
  --planner gemini
```

The tools are synthetic. Email, calendar, ticketing, web, PDF, memory, filesystem, and MCP actions are all local mock actions. Filesystem access is restricted to a per-run directory under `data/sandbox`.
