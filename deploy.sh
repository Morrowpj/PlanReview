#!/bin/bash

# Exit on any failure
set -e

echo "Installing system dependencies..."
apt-get update
apt-get install -y libpoppler-cpp-dev pkg-config poppler-utils

echo "Running Oryx build..."
oryx build . -o /home/site/wwwroot --platform python --platform-version 3.11