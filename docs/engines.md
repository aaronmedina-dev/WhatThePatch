# AI Engines

WhatThePatch supports multiple AI engines through a pluggable architecture. Choose the one that best fits your needs.

## Quick Comparison

| Engine | Type | Auth Required | Best For |
|--------|------|---------------|----------|
| `claude-api` | API | Anthropic API key | Direct API access, full control |
| `claude-cli` | CLI | Claude Code auth | Team users, existing CLI setup |
| `openai-api` | API | OpenAI API key | GPT-4o users, direct API |
| `openai-codex-cli` | CLI | ChatGPT subscription | ChatGPT Plus/Pro/Team users |
| `gemini-api` | API | Google AI API key | Gemini users, competitive pricing |
| `gemini-cli` | CLI | Google auth | Google Cloud users |
| `ollama` | Local | None | Privacy, offline, no API costs |

> **Note for CLI engines:** If you already have Claude Code, Codex, or Gemini CLI installed and authenticated on your system, **no config.yaml setup is required**. WhatThePatch automatically detects these tools and uses your existing authentication. Just set the engine name (e.g., `engine: "claude-cli"`) and you're ready to go.

---

## Claude API

Uses the Anthropic Python SDK directly. Requires an API key.

```yaml
engine: "claude-api"

engines:
  claude-api:
    api_key: "sk-ant-api03-your-key-here"
    model: "claude-sonnet-4-20250514"
    max_tokens: 4096
    available_models:
      - "claude-sonnet-4-20250514"
      - "claude-opus-4-20250514"
      - "claude-3-5-sonnet-20241022"
      - "claude-3-5-haiku-20241022"
```

**Pros:**
- Faster execution
- More control over model parameters
- Direct API access

**Requirements:**
- Anthropic API key from https://console.anthropic.com/
- API billing (pay-per-use)

**Configuration Options:**

| Setting | Description | Default |
|---------|-------------|---------|
| `api_key` | Anthropic API key | Required |
| `model` | Claude model to use | `claude-sonnet-4-20250514` |
| `max_tokens` | Max response length | `4096` |
| `available_models` | Models shown in `--switch-model` | Built-in list |

---

## Claude CLI

Uses your existing Claude Code installation. Great for team users without personal API keys.

```yaml
engine: "claude-cli"

engines:
  claude-cli:
    path: ""  # Leave empty to use system PATH
    args: []  # Additional arguments (optional)
    available_models:
      - "opus"
      - "sonnet"
      - "haiku"
```

**No config.yaml setup required** - if `claude` is in your PATH and authenticated, it's ready to use.

**Pros:**
- Uses existing team authentication
- No additional API key needed
- Same billing as your Claude Code usage

**Requirements:**
- Claude Code CLI installed and authenticated
- `claude` command available in PATH (or configure path)

**Configuration Options:**

| Setting | Description | Default |
|---------|-------------|---------|
| `path` | Path to claude executable | System PATH |
| `args` | Additional CLI arguments | `[]` |
| `available_models` | Models shown in `--switch-model` | `opus`, `sonnet`, `haiku` |

---

## OpenAI API

Uses the OpenAI Python SDK. Supports GPT-4o and other OpenAI models.

```yaml
engine: "openai-api"

engines:
  openai-api:
    api_key: "sk-your-key-here"
    model: "gpt-4o"
    max_tokens: 4096
    available_models:
      - "gpt-4o"
      - "gpt-4o-mini"
      - "gpt-4-turbo"
      - "o1"
      - "o1-mini"
```

**Pros:**
- Access to GPT-4o and other OpenAI models
- Alternative to Claude if preferred
- Direct API access

**Requirements:**
- OpenAI API key from https://platform.openai.com/api-keys
- API billing (pay-per-use)

**Configuration Options:**

| Setting | Description | Default |
|---------|-------------|---------|
| `api_key` | OpenAI API key | Required |
| `model` | OpenAI model to use | `gpt-4o` |
| `max_tokens` | Max response length | `4096` |
| `available_models` | Models shown in `--switch-model` | Built-in list |

