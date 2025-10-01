#!/usr/bin/env bash
set -euo pipefail

# Script to compile and test Java projects
# Usage: ./compile_and_test.sh [maven|gradle] [test_name]

BUILD_SYSTEM=${1:-maven}
TEST_NAME=${2:-}

echo "Building with $BUILD_SYSTEM..."

if [[ "$BUILD_SYSTEM" == "maven" ]]; then
    # Maven build and test
    echo "Running Maven compile..."
    mvn compile -q -DskipTests=true
    
    if [[ -n "$TEST_NAME" ]]; then
        echo "Running specific test: $TEST_NAME"
        mvn test -q -Dtest="$TEST_NAME"
    else
        echo "Running all tests..."
        mvn test -q
    fi
    
elif [[ "$BUILD_SYSTEM" == "gradle" ]]; then
    # Gradle build and test
    echo "Running Gradle compile..."
    ./gradlew compileJava -q
    
    if [[ -n "$TEST_NAME" ]]; then
        echo "Running specific test: $TEST_NAME"
        ./gradlew test -q --tests "$TEST_NAME"
    else
        echo "Running all tests..."
        ./gradlew test -q
    fi
    
else
    echo "Error: Unsupported build system: $BUILD_SYSTEM"
    echo "Supported systems: maven, gradle"
    exit 1
fi

echo "Build and test completed successfully."
