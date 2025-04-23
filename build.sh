#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip and install essential build tools
pip install --upgrade pip
pip install wheel setuptools

# Install Python dependencies
pip install -r requirements.txt