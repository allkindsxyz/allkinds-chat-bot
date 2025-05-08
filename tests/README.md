# Automated Tests for AllkindsTeamBot

This directory contains automated tests for the AllkindsTeamBot. These tests help ensure that the bot behaves correctly and that critical functionality doesn't break when making changes.

## Test Structure

- `unit/`: Unit tests for individual components
- `integration/`: Integration tests for combined functionality
- `fixtures/`: Shared test fixtures and mock objects

## Running Tests

To run all tests:

```bash
pytest
```

To run a specific test file:

```bash
pytest tests/unit/test_handlers_integrity.py
```

To run tests with a specific marker:

```bash
pytest -m bot_start
pytest -m question_creation
pytest -m question_answering
pytest -m question_deletion
pytest -m ui_elements
```

## Important Test Categories

1. **Handler Integrity Tests**: Ensure that all handler modules have the required `register_handlers` function
2. **Bot Startup Tests**: Verify the bot can connect to Telegram and start correctly
3. **Question Creation Tests**: Test the flow of creating questions
4. **Question Answering Tests**: Test answering questions and changing answers
5. **Question Deletion Tests**: Test deleting questions (including authorization checks)
6. **UI Elements Tests**: Test the UI elements like buttons and notifications

## Adding New Tests

When adding new tests:

1. Add appropriate markers to categorize your tests
2. Use the existing fixtures when possible
3. Isolate your tests from the real Telegram API and database
4. Mock external dependencies to avoid side effects

## Dependencies

The tests require the following packages:

- pytest
- pytest-asyncio
- pytest-mock
- pytest-cov (for coverage reports)

## Generating Coverage Reports

```bash
pytest --cov=src
```

## Test Guidelines

1. **Isolation**: Tests should not affect each other or depend on external services
2. **Completeness**: Test both happy paths and error conditions
3. **Readability**: Test names should clearly describe what they're testing
4. **Maintenance**: Keep tests up to date with code changes

## Critical Tests

The most critical test is `test_register_handlers_exists` in `unit/test_handlers_integrity.py`, which ensures that all handler modules contain the required `register_handlers` function. This prevents the bot from failing silently due to missing handler registrations. 