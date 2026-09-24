# flow-review engine

The deterministic engine behind the [flow-review](https://github.com/Bilohit/flow-review) Claude Code plugin. It launches your app, proves it is ready, drives and records user flows, replays them, measures each page (contrast, off-palette colours, overlapping or undersized controls, server and console errors), keeps a findings ledger across runs, and serves a live local dashboard.

It never calls an LLM API. All model work happens in Claude Code through the plugin's agents.

It ships inside the plugin and is installed from GitHub, never from PyPI. Installing the plugin is enough: `flow-review setup-env` installs this folder into a managed venv. To install it on its own:

```bash
pip install "flow-review[web] @ git+https://github.com/Bilohit/flow-review#subdirectory=plugins/flow-review/engine"
python -m playwright install chromium
flow-review --help
```

Main commands: `plan`, `drive`, `replay`, `triage`, `ledger`, `budget`, `serve`.
