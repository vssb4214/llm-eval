# LLM Evaluator

A comprehensive benchmark system for evaluating Large Language Models on Java maintenance tasks including fault localization, patch generation, and build/test execution.

## Features

- End-to-end evaluation workflow from log analysis to patch application
- Support for multiple model providers (OpenAI, Anthropic, local models)
- Comprehensive scoring system across fix success, localization, and reliability
- Real test cases using actual Java projects with failure logs
- Build system support for Maven and Gradle projects
- Rich reporting with charts and detailed analysis

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/vssb4214/llm-evaluator.git
cd llm-evaluator

# Install dependencies
poetry install

# Copy environment template
cp env.example .env
# Edit .env with your API keys if needed
```

### Configuration

1. Set up API keys in `.env` (optional for local models):
```bash
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

2. Configure models in `models.yaml`:
```yaml
models:
  - name: local-model
    family: openai
    endpoint: http://localhost:8000/v1
    api_key_env: ""
    model: your-model-name
    temperature: 0.2
    max_tokens: 4096
```

### Running the Benchmark

```bash
# Run benchmark with default settings
poetry run jmb run

# Run with custom parameters
poetry run jmb run \
  --cases bench/cases \
  --models models.yaml \
  --out results/run-timestamp \
  --seeds 0 1 2 \
  --temp 0.2

# Generate report
poetry run jmb report --input results/run-20240115-143022
```

## CLI Commands

### `jmb run`
Run the benchmark with specified parameters.

**Options:**
- `--cases, -c`: Directory containing test cases (default: `bench/cases`)
- `--models, -m`: Path to models configuration (default: `models.yaml`)
- `--out, -o`: Output directory for results
- `--seeds, -s`: Random seeds to use (default: `[0, 1, 2]`)
- `--temp, -t`: Temperature for model generation (default: `0.2`)
- `--retry, -r`: Maximum retries per run (default: `1`)
- `--timeout`: Timeout per run in seconds (default: `600`)

### `jmb report`
Generate a benchmark report from results.

**Options:**
- `--out, -o`: Output path for report
- `--html`: Generate HTML report in addition to Markdown

### `jmb validate`
Validate test case structure and configuration.

### `jmb list-models`
List available model configurations with validation status.

## Test Case Structure

Each test case is a directory containing:

```
sample-1/
├── repo_url.txt          # Git repository URL
├── bug_sha.txt           # Commit SHA with the bug
├── build_system.txt      # "maven" or "gradle"
├── logs.txt              # Build/test failure logs
├── failing_test.txt      # Optional: specific failing test
├── truth_file.txt        # Optional: ground truth file path
└── truth_line.txt        # Optional: ground truth line number
```

## Model Configuration

Models are configured in `models.yaml`:

```yaml
models:
  - name: model-name
    family: openai|anthropic|local
    endpoint: API endpoint URL
    api_key_env: Environment variable name for API key
    model: Model identifier for API
    temperature: 0.2
    max_tokens: 4096
    cost_per_1k_input: 0.01
    cost_per_1k_output: 0.03
```

### Supported Model Families

- **OpenAI**: GPT-4, GPT-3.5-turbo, and OpenAI-compatible APIs
- **Anthropic**: Claude models
- **Local**: vLLM, LM Studio, and other local endpoints

## Scoring System

The benchmark uses a 100-point scoring system:

### Fix Success (55 points)
- **Build Pass (20 points)**: Project compiles without errors
- **Test Pass (25 points)**: All tests pass, including previously failing tests
- **Minimality (10 points)**: Patch is minimal and focused

### Localization (20 points)
- **Top-1 Correct (12 points)**: First localization matches ground truth
- **Top-3 Hit (8 points)**: Any of top-3 localizations match ground truth

### Operations (15 points)
- **Latency Efficiency (10 points)**: Fast execution
- **Token Efficiency (5 points)**: Efficient token usage

### Reliability (10 points)
- **JSON Validity (5 points)**: Model output is valid JSON
- **Patch Validity (5 points)**: Patch applies successfully

## Project Structure

```
llm-evaluator/
├── src/jmb/                 # Main source code
│   ├── cli.py              # CLI interface
│   ├── config.py           # Configuration management
│   ├── types.py            # Data models
│   ├── prompts.py          # Prompting system
│   ├── model_client/       # Model client implementations
│   ├── vcs.py              # Git operations
│   ├── repo_summary.py     # Repository analysis
│   ├── retrieval.py        # Code retrieval
│   ├── patcher.py          # Patch application
│   ├── builder.py          # Build/test execution
│   ├── scorer.py           # Scoring system
│   ├── runner.py           # Benchmark runner
│   ├── report.py           # Report generation
│   └── utils.py            # Utility functions
├── bench/cases/            # Test cases
├── scripts/                # Shell scripts
├── templates/              # Report templates
├── pyproject.toml          # Poetry configuration
├── models.yaml             # Model configurations
└── env.example             # Environment template
```

## Development

### Adding New Model Clients

1. Create a new client class in `src/jmb/model_client/`
2. Inherit from `ModelClient` base class
3. Implement the `generate()` method
4. Add the client to the factory in `model_client/factory.py`
5. Update the `ModelFamily` enum in `types.py`

### Adding New Metrics

1. Add new fields to `ScoringMetrics` in `types.py`
2. Implement scoring logic in `scorer.py`
3. Update the report template in `templates/report.md.j2`
4. Add visualization in `report.py`

## Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure your API keys are correctly set in `.env`
2. **Model Configuration Errors**: Check `models.yaml` syntax and endpoint URLs
3. **Build Failures**: Ensure Maven/Gradle are installed and accessible
4. **Git Errors**: Ensure Git is installed and repositories are accessible
5. **Timeout Errors**: Increase `--timeout` for slow models or large repositories

### Validation

Validate your setup:
```bash
# Check test cases
poetry run jmb validate

# Check model configurations
poetry run jmb list-models
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.