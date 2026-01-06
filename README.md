# WhatThePatch

A CLI tool to automatically generate PR reviews using AI. Supports GitHub and Bitbucket pull requests.

## Why This Tool?

Software development has never moved faster. With the evolution of AI-assisted coding, changes are being pushed at unprecedented speed. While this acceleration is exciting, it also presents a challenge: how do we ensure we truly understand the code we're approving?

WhatThePatch was created to help developers digest and understand changes in their codebase. Instead of blindly approving pull requests or spending hours manually reviewing complex diffs, this tool leverages AI to provide comprehensive, intelligent code reviews that highlight potential issues, security concerns, and areas that need attention.

The goal isn't to replace human judgment, but to augment it - giving reviewers the insights they need to make informed decisions quickly and confidently.

## How It Compares

There are several AI-powered PR review tools available. Here's how WhatThePatch differs:

| Feature | WhatThePatch | CodeRabbit, PR-Agent, etc. |
|---------|--------------|---------------------------|
| **Hosting** | Self-hosted, runs locally | Cloud/SaaS |
| **Privacy** | Code only sent to your chosen AI provider | Code processed by third-party servers |
| **Output** | Local markdown files you own | Comments on PR (may disappear) |
| **Review Prompt** | Fully customizable | Fixed or limited configuration |
| **Bitbucket Support** | Native support | Limited or no support |
| **GitHub Support** | Native support | Yes |
| **Cost Model** | Pay-per-use API or free via CLI tools | Monthly subscription |
| **Team Auth** | Works with Claude Code/Codex team plans | Separate subscription required |
| **Offline Archive** | Reviews saved locally forever | Dependent on service availability |

### When to Use WhatThePatch

- You want **full control** over how reviews are conducted
- You need **Bitbucket support** alongside GitHub
- You prefer **local archives** of all reviews
- You're already paying for **Claude API, OpenAI API, or CLI tools**
- **Privacy matters** - you don't want code on additional third-party servers
- You want to **customize review criteria** to match your team's standards

### Alternative Tools

If you prefer SaaS solutions that comment directly on PRs:

