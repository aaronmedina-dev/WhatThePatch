#!/usr/bin/env python3
"""Quick test script for --context functionality."""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from whatthepatch import (
    read_context_paths,
    check_context_size,
    EXCLUDED_DIRS,
    BINARY_EXTENSIONS,
    CONTEXT_SIZE_WARNING_THRESHOLD,
)


def test_context(paths: list[str]):
    """Test context reading with given paths."""
    print("=" * 60)
    print("Testing --context functionality")
    print("=" * 60)

    print(f"\nConfiguration:")
    print(f"  Size warning threshold: {CONTEXT_SIZE_WARNING_THRESHOLD / 1024:.0f}KB")
    print(f"  Excluded dirs: {', '.join(sorted(EXCLUDED_DIRS))}")
    print(f"  Binary extensions: {len(BINARY_EXTENSIONS)} types")

    print(f"\nInput paths:")
    for p in paths:
        path = Path(p).expanduser().resolve()
        exists = "exists" if path.exists() else "NOT FOUND"
        path_type = "dir" if path.is_dir() else "file" if path.is_file() else "unknown"
        print(f"  - {p} ({path_type}, {exists})")

    print(f"\nReading context...")
    content, size_bytes = read_context_paths(paths)

    print(f"\nResults:")
    print(f"  Total size: {size_bytes} bytes ({size_bytes / 1024:.2f}KB)")
    print(f"  Content length: {len(content)} characters")

    # Count files found
    file_count = content.count("### File:")
    print(f"  Files found: {file_count}")

    print(f"\n--- Content Preview (first 2000 chars) ---\n")
    print(content[:2000])
    if len(content) > 2000:
        print(f"\n... ({len(content) - 2000} more characters)")

    print(f"\n--- End Preview ---")

    # Test size check (without prompting)
    if size_bytes > CONTEXT_SIZE_WARNING_THRESHOLD:
        print(f"\nWARNING: Context exceeds threshold ({size_bytes / 1024:.1f}KB > {CONTEXT_SIZE_WARNING_THRESHOLD / 1024:.0f}KB)")
        print("User would be prompted to confirm.")
    else:
        print(f"\nContext size OK (under {CONTEXT_SIZE_WARNING_THRESHOLD / 1024:.0f}KB threshold)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_context.py <path1> [path2] ...")
        print("\nExamples:")
        print("  python test_context.py ./engines")
        print("  python test_context.py ./prompt.md ./banner.py")
        print("  python test_context.py /path/to/external/repo")
        sys.exit(1)

    test_context(sys.argv[1:])
