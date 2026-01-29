# Customizing the Review Prompt

**This is what sets WhatThePatch apart from other AI-powered PR review tools.**

Most PR review tools offer limited or no customization - you get a generic review output regardless of whether you're a DevOps engineer reviewing Terraform configs, a frontend developer checking React components, or a backend engineer analyzing API endpoints. WhatThePatch gives you complete control over the review process through a single, editable file: `prompt.md`.

## Why Customize?

The `prompt.md` file is the brain of your reviews. It controls:
- **What the AI looks for** - Define focus areas specific to your role (security, accessibility, performance, etc.)
- **How issues are categorized** - Set severity definitions that match your team's standards
- **What the output looks like** - Structure the report format to your preferences
- **Domain-specific rules** - Add checks for your tech stack (e.g., "Flag N+1 queries", "Check for missing ARIA labels")
- **Your coding standards** - Embed your team's or organisation's conventions directly into the review criteria

**Any changes you make to `prompt.md` directly impact the output.** A DevOps-focused prompt will catch infrastructure risks and security issues. A frontend-focused prompt will highlight accessibility violations and performance concerns. You're not locked into a one-size-fits-all review - you get reviews tailored to what actually matters for your work.

## Viewing and Editing the Prompt

```bash
# View the current prompt
wtp --show-prompt

# Open in your default editor
wtp --edit-prompt
```

The `--edit-prompt` command uses your `$EDITOR` or `$VISUAL` environment variable. If not set, it tries `code`, `nano`, `vim`, or `vi` in that order.

## Role-Based Prompt Templates

Different roles have different review priorities. WhatThePatch includes example templates in `prompt-templates/` that you can use as starting points:

| Template | Focus Areas |
|----------|-------------|
| `devops-prompt.md` | Infrastructure, CI/CD, security, Docker/K8s, secrets, deployment |
| `frontend-prompt.md` | Accessibility, UX, performance, responsive design, state management |
| `backend-prompt.md` | API design, database queries, auth, data validation, error handling |
| `microservices-prompt.md` | AWS Lambda, CDK, serverless patterns, event-driven architecture, observability |

### Using a Template

```bash
# Copy a template to use as your prompt
cp prompt-templates/frontend-prompt.md prompt.md

# Or if installed globally
cp ~/.whatthepatch/prompt-templates/backend-prompt.md ~/.whatthepatch/prompt.md
```

## Customizing for Your Role

The prompt file has several sections you can modify:

### 1. Role Description

Tell the AI what perspective to review from:

```markdown
You are a DevOps engineer reviewing a pull request...
```

### 2. Focus Areas

List specific things to look for:

```markdown
## Review Focus Areas
- **Security**: Secrets exposure, IAM policies...
- **Infrastructure**: Terraform, Kubernetes...
```

### 3. Severity Definitions

Define what each severity level means for your domain:

```markdown
- **Critical**: Security vulnerabilities, secrets exposure...
- **High**: Missing resource limits, no rollback strategy...
```

### 4. Domain-Specific Rules

Add rules for your tech stack:

```markdown
- Flag any hardcoded values that should be environment variables
- Note any missing health checks or readiness probes
```

## What You Can Customize

- **Review focus areas** - Security, performance, maintainability, etc.
- **Output format** - Structure of the review report
- **Severity definitions** - What constitutes Critical/High/Medium/Low issues
- **Coding standards** - Your team's specific conventions
- **Domain-specific rules** - Things unique to your tech stack or role
- **Test case suggestions** - What kinds of tests to recommend

## Tips for Effective Prompts

1. **Be specific about priorities** - List exactly what matters most for your role
2. **Define severity clearly** - Give concrete examples for each level
3. **Add domain context** - Mention your tech stack (e.g., "We use PostgreSQL and Redis")
4. **Include anti-patterns** - List specific things to flag (e.g., "Flag any SELECT * queries")
5. **Set the tone** - Specify if you want concise or detailed explanations

## Available Template Variables

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

## Output Quality by Engine

**Important:** Not all AI engines follow prompt templates equally well.

| Engine | Format Compliance | Notes |
|--------|-------------------|-------|
| Claude API | Excellent | Follows template structure precisely |
| OpenAI API | Excellent | Follows template structure precisely |
| Gemini API | Excellent | Follows template structure precisely |
| CLI engines | Same as API | Uses same underlying models |
| Ollama (7B models) | Poor to moderate | Often ignores or simplifies structure |
| Ollama (13B+ models) | Moderate | Better but still inconsistent |

### Why Local Models Differ

Local models (Ollama) running 7B-13B parameter models are optimized for code understanding, but **not** for following complex output format instructions. The prompt template requires:

- Precise markdown structure with specific sections
- Severity emojis and consistent formatting
- File paths and line numbers in specific formats
- Structured recommendations

Smaller models often produce useful code insights but may:
- Skip or merge sections
- Ignore severity formatting
- Provide less structured output
- Vary significantly between runs

**This is a fundamental model capability gap, not something that can be fixed through prompt engineering.** WhatThePatch includes a default system prompt for Ollama that helps, but cannot fully solve the limitation.

### Recommendations

- **For consistent, structured reviews:** Use cloud APIs (Claude, OpenAI, Gemini)
- **For privacy-first or offline reviews:** Use Ollama, but expect variable formatting
- **For Ollama:** Consider simpler prompt templates that don't rely on precise structure
