# External Context

**This is one of the biggest advantages of a local PR review tool.**

Cloud-based PR review services can only see code that's publicly accessible or connected to their platform. When your PR references:
- Private shared libraries
- Internal packages from other repositories
- Proprietary frameworks or utilities
- Code from repositories on different platforms

...these services make assumptions or miss important context entirely.

WhatThePatch solves this by letting you include **any local files, directories, or URLs** as additional context for the AI review.

## Local Files and Directories

```bash
# Include a private shared library
wtp --review <URL> --context /path/to/internal-shared-lib

# Include type definitions from another repo
wtp --review <URL> -c /path/to/private-types-repo/src/types

# Include multiple context sources
wtp --review <URL> -c /path/to/auth-service -c /path/to/shared-utils
```

## URL Context

You can also include remote files and documentation as context:

```bash
# GitHub file (blob URL auto-converted to raw)
wtp --review <URL> --context https://github.com/owner/repo/blob/main/src/types.ts

# Bitbucket file
wtp --review <URL> --context https://bitbucket.org/workspace/repo/src/main/config.json

# Developer documentation (HTML converted to Markdown)
wtp --review <URL> --context https://docs.python.org/3/library/asyncio.html

# Mix local files and URLs
wtp --review <URL> -c ./local/file.py -c https://github.com/org/shared/blob/main/types.d.ts
```

### Supported URL Types

| URL Type | Example | Handling |
|----------|---------|----------|
| GitHub blob | `https://github.com/owner/repo/blob/main/file.py` | Fetched via GitHub API |
| GitHub raw | `https://raw.githubusercontent.com/owner/repo/main/file.py` | Fetched via GitHub API |
| Bitbucket src | `https://bitbucket.org/workspace/repo/src/main/file.py` | Fetched via Bitbucket API |
| HTML page | `https://docs.python.org/3/library/asyncio.html` | Converted to Markdown |
| Raw text | `https://example.com/file.txt` | Fetched as-is |

### Private Repository Access

URL context supports **private repositories** using your configured tokens:

- **GitHub**: Uses your `tokens.github` from config.yaml
- **Bitbucket**: Uses your `tokens.bitbucket_username` and `tokens.bitbucket_app_password` from config.yaml

This means you can include files from any private repo you have access to - the same credentials used for fetching PR data are automatically used for URL context.

```bash
# Works with private GitHub repos (if token is configured)
wtp --review <URL> -c https://github.com/my-org/private-shared-lib/blob/main/types.ts

# Works with private Bitbucket repos (if credentials are configured)
wtp --review <URL> -c https://bitbucket.org/my-workspace/internal-utils/src/main/helpers.py
```

### URL Caching

- Fetched URLs are cached locally for 1 hour at `~/.whatthepatch/url_cache/`
- Subsequent requests within the TTL use the cached content for faster execution
- Cache is automatically refreshed when expired

### Limitations

- URL fetching retrieves **single pages only** - it does not crawl or traverse websites
- For documentation sites, you only get the specific page URL provided, not related pages
- To include multiple documentation pages, specify each URL separately with multiple `-c` flags

## How It Works

1. Local files are read recursively from specified paths
2. URLs are fetched via platform APIs (GitHub/Bitbucket) with authentication, or direct HTTP for other URLs
3. HTML pages are automatically converted to Markdown for better AI comprehension
4. Content is added to the AI prompt as "External Context"
5. The AI uses this context to understand references in your PR
6. Binary files and common non-code directories (node_modules, .git, etc.) are automatically excluded from local paths

## Size Management

If the combined context exceeds ~100KB, you'll be prompted to confirm before proceeding to avoid excessive API costs.

## Testing Context

Use `--dry-run` and `--verbose` flags to test your setup without making AI API calls:

```bash
# Test a review without calling AI
wtp --review <URL> --dry-run

# Test with external context
wtp --review <URL> --context /path/to/lib --dry-run

# See prompt preview (still makes AI call)
wtp --review <URL> --verbose

# Combine for full inspection without API call
wtp --review <URL> -c /path/to/lib -v --dry-run
```

A test script is also included for testing context reading independently:

```bash
# Test reading a directory
python test_context.py ./engines

# Test reading multiple paths
python test_context.py ./banner.py ./prompt.md /path/to/external/repo
```
