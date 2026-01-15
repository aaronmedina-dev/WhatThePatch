![WhatThePatch!? Banner](assets/wtp_banner.png)

# WhatThePatch!?

A CLI tool to automatically generate PR reviews using AI. Supports GitHub and Bitbucket pull requests.

![WhatThePatch!? Info Graphic](assets/wtp-info-graphics.jpg)

## Why This Tool?

Software development has never moved faster. With the evolution of AI-assisted coding, changes are being pushed at unprecedented speed. While this acceleration is exciting, it also presents a challenge: how do we ensure we truly understand the code we're approving?

WhatThePatch!? was created to help developers digest and understand changes in their codebase. Instead of blindly approving pull requests or spending hours manually reviewing complex diffs, this tool leverages AI to provide comprehensive, intelligent code reviews that highlight potential issues, security concerns, and areas that need attention.

The goal isn't to replace human judgment, but to augment it - giving reviewers the insights they need to make informed decisions quickly and confidently.

## How It Compares

There are several AI-powered PR review tools available. Here's how WhatThePatch!? differs:

| Feature | WhatThePatch!? | CodeRabbit, PR-Agent, etc. |
|---------|----------------|---------------------------|
| **Hosting** | Self-hosted, runs locally | Cloud/SaaS |
| **Privacy** | Code only sent to your chosen AI provider | Code processed by third-party servers |
| **External Context** | Add private repos/files as context | Limited to public/connected repos |
| **Output Formats** | Markdown, plain text, or styled HTML | PR comments only |
| **Review Prompt** | Fully customizable | Fixed or limited configuration |
| **Bitbucket Support** | Native support | Limited or no support |
| **GitHub Support** | Native support | Yes |
| **Cost Model** | Pay-per-use API or free via CLI tools | Monthly subscription |
| **Team Auth** | Works with Claude Code/Codex team plans | Separate subscription required |
| **Offline Archive** | Reviews saved locally forever | Dependent on service availability |

### When to Use WhatThePatch!?

- You want **full control** over how reviews are conducted
- You're working with **multiple repo providers** and/or accounts
- You prefer **local archives** of all reviews
- You're already paying for **Claude API, OpenAI API, or CLI tools**
- **Privacy matters** - you don't want code on additional third-party servers
- **Customize review criteria** to match your job role, tech stack, and team's or organisation standards
- Your PRs **reference external private repositories** that cloud tools can't access

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
| Core Python script | ✅ | ✅ |
| AI Engines (API/CLI) | ✅ | ✅ |
| Config/YAML handling | ✅ | ✅ |
| API calls (GitHub/Bitbucket) | ✅ | ✅ |
| CLI installation (`wtp` command) | ✅ | Not supported |
| Interactive setup wizard | ✅ | Partial |

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
# GitHub PR (default: html format, auto-opens in browser)
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

### Output Formats

WhatThePatch!? supports three output formats:

| Format | Extension | Description |
|--------|-----------|-------------|
| `html` | `.html` | Styled HTML (default) - GitHub-like styling with syntax highlighting |
| `md` | `.md` | Markdown - Best for viewing in code editors or GitHub |
| `txt` | `.txt` | Plain text - Same as markdown but with .txt extension |

Use `wtp --switch-output` to change the default format, or `--format` flag for a one-time override.

**HTML Output Features:**
- GitHub-inspired styling with clean typography
- Automatic dark/light mode based on system preferences
- Syntax highlighting for code blocks (powered by Pygments)
- Responsive layout for different screen sizes
- Self-contained file (all CSS embedded)

**Auto-Open Behavior:**
- **HTML files**: Open in your default web browser
- **MD/TXT files**: Open in your default text editor
- Disable with `--no-open` flag or set `auto_open: false` in config

### ⭐️ Adding External Context

**This is one of the biggest advantages of a local PR review tool.**

Cloud-based PR review services can only see code that's publicly accessible or connected to their platform. When your PR references:
- Private shared libraries
- Internal packages from other repositories
- Proprietary frameworks or utilities
- Code from repositories on different platforms

...these services make assumptions or miss important context entirely.

WhatThePatch!? solves this by letting you include **any local files or directories** as additional context for the AI review:

**Examples:**

```bash
# Include a private shared library
wtp --review <URL> --context /path/to/internal-shared-lib

# Include type definitions from another repo
wtp --review <URL> -c /path/to/private-types-repo/src/types

# Include multiple context sources
wtp --review <URL> -c /path/to/auth-service -c /path/to/shared-utils
```

**How it works:**
1. Files are read recursively from specified paths
2. Content is added to the AI prompt as "External Context"
3. The AI uses this context to understand references in your PR
4. Binary files and common non-code directories (node_modules, .git, etc.) are automatically excluded

**Size management:**
If the combined context exceeds ~100KB, you'll be prompted to confirm before proceeding to avoid excessive API costs.

### Testing and Debugging

Use `--dry-run` and `--verbose` flags to test your setup without making AI API calls:

**Dry Run (`--dry-run`):**
Shows what would be sent to the AI without actually calling it. Useful for:
- Verifying external context is being picked up correctly
- Checking prompt size before incurring API costs
- Testing configuration without waiting for AI response

```bash
# Test a review without calling AI
wtp --review <URL> --dry-run

# Test with external context
wtp --review <URL> --context /path/to/lib --dry-run
```

**Verbose Mode (`--verbose`, `-v`):**
Shows detailed output including a preview of the prompt that will be sent. Useful for:
- Debugging prompt template issues
- Seeing exactly what context is included
- Verifying all template variables are populated correctly

```bash
# See prompt preview (still makes AI call)
wtp --review <URL> --verbose

# Combine with dry-run for full inspection without API call
wtp --review <URL> -c /path/to/lib -v --dry-run
```

