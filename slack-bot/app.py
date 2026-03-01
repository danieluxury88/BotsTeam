import os
import subprocess
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in your shell or .env file."
        )
    return value


SLACK_BOT_TOKEN = require_env("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = require_env("SLACK_APP_TOKEN")

# 1) Slack app
app = App(token=SLACK_BOT_TOKEN, token_verification_enabled=False)

# 2) VERY IMPORTANT: restrict what can be executed (allowlist)
ALLOWED = {
    "ls": ["ls", "-al"],
    "df": ["df", "-h"],
    "uptime": ["uptime"],
    "whoami": ["whoami"],
    "gitman list": ["gitman", "list"],
}

def run_in_wsl(argv: list[str]) -> str:
    """
    Runs the command in the current WSL distro (because this script runs in WSL).
    """
    p = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=10,
    )
    out = (p.stdout + p.stderr).strip()
    if not out:
        out = "(no output)"
    return out[:3500]  # Slack message safety limit-ish

@app.command("/wsl")
def handle_wsl_command(ack, respond, command):
    ack()

    text = (command.get("text") or "").strip()
    # Examples: "/wsl ls", "/wsl df", "/wsl gitman list"
    key = " ".join(text.split())

    if key not in ALLOWED:
        respond(
            "Allowed commands: " + ", ".join(sorted(ALLOWED.keys())) +
            "\nExamples: `/wsl ls`, `/wsl gitman list`"
        )
        return

    output = run_in_wsl(ALLOWED[key])
    respond(f"```{output}```")

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
