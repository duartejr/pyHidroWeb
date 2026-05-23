# Contributing to pyHidroWeb

Thank you for your interest in contributing to pyHidroWeb! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Welcome feedback and different perspectives
- Focus on what's best for the community
- Show empathy to others

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
git clone https://github.com/your-username/pyhidroweb.git
cd pyhidroweb
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

## Development Workflow

### Code Style

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) and use the following tools:

**Black** for code formatting:

```bash
black src/ tests/
```

**isort** for import sorting:

```bash
isort src/ tests/
```

**flake8** for style checks:

```bash
flake8 src/ tests/
```

**mypy** for type checking:

```bash
mypy src/
```

### Writing Tests

- Write tests for all new functionality
- Aim for >80% code coverage
- Use pytest for testing
- Place tests in `tests/unit/` for unit tests

Example test:

```python
def test_new_feature():
    """Test description of new feature."""
    result = new_function()
    assert result is not None
    assert len(result) == expected_length
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/pyhydroweb --cov-report=html

# Run specific test file
pytest tests/unit/test_core.py

# Run with verbose output
pytest -v
```

### Docstrings

Use Google-style docstrings:

```python
def download_data(station: int, data_type: int = 3) -> pd.DataFrame:
    """
    Download hydrological data for a station.

    Args:
        station: Station code
        data_type: Type of data (2=rainfall, 3=flow)

    Returns:
        DataFrame containing downloaded data

    Raises:
        InvalidDataTypeError: If data_type is invalid
        DownloadError: If download fails

    Example:
        >>> data = download_data(34879500, data_type=3)
    """
    pass
```

### Type Hints

Always include type hints:

```python
from typing import Optional, List, Union
import pandas as pd

def process_data(
    data: pd.DataFrame,
    threshold: float = 0.5,
    dates: Optional[List[str]] = None
) -> Union[pd.DataFrame, None]:
    """Process data with type hints."""
    pass
```

## Commit Guidelines

- Write clear, descriptive commit messages
- Reference issue numbers when applicable (e.g., "Fix #123")
- Use imperative mood ("Add feature" not "Added feature")
- Keep commits focused and atomic

Example:

```
Add validation for station codes

- Add InvalidStationCodeError exception
- Add validate_station_code() function
- Add tests for station code validation

Fixes #45
```

## Pull Request Process

1. **Update Your Branch**

```bash
git fetch origin
git rebase origin/main
```

2. **Run All Checks**

```bash
# Format code
black src/ tests/
isort src/ tests/

# Run linting
flake8 src/ tests/

# Run type checking
mypy src/

# Run tests
pytest --cov=src/pyhydroweb
```

3. **Push Your Changes**

```bash
git push origin feature/your-feature-name
```

4. **Create Pull Request**

   - Provide a clear title and description
   - Reference related issues
   - Explain why the change is needed
   - Describe any breaking changes

## Documentation

### README Updates

Update README.md if you:

- Add new functions or modules
- Change API behavior
- Add new features or examples

### Docstring Requirements

All public functions must have:

- Clear description of what the function does
- Args section listing all parameters with types
- Returns section describing return value and type
- Raises section listing possible exceptions
- Example section with usage example

## Reporting Issues

When reporting bugs, include:

- Python version
- Operating system
- pyHidroWeb version
- Error message and traceback
- Steps to reproduce the issue
- Expected vs. actual behavior

## Feature Requests

When requesting features:

- Clearly describe the desired functionality
- Explain the use case
- Provide examples of how it would be used
- Reference any related issues

## Review Process

- At least one maintainer review
- All tests must pass
- Code coverage should not decrease
- Documentation must be updated
- Commit history should be clean

## Questions?

Feel free to:

- Open an issue for discussion
- Check existing issues and documentation
- Ask in pull request comments

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.

Thank you for contributing to pyHidroWeb!
