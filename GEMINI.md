# envars

## Purpose
`envars` is the legacy v1 of Time Out's config/secret management tool. It resolves environment variables from a YAML file, with AWS KMS-encrypted secrets. For any NEW work, prefer [`envars2`](https://github.com/timeoutdigital/envars2) (which supports GCP). Only use this repo for bug fixes on older deployments or v1 to v2 migrations.

## Local Development
- Prerequisite: `timeout-tools` (Time Out's internal setup utility — see the [timeout-tools README](https://github.com/timeoutdigital/timeout-tools) for installation).
- Setup: `timeout-tools python-setup`
- Test: `invoke test`
- Run locally: `python -m envars.envars`
- Task list: `invoke --list`

## Architecture Notes
- Written in Python, CLI entry point is `envars/envars.py`.
- No GCP support (AWS only).
- Packaging via `setup.py` and `requirements.in` (pip-tools).
