# WhatThePatch Test Suite

This directory contains the automated test suite for WhatThePatch.

## Setup

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

### Basic Usage

Run all tests:
```bash
pytest tests/
```

Run with verbose output:
```bash
pytest tests/ -v
```

Run a specific test file:
```bash
pytest tests/test_models.py -v
pytest tests/test_engines.py -v
pytest tests/test_cli.py -v
```

Run a specific test class:
```bash
pytest tests/test_models.py::TestGetEngineModel -v
```

Run a specific test:
```bash
pytest tests/test_models.py::TestGetEngineModel::test_returns_configured_model -v
```

### Test Reports and Dashboards

#### HTML Report (Visual Dashboard)

Generate an HTML report with detailed results:
```bash
pytest tests/ --html=tests/report.html --self-contained-html
```

Open `tests/report.html` in your browser to view the interactive dashboard.

#### Coverage Report

Run tests with coverage analysis:
```bash
pytest tests/ --cov=. --cov-report=html
```

This generates a `htmlcov/` directory. Open `htmlcov/index.html` in your browser to see which lines of code are covered by tests.

#### Combined HTML Report with Coverage

```bash
pytest tests/ --html=tests/report.html --self-contained-html --cov=. --cov-report=html
```

#### Terminal Coverage Summary

Quick coverage summary in the terminal:
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

### Reading Test Results

#### Understanding Coverage Reports

The coverage report shows how much of your code is exercised by tests:

| Column | Meaning |
|--------|---------|
| **File** | The Python file being analyzed |
| **statements** | Total number of executable lines of code |
| **missing** | Lines not executed during tests |
| **excluded** | Lines excluded from coverage (e.g., `# pragma: no cover`) |
| **coverage** | Percentage of statements executed (higher is better) |

**Coverage Percentages:**
- **100%** - Every line was executed during tests
- **75-99%** - Good coverage, most code paths tested
- **50-74%** - Moderate coverage, key paths likely tested
- **< 50%** - Low coverage, many untested code paths

**Clicking into Files:**
In the HTML report (`htmlcov/index.html`), click any filename to see line-by-line coverage:
- **Green lines** - Executed during tests
- **Red lines** - Not executed (missing coverage)
- **White lines** - Not executable (comments, blank lines, etc.)

**Why Some Files Have Low Coverage:**
- `setup.py` (0%) - Setup wizard requires user interaction
- `whatthepatch.py` (14%) - Main script has many CLI functions requiring integration tests
- Engine files (~19%) - API calls need mocking or real credentials
- Test files (100%) - Tests themselves are fully executed

#### Understanding Test Results

**Terminal Output:**
```
tests/test_cli.py .........................    [ 34%]
tests/test_engines.py ........................ [ 69%]
tests/test_models.py ......................   [100%]

71 passed in 0.27s
```

| Symbol | Meaning |
|--------|---------|
| `.` | Test passed |
| `F` | Test failed (assertion error) |
| `E` | Test error (exception during setup/execution) |
| `s` | Test skipped |
| `x` | Test expected to fail (xfail) |

**HTML Report (`tests/report.html`):**
- **Summary** - Total passed/failed/skipped at the top
- **Test List** - Each test with pass/fail status
- **Click to Expand** - Shows test details, duration, and any error messages
- **Filter** - Use checkboxes to show only passed/failed tests

### Quick Test Commands

| Command | Description |
|---------|-------------|
| `pytest tests/` | Run all tests |
| `pytest tests/ -v` | Verbose output |
| `pytest tests/ -q` | Quiet output (minimal) |
| `pytest tests/ -x` | Stop on first failure |
| `pytest tests/ --tb=short` | Shorter tracebacks |
| `pytest tests/ --tb=no` | No tracebacks |
| `pytest tests/ -k "model"` | Run tests matching "model" |
| `pytest tests/ --lf` | Run only last failed tests |

## Test Structure

```
tests/
├── README.md           # This file
├── conftest.py         # Shared pytest fixtures
├── test_models.py      # Tests for model management functions
├── test_engines.py     # Tests for engine detection and configuration
├── test_cli.py              # Tests for CLI parsing and utilities
└── manual_test_context.py   # Manual test script for --context (not pytest)
```

### Test Files

#### `conftest.py`
Shared fixtures used across all test files:
- `mock_config_full` - Complete config with all engines configured
- `mock_config_minimal` - Config with placeholder API keys
- `mock_config_empty` - Empty config for edge case testing
- `mock_pr_data` - Sample PR data for testing
- `sample_branch_names` - Test cases for ticket ID extraction

#### `test_models.py`
Tests for model management functions:
- `ENGINE_DEFAULT_MODELS` constant validation
- `get_engine_model()` - retrieving configured/default models
- `get_available_models()` - getting model lists from config
- Config model override behavior

#### `test_engines.py`
Tests for engine detection and configuration:
- `get_engine_config_status()` - checking engine availability
- API key placeholder detection
- CLI tool availability detection (with mocking)
- Engine registry and factory functions
- BaseEngine class requirements

#### `test_cli.py`
Tests for CLI utilities:
- `parse_pr_url()` - GitHub/Bitbucket URL parsing
- `extract_ticket_id()` - ticket extraction from branch names
- `parse_version()` - version string parsing
- `sanitize_filename()` - filename sanitization
- Version constant validation

#### `manual_test_context.py`
**Note:** This is a standalone manual test script, not a pytest test.
Run it directly to test the `--context` functionality:
```bash
python tests/manual_test_context.py ./engines ./prompt.md
```

## Writing New Tests

### Adding a New Test File

1. Create a new file in `tests/` with the `test_` prefix
2. Import pytest and the functions you want to test
3. Use fixtures from `conftest.py` as needed

Example:
```python
"""Tests for new_feature module."""
import pytest
from whatthepatch import new_function

class TestNewFunction:
    """Tests for new_function()."""

    def test_basic_functionality(self, mock_config_full):
        """Should do something expected."""
        result = new_function(mock_config_full)
        assert result == expected_value

    def test_edge_case(self, mock_config_empty):
        """Should handle empty config gracefully."""
        result = new_function(mock_config_empty)
        assert result is None
```

### Adding New Fixtures

Add shared fixtures to `conftest.py`:
```python
@pytest.fixture
def my_new_fixture():
    """Description of what this fixture provides."""
    return {"key": "value"}
```

## Continuous Integration

To run tests in CI/CD pipelines:

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests with JUnit XML output for CI
pytest tests/ --junitxml=test-results.xml

# Run with coverage for CI
pytest tests/ --cov=. --cov-report=xml
```

## Troubleshooting

### Import Errors

If you get import errors, make sure you're running from the project root:
```bash
cd /path/to/WhatThePatch
pytest tests/
```

### Fixture Not Found

If a fixture is not found, ensure `conftest.py` is in the `tests/` directory and contains the fixture definition.

### Mocking Issues

For tests that mock system functions (like `shutil.which`), ensure the mock path matches where the function is called, not where it's defined:
```python
# Correct - mock where it's used
with patch("whatthepatch.shutil.which") as mock:
    ...

# Or if imported directly
with patch("shutil.which") as mock:
    ...
```