---

## OpenAI Codex CLI

Uses your existing OpenAI Codex CLI installation. Great for ChatGPT Plus/Pro/Team users.

```yaml
engine: "openai-codex-cli"

engines:
  openai-codex-cli:
    path: ""  # Leave empty to use system PATH
    model: "gpt-5"
    api_key: ""  # Optional, uses ChatGPT sign-in by default
    available_models:
      - "gpt-5"
      - "gpt-4o"
      - "o1"
```

**No config.yaml setup required** - if `codex` is in your PATH and authenticated, it's ready to use.

**Pros:**
- Uses existing ChatGPT authentication
- No additional API key needed
- Same billing as your ChatGPT subscription

**Requirements:**
- OpenAI Codex CLI installed: `npm install -g @openai/codex`
- ChatGPT Plus, Pro, Business, Edu, or Enterprise subscription
- Run `codex` once to sign in with your ChatGPT account

**Configuration Options:**

| Setting | Description | Default |
|---------|-------------|---------|
| `path` | Path to codex executable | System PATH |
| `model` | Model to use | `gpt-5` |
| `api_key` | Optional API key | ChatGPT sign-in |
| `available_models` | Models shown in `--switch-model` | Built-in list |

---

## Gemini API

Uses the Google Generative AI SDK directly. Supports Gemini 2.0 Flash and other models.

```yaml
engine: "gemini-api"

engines:
  gemini-api:
    api_key: "AIza..."
    model: "gemini-2.0-flash"
    max_tokens: 4096
    available_models:
      - "gemini-2.0-flash"
      - "gemini-2.0-flash-thinking-exp"
      - "gemini-1.5-pro"
      - "gemini-1.5-flash"
```

**Pros:**
- Access to Gemini 2.0 Flash and other Google AI models
- Competitive pricing
- Fast response times

**Requirements:**
- Google AI API key from https://aistudio.google.com/app/apikey
- API billing (pay-per-use)

**Configuration Options:**

| Setting | Description | Default |
|---------|-------------|---------|
| `api_key` | Google AI API key | Required |
| `model` | Gemini model to use | `gemini-2.0-flash` |
| `max_tokens` | Max response length | `4096` |
| `available_models` | Models shown in `--switch-model` | Built-in list |

---

## Gemini CLI

Uses your existing Gemini CLI installation. Great for users with Google Cloud authentication.

```yaml
engine: "gemini-cli"

engines:
  gemini-cli:
    path: ""  # Leave empty to use system PATH
    model: "gemini-2.0-flash"
    api_key: ""  # Optional, uses Google auth or GEMINI_API_KEY
    available_models:
      - "gemini-2.0-flash"
      - "gemini-2.0-flash-thinking-exp"
      - "gemini-1.5-pro"
      - "gemini-1.5-flash"
```

**No config.yaml setup required** - if `gemini` is in your PATH and authenticated, it's ready to use.

**Pros:**
- Uses existing Google authentication
- Can use Google Cloud billing
- No separate API key needed if using `gemini auth` or `GEMINI_API_KEY`

**Requirements:**
- Gemini CLI installed from: https://github.com/google-gemini/gemini-cli
- Google account with AI access
- Run `gemini auth` to sign in, or set `GEMINI_API_KEY` environment variable

**Configuration Options:**

| Setting | Description | Default |
|---------|-------------|---------|
| `path` | Path to gemini executable | System PATH |
| `model` | Model to use | `gemini-2.0-flash` |
| `api_key` | Optional API key | Google auth or env var |
| `available_models` | Models shown in `--switch-model` | Built-in list |

---

## Ollama (Local Models)

Run AI models entirely on your local machine. No API key required, no cloud services - complete privacy and offline capability.

