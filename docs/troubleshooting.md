# Troubleshooting

Common issues and how to resolve them.

## CLI Issues

### "wtp: command not found"

The CLI command is not in your PATH. Either:

1. Run `python setup.py` and select "Install CLI command only"
2. Add `~/.local/bin` to your PATH:
   ```bash
   export PATH="$PATH:$HOME/.local/bin"
   ```
   Add this line to your `~/.zshrc` or `~/.bashrc` to make it permanent.

## Package Issues

### "anthropic package not installed"

```bash
pip install anthropic
```

### "openai package not installed"

```bash
pip install openai
```

### "google-generativeai package not installed"

```bash
pip install google-generativeai
```

## CLI Engine Issues

### "claude command not found"

Either:
1. Install Claude Code: https://claude.ai/code
2. Or set the full path in config under `engines.claude-cli.path: "/path/to/claude"`

### "codex command not found"

Either:
1. Install Codex CLI: `npm install -g @openai/codex`
2. Or set the full path in config under `engines.openai-codex-cli.path: "/path/to/codex"`

### "gemini command not found"

Either:
1. Install Gemini CLI from: https://github.com/google-gemini/gemini-cli
2. Or set the full path in config under `engines.gemini-cli.path: "/path/to/gemini"`
3. After installation, run `gemini auth` to authenticate or set `GEMINI_API_KEY`

## Ollama Issues

### "Cannot connect to Ollama"

Ollama server is not running. Start it with:

```bash
ollama serve
```

### "Model not found"

The specified model is not installed. Pull it with:

```bash
ollama pull codellama
```

Run `ollama list` to see installed models.

### "Input too large for model"

The PR diff exceeds the model's context length. Options:

1. Use a model with larger context (e.g., `llama3.2` has 128K context)
2. Review a smaller PR
3. Reduce external context

### Request timeout

Local inference can be slow, especially on CPU. Options:

1. Increase timeout in config: `engines.ollama.timeout: 600`
2. Use a smaller/faster model (e.g., `llama3.2`)
3. Enable GPU acceleration for faster inference

## API Issues

### API rate limits

If you hit rate limits with the API engine, consider:

- Using a model with higher limits
- Switching to CLI engine which uses your team's quota

### Invalid API key

Run `wtp --test-config` to verify your API keys are correct and have the right permissions.

## General Debugging

### Test your configuration

Run `wtp --test-config` to verify all tokens and credentials are working.

### Test without making API calls

Use `--dry-run` to see what would be sent without actually calling the AI:

```bash
wtp --review <URL> --dry-run
```

### See detailed output

Use `--verbose` or `-v` to see detailed output including prompt preview:

```bash
wtp --review <URL> --verbose
```

### Combine both

```bash
wtp --review <URL> --dry-run --verbose
```

## Uninstall

To remove the CLI command:

```bash
python setup.py --uninstall
```
