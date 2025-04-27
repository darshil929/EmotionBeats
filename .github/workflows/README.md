# EmotionBeats CI/CD Workflows

This directory contains GitHub Actions workflows for the EmotionBeats project.

## Workflows

### `ci.yml` - Continuous Integration

Ensures code quality and runs tests on every pull request and push to main branch.

**Steps:**
1. Code quality checks:
   - Code formatting (Black)
   - Import sorting (isort)
   - Linting (flake8)
   - Type checking (mypy)
   - Security scanning (bandit)
2. Run tests with pytest
3. Generate and upload test coverage report
4. Build Docker image (without push)

**Trigger:**
- Push to `main` branch (affecting backend code)
- Pull request to `main` branch (affecting backend code)

### `generate-docs.yml` - API Documentation

Generates API documentation using FastAPI's OpenAPI schema and deploys to GitHub Pages.

**Steps:**
1. Generate OpenAPI JSON schema
2. Set up MkDocs with Material theme
3. Build documentation site
4. Deploy to GitHub Pages

**Trigger:**
- Push to `main` branch (affecting backend code or requirements)

### `cd.yml` - Continuous Deployment (Placeholder)

This is a placeholder for future deployment workflows. Currently disabled.

**Future capabilities:**
- Build and tag Docker images
- Push to container registry
- Deploy to development/staging/production environments

**Trigger:**
- Currently manual via workflow_dispatch
- Will be configured for automated deployment when infrastructure is decided

## Secrets Required

- `SPOTIFY_CLIENT_ID` - Spotify API client ID
- `SPOTIFY_CLIENT_SECRET` - Spotify API client secret

## Adding New Workflows

When adding new workflows, please follow these conventions:
1. Use descriptive names
2. Add appropriate triggers and conditions
3. Document the workflow in this README

## Troubleshooting

If a workflow fails:
1. Check the specific job that failed
2. Review the logs for error messages
3. Fix the issue and push again to trigger the workflow