**Testing Context Reading:**
A test script is included for testing context reading independently:

```bash
# Test reading a directory
python test_context.py ./engines

# Test reading multiple paths
python test_context.py ./banner.py ./prompt.md /path/to/external/repo
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `wtp --review <URL>` | Generate a review for the given PR |
| `wtp --review <URL> --context PATH` | Add local file/directory as context (repeatable with `-c`) |
| `wtp --review <URL> --dry-run` | Show what would be sent without calling the AI |
| `wtp --review <URL> --verbose` | Show detailed output including prompt preview |
| `wtp --review <URL> --format <fmt>` | Override output format for this review: html, md, or txt |
| `wtp --review <URL> --no-open` | Don't auto-open the file after generation |
| `wtp --help` | Show help and usage information |
| `wtp --status` | Show current configuration and active AI engine |
| `wtp --switch-engine` | Switch between configured AI engines |
| `wtp --switch-output` | Switch default output format (html, md, txt) |
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
| `output.format` | Output format: `html`, `md`, or `txt` (default: `html`) |
| `output.auto_open` | Auto-open file after generation (default: `true`) |

### Ticket ID Extraction

| Setting | Description |
|---------|-------------|
| `ticket.pattern` | Regex to extract ticket ID from branch name (default: `([A-Z]+-\d+)`) |
| `ticket.fallback` | Value if no ticket ID found (default: `NO-TICKET`) |

## Customizing the Review Prompt

**This is what sets WhatThePatch!? apart from other AI-powered PR review tools.**

Most PR review tools offer limited or no customization - you get a generic review output regardless of whether you're a DevOps engineer reviewing Terraform configs, a frontend developer checking React components, or a backend engineer analyzing API endpoints. WhatThePatch!? gives you complete control over the review process through a single, editable file: `prompt.md`.

The `prompt.md` file is the brain of your reviews. It controls:
- **What the AI looks for** - Define focus areas specific to your role (security, accessibility, performance, etc.)
- **How issues are categorized** - Set severity definitions that match your team's standards
- **What the output looks like** - Structure the report format to your preferences
- **Domain-specific rules** - Add checks for your tech stack (e.g., "Flag N+1 queries", "Check for missing ARIA labels")
- **Your coding standards** - Embed your team's or organisation's conventions directly into the review criteria

**Any changes you make to `prompt.md` directly impact the output.** A DevOps-focused prompt will catch infrastructure risks and security issues. A frontend-focused prompt will highlight accessibility violations and performance concerns. You're not locked into a one-size-fits-all review - you get reviews tailored to what actually matters for your work.

### Viewing and Editing the Prompt

```bash
# View the current prompt
wtp --show-prompt

# Open in your default editor
wtp --edit-prompt
```

The `--edit-prompt` command uses your `$EDITOR` or `$VISUAL` environment variable. If not set, it tries `code`, `nano`, `vim`, or `vi` in that order.

### Role-Based Prompt Templates

Different roles have different review priorities. WhatThePatch!? includes example templates in `prompt-templates/` that you can use as starting points:

| Template | Focus Areas |
|----------|-------------|
| `devops-prompt.md` | Infrastructure, CI/CD, security, Docker/K8s, secrets, deployment |
| `frontend-prompt.md` | Accessibility, UX, performance, responsive design, state management |
| `backend-prompt.md` | API design, database queries, auth, data validation, error handling |

**To use a template:**

```bash
# Copy a template to use as your prompt
cp prompt-templates/frontend-prompt.md prompt.md

# Or if installed globally
cp ~/.whatthepatch/prompt-templates/backend-prompt.md ~/.whatthepatch/prompt.md
```

### Customizing for Your Role

The prompt file has several sections you can modify:

1. **Role Description** - Tell the AI what perspective to review from
   ```markdown
   You are a DevOps engineer reviewing a pull request...
   ```

2. **Focus Areas** - List specific things to look for
   ```markdown
   ## Review Focus Areas
   - **Security**: Secrets exposure, IAM policies...
   - **Infrastructure**: Terraform, Kubernetes...
   ```

3. **Severity Definitions** - Define what each severity level means for your domain
   ```markdown
   - **Critical**: Security vulnerabilities, secrets exposure...
   - **High**: Missing resource limits, no rollback strategy...
   ```

4. **Rules** - Add domain-specific rules
   ```markdown
   - Flag any hardcoded values that should be environment variables
   - Note any missing health checks or readiness probes
   ```

### What You Can Customize

- **Review focus areas** - Security, performance, maintainability, etc.
- **Output format** - Structure of the review report
- **Severity definitions** - What constitutes Critical/High/Medium/Low issues
- **Coding standards** - Your team's specific conventions
- **Domain-specific rules** - Things unique to your tech stack or role
- **Test case suggestions** - What kinds of tests to recommend

### Tips for Effective Prompts

1. **Be specific about priorities** - List exactly what matters most for your role
2. **Define severity clearly** - Give concrete examples for each level
3. **Add domain context** - Mention your tech stack (e.g., "We use PostgreSQL and Redis")
4. **Include anti-patterns** - List specific things to flag (e.g., "Flag any SELECT * queries")
5. **Set the tone** - Specify if you want concise or detailed explanations

### Available Template Variables

| Variable | Description |
|----------|-------------|
| `{ticket_id}` | Extracted ticket ID from branch name |
| `{pr_title}` | Pull request title |
| `{pr_url}` | Full URL of the pull request |
| `{pr_author}` | PR author's username or display name |
| `{source_branch}` | Source branch name |
| `{target_branch}` | Target branch name |
| `{pr_description}` | PR description body |
| `{external_context}` | External context from `--context` flag (or "No external context provided.") |
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
