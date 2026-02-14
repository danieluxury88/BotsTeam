"""Analyzer — sends grouped git history to Claude and returns a summary."""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """\
You are GitBot, an expert software engineer assistant specializing in code review and project analysis.

Your job is to analyze a grouped git commit history and produce a clear, high-level summary that helps
developers and project managers quickly understand:
- What has been worked on recently
- Which areas of the codebase are most active
- Any patterns worth highlighting (e.g. bug-fix bursts, feature development phases, refactoring periods)
- A brief assessment of development velocity and team activity

Guidelines:
- Be concise and direct. Avoid filler phrases.
- Group your observations naturally — don't just restate the commit list.
- Use developer-friendly language.
- If you spot anything noteworthy (e.g. many fixes in one area, or a quiet period followed by heavy activity), call it out.
- Format your response in clean Markdown with sections.
"""


def analyze_history(
    formatted_history: str,
    repo_name: str = "repository",
    model: str | None = None,
) -> str:
    """Send commit history to Claude and return a markdown summary."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )

    effective_model = (
        model
        or os.environ.get("GITBOT_MODEL")
        or "claude-haiku-4-5-20251001"  # Fast and cost-effective for this task
    )

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""\
Please analyze the following git history for the **{repo_name}** repository and provide a high-level summary.

{formatted_history}

Produce a structured report with:
1. **Overview** — one paragraph summarizing the overall activity
2. **Key Changes** — the most significant work done, grouped logically
3. **Active Areas** — which parts of the codebase saw the most activity
4. **Observations** — any patterns, concerns, or highlights worth noting
"""

    message = client.messages.create(
        model=effective_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text