```yaml
engine: "ollama"

engines:
  ollama:
    host: "localhost:11434"
    model: "codellama"
    timeout: 300
    # num_ctx: 32768  # Optional context window override
    # system_prompt: "Custom prompt"  # Optional
    available_models:
      - "codellama"
      - "codellama:13b"
      - "llama3.2"
      - "deepseek-coder-v2:lite"
      - "qwen2.5-coder"
      - "mistral"
```

**Pros:**
- Complete privacy - code never leaves your machine
- No API key required
- No per-request costs
- Works offline
- Supports many open-source models

**Requirements:**
- Ollama installed: https://ollama.com/download
- At least one model pulled (e.g., `ollama pull codellama`)
- Ollama server running (`ollama serve`)

**Configuration Options:**

| Setting | Description | Default |
|---------|-------------|---------|
| `host` | Ollama server address | `localhost:11434` |
| `model` | Model to use | `codellama` |
| `timeout` | Request timeout in seconds | `300` |
| `num_ctx` | Context window size override | Model default |
| `system_prompt` | Custom system prompt | Built-in default |
| `available_models` | Models shown in `--switch-model` | Built-in list |

### Recommended Models for Code Review

| Model | Size | RAM Required | Notes |
|-------|------|--------------|-------|
| `codellama` | 7B | ~8GB | Default, optimized for code |
| `codellama:13b` | 13B | ~16GB | Better understanding |
| `llama3.2` | 3B | ~4GB | Fast, good for quick reviews |
| `deepseek-coder-v2:lite` | 16B | ~12GB | Advanced code analysis |
| `qwen2.5-coder` | 7B | ~8GB | Good code generation |

### GPU Acceleration

- **macOS (Apple Silicon)**: Automatic via Metal. M1/M2/M3 Macs work great.
- **Linux/Windows (NVIDIA)**: Requires NVIDIA GPU with CUDA. 8GB+ VRAM for 7B models, 16GB+ for 13B.
- **CPU-only**: Works but significantly slower. Use smaller models (llama3.2) for reasonable speed.

### Remote Ollama

You can connect to Ollama running on another machine:

```yaml
engines:
  ollama:
    host: "192.168.1.100:11434"  # Remote server IP
    model: "codellama"
```

Note: Ensure the remote Ollama server is accessible and consider security implications of sending code over the network.

### Output Quality Expectations

Local models have fundamental limitations compared to cloud APIs like Claude or GPT-4:

| Aspect | Cloud APIs (Claude, GPT-4) | Local Models (Ollama) |
|--------|---------------------------|----------------------|
| Output format compliance | Excellent - follows templates precisely | Variable - may ignore structure |
| Code understanding | Excellent | Good (especially codellama) |
| Issue detection | Comprehensive | Basic to moderate |
| Recommendation quality | Detailed, actionable | Often generic |
| Model size | 100B+ parameters | 3B-16B parameters |

**Why this happens:** Smaller models (7B-13B parameters) are optimized for code understanding but not for following complex output format instructions.

**Best use cases for Ollama:**
- Privacy-sensitive code reviews
- Quick, informal reviews where format doesn't matter
- Offline environments
- Cost savings (no API fees)
- Learning/experimentation

**When to use cloud APIs instead:**
- Production code reviews requiring consistent, structured output
- Complex PRs needing thorough analysis
- When review format compliance matters
- Team environments with standardized review formats

---

## Customizing Available Models

Each engine has an `available_models` list that controls which models appear in `wtp --switch-model`. You can customize this list in your `config.yaml`:

```yaml
engines:
  claude-api:
    api_key: "sk-ant-..."
    model: "claude-sonnet-4-20250514"
    available_models:
      - "claude-sonnet-4-20250514"
      - "claude-opus-4-20250514"
      - "my-custom-model"  # Add any model you have access to
```

If `available_models` is not specified, built-in defaults are used. You can also enter any custom model name directly in `--switch-model` by selecting the "Enter custom model" option.

**Note:** If you configure an invalid model, you'll get a helpful error message when running a review. Use `wtp --test-config` to verify your model configuration.