- **[CodeRabbit](https://coderabbit.ai)** - AI PR reviews for GitHub/GitLab
- **[PR-Agent](https://github.com/Codium-ai/pr-agent)** - Open source, by CodiumAI
- **[GitHub Copilot](https://github.com/features/copilot)** - Native GitHub integration

## Requirements

- Python 3.8+
- One of the following for AI access:
  - Anthropic API key (for Claude), OR
  - Claude Code CLI installed and authenticated, OR
  - OpenAI API key (for GPT-4o), OR
  - OpenAI Codex CLI installed and authenticated
- GitHub token (for GitHub PRs) and/or Bitbucket app password (for Bitbucket PRs)

## Platform Support

This tool is designed for **macOS and Linux**. Here's the compatibility breakdown:

| Component | macOS/Linux | Windows |
|-----------|-------------|---------|
| Core Python script | Works | Works |
| AI Engines (API/CLI) | Works | Works |
| Config/YAML handling | Works | Works |
| API calls (GitHub/Bitbucket) | Works | Works |
| CLI installation (`wtp` command) | Works | Not supported |
| Interactive setup wizard | Works | Partial |

### Windows Users

The core functionality works on Windows, but the CLI installation does not. Windows users can run the tool directly with Python:

```bash
python whatthepatch.py --review https://github.com/owner/repo/pull/123
python whatthepatch.py --status
python whatthepatch.py --test-config
```

The setup wizard will install dependencies and create the config file, but the `wtp` global command will not be available.

## Quick Start

Run the interactive setup wizard:

```bash
python setup.py
```

This will:
1. Install required dependencies
2. Guide you through creating `config.yaml`
3. Test your configuration
4. Install the `wtp` CLI command

Once complete, you can run reviews from anywhere:

```bash
wtp --review https://github.com/owner/repo/pull/123
```

## Manual Setup

If you prefer manual setup:

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

Copy the example config and fill in your values:

```bash
cp config.example.yaml config.yaml
```

### 3. Choose your engine

This tool supports multiple AI engines through a pluggable architecture. Currently available:

#### Option A: Anthropic API (Recommended)

Uses the Anthropic Python SDK directly. Requires an API key.

```yaml
engine: "claude-api"

engines:
  claude-api:
    api_key: "sk-ant-api03-your-key-here"
    model: "claude-sonnet-4-20250514"
    max_tokens: 4096
```

**Pros:**
- Faster execution
- More control over model parameters
- Direct API access

**Requirements:**
- Anthropic API key from https://console.anthropic.com/
- API billing (pay-per-use)

#### Option B: Claude Code CLI

Uses your existing Claude Code installation. Great for team users without personal API keys.

```yaml
engine: "claude-cli"

engines:
  claude-cli:
    path: ""  # Leave empty to use system PATH
    args: []  # Additional arguments
```

**Pros:**
- Uses existing team authentication
- No additional API key needed
- Same billing as your Claude Code usage

**Requirements:**
- Claude Code CLI installed and authenticated
- `claude` command available in PATH (or configure `engines.claude-cli.path`)

#### Option C: OpenAI API

Uses the OpenAI Python SDK. Supports GPT-4o and other OpenAI models.

```yaml
engine: "openai-api"

engines:
  openai-api:
    api_key: "sk-your-key-here"
    model: "gpt-4o"
    max_tokens: 4096
```

**Pros:**
- Access to GPT-4o and other OpenAI models
- Alternative to Claude if preferred
- Direct API access

**Requirements:**
- OpenAI API key from https://platform.openai.com/api-keys
- API billing (pay-per-use)

#### Option D: OpenAI Codex CLI

Uses your existing OpenAI Codex CLI installation. Great for ChatGPT Plus/Pro/Team users.

```yaml
engine: "openai-codex-cli"

engines:
  openai-codex-cli:
    path: ""  # Leave empty to use system PATH
    model: "gpt-5-codex"
    api_key: ""  # Optional, uses ChatGPT sign-in by default
```

**Pros:**
- Uses existing ChatGPT authentication
- No additional API key needed
- Same billing as your ChatGPT subscription

**Requirements:**
- OpenAI Codex CLI installed: `npm install -g @openai/codex`
- ChatGPT Plus, Pro, Business, Edu, or Enterprise subscription
- Run `codex` once to sign in with your ChatGPT account

### 4. Configure repository access

For both GitHub and Bitbucket private repositories, you need tokens:

- **GitHub Token**: Create at https://github.com/settings/tokens (scope: `repo`)
- **Bitbucket App Password**: Create at https://bitbucket.org/account/settings/app-passwords/ (permission: Repositories Read)

### 5. Install CLI command (optional)

To use `wtp` from anywhere:

```bash
python setup.py
# Select option 5: "Install CLI command only"
```

This creates the `wtp` command in `~/.local/bin/`.

## Usage

After running `python setup.py`, the `wtp` command will be available:

```bash
wtp --review <PR_URL>
```

### Examples

```bash
# GitHub PR (default: markdown format, auto-opens)
wtp --review https://github.com/owner/repo/pull/123

# Bitbucket PR
wtp --review https://bitbucket.org/workspace/repo/pull-requests/456

# Output as HTML (opens in browser)
wtp --review https://github.com/owner/repo/pull/123 --format html

# Output as plain text
wtp --review https://github.com/owner/repo/pull/123 --format txt

# Don't auto-open the file
wtp --review https://github.com/owner/repo/pull/123 --no-open
```

The review will be saved to the configured output directory (default: `~/pr-reviews/`).

### CLI Commands

| Command | Description |
|---------|-------------|
| `wtp --review <URL>` | Generate a review for the given PR |
| `wtp --review <URL> --format <fmt>` | Output in specific format: md, txt, or html |
| `wtp --review <URL> --no-open` | Don't auto-open the file after generation |
| `wtp --help` | Show help and usage information |
| `wtp --status` | Show current configuration and active AI engine |
| `wtp --switch-engine` | Switch between configured AI engines |
| `wtp --test-config` | Test your configuration (tokens, API keys) |
| `wtp --update` | Update the tool from the git repository |
| `wtp --show-prompt` | Display the current review prompt template |
| `wtp --edit-prompt` | Open the prompt template in your editor |

### Setup Commands

| Command | Description |
|---------|-------------|
| `python setup.py` | Run interactive setup wizard |
| `python setup.py --uninstall` | Remove the CLI command |

### Without CLI Installation

If you prefer not to install the CLI command, you can run directly:

```bash
python /path/to/whatthepatch.py --review <PR_URL>
python /path/to/whatthepatch.py --test-config
```

## Configuration Reference

See `config.example.yaml` for all available options:

### Engine Settings

| Setting | Description |
|---------|-------------|
| `engine` | Active engine: `"claude-api"`, `"claude-cli"`, `"openai-api"`, or `"openai-codex-cli"` |

### Engine-Specific Configuration

**Claude API (`engines.claude-api`)**

| Setting | Description |
|---------|-------------|
| `api_key` | Anthropic API key (required) |
| `model` | Claude model to use (default: `claude-sonnet-4-20250514`) |
| `max_tokens` | Max response length (default: `4096`) |

**Claude CLI (`engines.claude-cli`)**

| Setting | Description |
|---------|-------------|
| `path` | Path to claude executable (leave empty for system PATH) |
| `args` | Additional arguments to pass to claude command |

**OpenAI API (`engines.openai-api`)**

| Setting | Description |
|---------|-------------|
| `api_key` | OpenAI API key (required) |
| `model` | OpenAI model to use (default: `gpt-4o`) |
| `max_tokens` | Max response length (default: `4096`) |

**OpenAI Codex CLI (`engines.openai-codex-cli`)**

| Setting | Description |
|---------|-------------|
| `path` | Path to codex executable (leave empty for system PATH) |
| `model` | Model to use (default: `gpt-5-codex`) |
| `api_key` | Optional API key (uses ChatGPT sign-in if empty) |

### Repository Access Tokens

| Setting | Description |
|---------|-------------|
| `tokens.github` | GitHub Personal Access Token |
| `tokens.bitbucket_username` | Bitbucket username |
| `tokens.bitbucket_app_password` | Bitbucket App Password |

### Output Settings

| Setting | Description |
|---------|-------------|
| `output.directory` | Where to save review files (default: `~/pr-reviews`) |
| `output.filename_pattern` | Filename template. Variables: `{repo}`, `{pr_number}`, `{ticket_id}`, `{branch}` |
| `output.format` | Output format: `md`, `txt`, or `html` (default: `md`) |
| `output.auto_open` | Auto-open file after generation (default: `true`) |

### Ticket ID Extraction

| Setting | Description |
|---------|-------------|
| `ticket.pattern` | Regex to extract ticket ID from branch name (default: `([A-Z]+-\d+)`) |
| `ticket.fallback` | Value if no ticket ID found (default: `NO-TICKET`) |

## Customizing the Review Prompt

The review prompt is stored in `prompt.md`. This file controls how the AI analyzes and reports on pull requests. You can customize it to match your team's coding standards, focus areas, and review preferences.

### Viewing and Editing the Prompt

```bash
# View the current prompt
wtp --show-prompt

# Open in your default editor
wtp --edit-prompt
```

The `--edit-prompt` command uses your `$EDITOR` or `$VISUAL` environment variable. If not set, it tries `code`, `nano`, `vim`, or `vi` in that order.

### What You Can Customize

- **Review focus areas** - Security, performance, maintainability, etc.
- **Output format** - Structure of the review report
- **Severity definitions** - What constitutes High/Medium/Low issues
- **Coding standards** - Your team's specific conventions
- **Additional instructions** - Any special requirements

### Available Template Variables

| Variable | Description |
|----------|-------------|
| `{ticket_id}` | Extracted ticket ID from branch name |
| `{pr_title}` | Pull request title |
| `{source_branch}` | Source branch name |
| `{target_branch}` | Target branch name |
| `{pr_description}` | PR description body |
| `{diff}` | The full diff content |

## Sample Output

```markdown
# PR Review: ABC-123 - Add user authentication middleware

## Summary

This PR adds JWT-based authentication middleware to protect API endpoints.

**Changes:**
- Added new file `src/middleware/auth.ts`
- Modified `src/routes/index.ts` to apply middleware
- Added auth configuration to `config/default.json`

---

## Issues Found

### High: Missing token expiration validation

**File:** `src/middleware/auth.ts:24-28`

The JWT verification does not check for token expiration.

```typescript
const decoded = jwt.verify(token, config.secret);
req.user = decoded;
```

Expired tokens will still be accepted, creating a security risk.

**Recommendations:**
1. Add `maxAge` option to jwt.verify()
2. Check `decoded.exp` against current timestamp

---

### Medium: Hardcoded secret in fallback

**File:** `src/middleware/auth.ts:8`

```typescript
const secret = config.secret || 'default-secret';
```

Fallback to hardcoded secret is dangerous in production.

**Recommendations:**
1. Remove the fallback entirely
2. Throw an error if secret is not configured

---

## Observations (Not Issues)

1. **Good error handling** - Auth failures return appropriate 401 status codes
2. **Clean separation** - Middleware is properly isolated from route logic

---

## Suggested Test Cases

1. Verify valid tokens are accepted
2. Verify expired tokens are rejected
3. Verify malformed tokens return 401
4. Verify missing Authorization header returns 401
5. Test with missing config.secret (should fail to start)

---

## Verdict

**Needs Minor Changes**

Security-related issues with token expiration and fallback secret should be addressed before merging.
```

## Troubleshooting

### "wtp: command not found"

The CLI command is not in your PATH. Either:
1. Run `python setup.py` and select "Install CLI command only"
2. Add `~/.local/bin` to your PATH:
   ```bash
   export PATH="$PATH:$HOME/.local/bin"
   ```
   Add this line to your `~/.zshrc` or `~/.bashrc` to make it permanent.

### "anthropic package not installed"

Run: `pip install anthropic`

### "openai package not installed"

Run: `pip install openai`

### "claude command not found"

Either:
1. Install Claude Code: https://claude.ai/code
2. Or set the full path in config under `engines.claude-cli.path: "/path/to/claude"`

### Test your configuration

Run `wtp --test-config` to verify all tokens and credentials are working.

### API rate limits

If you hit rate limits with the API engine, consider:
- Using a model with higher limits
- Switching to CLI engine which uses your team's quota

### Uninstall

To remove the CLI command:
```bash
python setup.py --uninstall
```

## Author

**Aaron Medina**

- GitHub: [https://github.com/aaronmedina-dev](https://github.com/aaronmedina-dev)
- LinkedIn: [https://www.linkedin.com/in/aamedina/](https://www.linkedin.com/in/aamedina/)
