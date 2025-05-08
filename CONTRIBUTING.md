# Contributing to Allkinds Chat Bot

Thank you for considering contributing to the Allkinds Chat Bot! This document provides guidelines and instructions for contributing to this project.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/allkinds-chat-bot.git
cd allkinds-chat-bot
```

2. Install Poetry (dependency management):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. Install dependencies:
```bash
poetry install
```

4. Set up environment variables:
Copy `.env.example` to `.env` and fill in the required values:
```bash
cp .env.example .env
```

5. Initialize the database:
```bash
poetry run python -m src.db.init_chat_db
```

6. Run the bot locally:
```bash
poetry run python -m src.main
```

## Code Style

We follow PEP 8 with a few modifications:
- 88 character line length limit (using Black)
- Use descriptive variable names with auxiliary verbs (e.g., is_active, has_permission)

Run these commands before submitting a pull request:
```bash
# Format code
poetry run black .

# Check imports
poetry run isort .

# Lint code
poetry run flake8
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass with `poetry run pytest`
6. Update documentation if necessary
7. Submit a pull request

## Commit Messages

Use conventional commits format:
```
feat: add user blocking functionality
fix: resolve issue with message forwarding
docs: update README with new environment variables
test: add tests for chat session repository
```

## Adding New Features

1. First discuss the change you wish to make via issue, email, or any other method with the owners of this repository.
2. Update the README.md with details of changes to the interface.
3. Update the version number in pyproject.toml according to SemVer.

## Testing

Write tests for all new functionality. We use pytest for testing.

Run the test suite:
```bash
poetry run pytest
```

## License

By contributing, you agree that your contributions will be licensed under the project's license. 