#!/usr/bin/env sh

set -e -x

if [ "${1}" != "major" -a "${1}" != "minor" -a "${1}" != "patch" ]; then
	echo "Usage: ${0} (major|minor|patch)"
	exit 1
fi

part="${1}"
poetry version major
ruff check --fix .
ruff format .
dmypy run -- --strict --package charmonium.time_block
python -m pytest
poetry build
twine check dist/*
if [ -z "${dry_run}" ]; then
	poetry publish
fi
