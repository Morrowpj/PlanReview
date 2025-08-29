# Makefile for PlanReview API testing

.PHONY: help install test test-fast test-auth test-conversations test-chat test-reviewrooms test-integration test-verbose clean coverage serve-coverage

# Default target
help:
	@echo "PlanReview API Test Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests with coverage"
	@echo "  make test-fast        Run all tests without coverage"
	@echo "  make test-verbose     Run all tests with verbose output"
	@echo ""
	@echo "Specific Test Suites:"
	@echo "  make test-auth        Run authentication tests only"
	@echo "  make test-conversations   Run conversation tests only" 
	@echo "  make test-chat        Run chat tests only"
	@echo "  make test-reviewrooms Run review room tests only"
	@echo "  make test-integration Run integration tests only"
	@echo ""
	@echo "Coverage:"
	@echo "  make coverage         Generate coverage report"
	@echo "  make serve-coverage   Serve HTML coverage report (http://localhost:8080)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove test artifacts and cache"

# Install dependencies
install:
	pip install -r requirements.txt

# Run all tests with coverage
test:
	python run_tests.py --install-deps

# Run all tests without coverage (faster)
test-fast:
	python run_tests.py --no-coverage --no-html

# Run tests with verbose output
test-verbose:
	python run_tests.py --verbose

# Run specific test suites
test-auth:
	python run_tests.py --suite auth --no-coverage

test-conversations:
	python run_tests.py --suite conversations --no-coverage

test-chat:
	python run_tests.py --suite chat --no-coverage

test-reviewrooms:
	python run_tests.py --suite reviewrooms --no-coverage

test-integration:
	python run_tests.py --suite integration --no-coverage

# Generate coverage report only
coverage:
	pytest tests/ --cov=api --cov-report=html:test_results/coverage_html --cov-report=term

# Serve HTML coverage report
serve-coverage:
	@if [ -d "test_results/coverage_html" ]; then \
		echo "🌐 Serving coverage report at http://localhost:8080"; \
		echo "📁 Coverage report directory: test_results/coverage_html"; \
		cd test_results/coverage_html && python -m http.server 8080; \
	else \
		echo "❌ No coverage report found. Run 'make test' or 'make coverage' first."; \
	fi

# Clean up test artifacts
clean:
	rm -rf test_results/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -f test.db
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run tests in development mode with file watching (requires pytest-watch)
test-watch:
	@if command -v ptw >/dev/null 2>&1; then \
		ptw --runner "python run_tests.py --no-coverage"; \
	else \
		echo "❌ pytest-watch not installed. Install with: pip install pytest-watch"; \
	fi

# Quick syntax check
check-syntax:
	python -m py_compile api/main.py
	python -m py_compile run_tests.py
	@echo "✅ Syntax check passed"

# Run linting (if available)
lint:
	@if command -v flake8 >/dev/null 2>&1; then \
		flake8 api/ tests/ --max-line-length=100; \
	else \
		echo "⚠️  flake8 not installed. Install with: pip install flake8"; \
	fi

# Full quality check
quality: check-syntax lint test
	@echo "🎉 All quality checks passed!"