# ReportBot

`reportbot` reviews, improves, and translates Markdown reports.

The bot keeps its behavior in Markdown prompt files under `reportbot/prompts/`:

- `review.md`: instructions for critique and feedback
- `improve.md`: instructions for rewriting and polishing
- `translate.md`: instructions for translation while preserving Markdown structure

That keeps iteration cheap: change the prompt text without touching the analyzer.

## Examples

```bash
uv run reportbot review path/to/report.md
uv run reportbot improve path/to/report.md --output improved.md
uv run reportbot translate path/to/report.md --lang de --output translated.md
uv run reportbot review path/to/report.md --instructions-file custom-review.md
```
