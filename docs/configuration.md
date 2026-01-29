# Configuration Reference

WhatThePatch uses a YAML configuration file. Copy `config.example.yaml` to `config.yaml` and customize as needed.

## Quick Setup

The easiest way to configure is via the setup wizard:

```bash
python setup.py
```

This interactively creates your `config.yaml` with all necessary settings.

## Configuration File Location

The tool looks for configuration in this order:
1. `./config.yaml` (current directory)
2. `~/.whatthepatch/config.yaml` (home directory)

## Full Configuration Options

### Engine Selection

```yaml
# Active engine - which AI to use for reviews
engine: "claude-api"
```

Available engines: `claude-api`, `claude-cli`, `openai-api`, `openai-codex-cli`, `gemini-api`, `gemini-cli`, `ollama`

See [engines.md](engines.md) for detailed configuration of each engine.

### Repository Access Tokens

```yaml
tokens:
  # GitHub Personal Access Token
  # Create at: https://github.com/settings/tokens
  # Required scopes: repo (for private repos)
  github: "ghp_..."

  # Bitbucket App Password
  # Create at: https://bitbucket.org/account/settings/app-passwords/
  # Required permissions: Repositories (Read)
  bitbucket_username: "your-username"
  bitbucket_app_password: "..."
```

| Setting | Description |
|---------|-------------|
| `tokens.github` | GitHub Personal Access Token |
| `tokens.bitbucket_username` | Bitbucket username |
| `tokens.bitbucket_app_password` | Bitbucket App Password |

### Output Settings

```yaml
output:
  # Directory where review files will be saved
  # Supports ~ for home directory
  directory: "~/pr-reviews"

  # Filename pattern. Available variables:
  # {repo} - repository name
  # {pr_number} - PR number
  # {ticket_id} - extracted ticket ID (or "NO-TICKET" if not found)
  # {branch} - source branch name (sanitized)
  # Note: Extension is added automatically based on format setting
  filename_pattern: "{repo}-{pr_number}"

  # Output format: md (markdown), txt (plain text), or html (styled HTML)
  # Can be overridden with --format flag, or changed with --switch-output
  format: "html"

  # Auto-open file after generation
  # Opens in browser for HTML, default text editor for md/txt
  # Can be disabled with --no-open flag
  auto_open: true
```

| Setting | Description | Default |
|---------|-------------|---------|
| `output.directory` | Where to save review files | `~/pr-reviews` |
| `output.filename_pattern` | Filename template | `{repo}-{pr_number}` |
| `output.format` | Output format: `html`, `md`, or `txt` | `html` |
| `output.auto_open` | Auto-open file after generation | `true` |

#### Filename Pattern Variables

| Variable | Description |
|----------|-------------|
| `{repo}` | Repository name |
| `{pr_number}` | PR number |
| `{ticket_id}` | Extracted ticket ID (or "NO-TICKET") |
| `{branch}` | Source branch name (sanitized) |

### Ticket ID Extraction

```yaml
ticket:
  # Regex pattern to extract ticket ID from branch name
  # Default matches patterns like: ABC-123, JIRA-456, PROJ-789
  # The first capture group is used as the ticket ID
  pattern: "([A-Z]+-\\d+)"

  # Fallback if no ticket ID found
  fallback: "NO-TICKET"
```

| Setting | Description | Default |
|---------|-------------|---------|
| `ticket.pattern` | Regex to extract ticket ID from branch | `([A-Z]+-\d+)` |
| `ticket.fallback` | Value if no ticket ID found | `NO-TICKET` |

## Output Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| `html` | `.html` | Styled HTML (default) - GitHub-like styling with syntax highlighting |
| `md` | `.md` | Markdown - Best for viewing in code editors or GitHub |
| `txt` | `.txt` | Plain text - Same as markdown but with .txt extension |

Use `wtp --switch-output` to change the default format, or `--format` flag for a one-time override.

### HTML Output Features

- GitHub-inspired styling with clean typography
- Automatic dark/light mode based on system preferences
- Syntax highlighting for code blocks (powered by Pygments)
- Responsive layout for different screen sizes
- Self-contained file (all CSS embedded)

### Auto-Open Behavior

- **HTML files**: Open in your default web browser
- **MD/TXT files**: Open in your default text editor
- Disable with `--no-open` flag or set `auto_open: false` in config

## Example Configuration

```yaml
# WhatThePatch Configuration

engine: "claude-api"

engines:
  claude-api:
    api_key: "sk-ant-api03-..."
    model: "claude-sonnet-4-20250514"
    max_tokens: 4096

tokens:
  github: "ghp_..."
  bitbucket_username: "your-username"
  bitbucket_app_password: "..."

output:
  directory: "~/pr-reviews"
  filename_pattern: "{repo}-{pr_number}"
  format: "html"
  auto_open: true

ticket:
  pattern: "([A-Z]+-\\d+)"
  fallback: "NO-TICKET"
```

## Verifying Configuration

Test your configuration with:

```bash
wtp --test-config
```

This verifies:
- All tokens and API keys are valid
- Connections to services work
- Engine configuration is correct
