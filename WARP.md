# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Cognee MCP v2.0** - Enterprise-grade modular Model Context Protocol server for Cognee knowledge graph operations. Features four core modules: Time Awareness, Ontology Support, Async Memory, and Self-Improving Memory.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/veritaswiki/cognee-mcp-v2.git
cd cognee-mcp-v2

# Environment setup with uv
uv venv
source .venv/bin/activate  # macOS/Linux
uv pip install -e ".[dev]"

# Copy environment template and configure
cp .env.example .env
# Edit .env with your Cognee API credentials

# Run MCP server
uv run python main.py
```

## Architecture Overview

```
cognee_mcp_v2/
├── main.py                 # MCP server entry point
├── config/                 # Configuration management
│   └── settings.py        # Pydantic settings with environment variables
├── core/                   # Core MCP framework
│   ├── mcp_server.py      # JSON-RPC 2.0 MCP server implementation
│   ├── api_client.py      # Cognee API client with async/auth
│   ├── auth.py            # Authentication management
│   ├── tool_registry.py   # Dynamic tool loading and execution
│   └── error_handler.py   # Centralized error handling
├── tools/                  # MCP tool implementations
│   ├── base_tools.py      # Core: add_text, add_files, cognify, search
│   ├── dataset_tools.py   # Dataset management operations
│   ├── graph_tools.py     # Knowledge graph queries and analysis
│   ├── temporal_tools.py  # Time-aware memory operations
│   ├── ontology_tools.py  # OWL/RDF ontology processing
│   ├── memory_tools.py    # Async memory operations
│   └── self_improving_tools.py  # Feedback-driven improvements
├── schemas/               # Data models and validation
│   ├── mcp_models.py     # MCP protocol models
│   └── api_models.py     # Cognee API request/response models
└── tests/                # Test suite
```

## Runtime Requirements

- **Python**: 3.9+ (configured in pyproject.toml)
- **Package Manager**: uv (preferred) or pip
- **Dependencies**: See pyproject.toml for full list
  - `pydantic>=2.0.0` - Settings and validation
  - `aiohttp>=3.8.0` - Async HTTP client
  - `structlog>=23.0.0` - Structured logging
  - `rdflib>=7.0.0` - RDF/OWL processing
  - `textblob>=0.17.1` - NLP operations

## Development Commands

### Environment Setup
```bash
# Create virtual environment
uv venv

# Install dependencies (development)
uv pip install -e ".[dev]"

# Install specific dependency groups
uv pip install -e ".[monitoring]"  # Prometheus, OpenTelemetry
```

### Running the Server
```bash
# Standard MCP server (stdio transport)
uv run python main.py

# With debug logging
LOG_LEVEL=DEBUG uv run python main.py

# Custom configuration
COGNEE_API_URL=https://your-api.com uv run python main.py
```

### Code Quality
```bash
# Format code
uv run black .
uv run isort .

# Lint and type check
uv run flake8 .
uv run mypy .

# Run all pre-commit hooks
uv run pre-commit run --all-files
```

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=core --cov=modules --cov=tools --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_base_tools.py

# Run single test
uv run pytest tests/unit/test_base_tools.py::test_add_text_success
```

## Configuration

### Environment Variables

The server uses Pydantic settings with environment variable support:

**Core API Configuration:**
```bash
COGNEE_API_URL=https://mcp-cognee.veritas.wiki    # API endpoint
COGNEE_API_KEY=your_jwt_token                     # JWT token (preferred)
COGNEE_API_EMAIL=user@example.com                 # Alternative: email
COGNEE_API_PASSWORD=password                      # Alternative: password
COGNEE_TIMEOUT=180.0                              # Request timeout (seconds)
```

**Feature Toggles:**
```bash
FEATURE_TIME_AWARENESS=true                       # Enable time-aware operations
FEATURE_ONTOLOGY_SUPPORT=true                     # Enable OWL/RDF processing
FEATURE_ASYNC_MEMORY=true                         # Enable async memory ops
FEATURE_SELF_IMPROVING=true                       # Enable learning features
FEATURE_ADVANCED_ANALYTICS=true                   # Enable analytics
```

**Logging:**
```bash
LOG_LEVEL=INFO                                    # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=structured                             # structured, json, simple
LOG_FILE_PATH=/path/to/logs/server.log           # Optional log file
```

**MCP Server:**
```bash
MCP_SERVER_NAME=cognee-mcp-v2                     # Server identifier
MCP_SERVER_VERSION=2.0.0                         # Version string
MCP_PROTOCOL_VERSION=2024-11-05                   # MCP protocol version
MCP_MAX_CONCURRENT_REQUESTS=10                    # Concurrency limit
```

### Sample .env file
```bash
# Copy from .env.example and customize
cp .env.example .env
```

## MCP Integration

### Running as MCP Server

The server implements JSON-RPC 2.0 over stdio transport:

```bash
# Standard MCP stdio server
uv run python main.py

# Test with echo (MCP protocol uses stdin/stdout)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocol_version":"2024-11-05","capabilities":{},"client_info":{"name":"test","version":"1.0"}}}' | uv run python main.py
```

### Available MCP Methods

**Core Protocol:**
- `initialize` - Initialize MCP session
- `tools/list` - List available tools
- `tools/call` - Execute tool with arguments
- `resources/list` - List server resources
- `resources/read` - Read resource content
- `prompts/list` - List available prompts
- `prompts/get` - Get prompt template

**Available Tools:**
- `add_text` - Add text content to dataset
- `add_files` - Add files to dataset
- `cognify` - Process dataset into knowledge graph
- `search` - Search knowledge graph
- `get_datasets` - List all datasets
- `delete_dataset` - Remove dataset
- `query_graph` - Execute graph queries
- `get_temporal_data` - Time-aware data retrieval
- `process_ontology` - Process OWL/RDF files
- `async_remember` - Async memory operations
- `provide_feedback` - Learning feedback

### Client Integration

To integrate with MCP clients (like Claude Desktop):

```json
{
  "mcpServers": {
    "cognee-mcp-v2": {
      "command": "uv",
      "args": ["run", "python", "/path/to/cognee_mcp_v2/main.py"],
      "cwd": "/path/to/cognee_mcp_v2"
    }
  }
}
```

## Tool Development

### Adding New Tools

1. Create tool class in appropriate module (e.g., `tools/custom_tools.py`):

```python
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class

@register_tool_class
class MyCustomTool(BaseTool):
    def __init__(self):
        metadata = ToolMetadata(
            name="my_custom_tool",
            description="Description of what this tool does",
            category=ToolCategory.CUSTOM,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self):
        return ToolInputSchema(
            type="object",
            properties={
                "param1": {"type": "string", "description": "Parameter description"}
            },
            required=["param1"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments, context=None):
        # Tool implementation
        return {"success": True, "result": "Tool output"}
```

2. Import in `main.py` tool loading section to register automatically

### Tool Categories

- `ToolCategory.BASIC` - Core Cognee operations
- `ToolCategory.DATASET` - Dataset management
- `ToolCategory.GRAPH` - Knowledge graph operations
- `ToolCategory.TEMPORAL` - Time-aware features
- `ToolCategory.ONTOLOGY` - OWL/RDF processing
- `ToolCategory.MEMORY` - Memory operations
- `ToolCategory.FEEDBACK` - Learning and improvement
- `ToolCategory.DIAGNOSTIC` - System diagnostics

## Troubleshooting

### Common Issues

**Authentication Errors:**
```bash
# Check API credentials
LOG_LEVEL=DEBUG uv run python main.py
# Look for authentication-related log messages

# Test API connectivity
curl -H "Authorization: Bearer $COGNEE_API_KEY" "$COGNEE_API_URL/health"
```

**Module Import Errors:**
```bash
# Reinstall in editable mode
uv pip install -e ".[dev]"

# Check Python path
uv run python -c "import sys; print('\n'.join(sys.path))"
```

**Tool Loading Failures:**
```bash
# Check feature flags
grep FEATURE_ .env

# Test specific tool import
uv run python -c "from tools.base_tools import AddTextTool; print('Import successful')"
```

**MCP Protocol Issues:**
```bash
# Validate MCP response format
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | uv run python main.py | jq .

# Check server capabilities
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocol_version":"2024-11-05","capabilities":{},"client_info":{"name":"debug","version":"1.0"}}}' | uv run python main.py | jq .
```

### Debug Mode

```bash
# Enable comprehensive debug logging
export LOG_LEVEL=DEBUG
export LOG_FORMAT=structured
uv run python main.py 2>&1 | tee debug.log
```

### Health Check

The server provides built-in diagnostics:

```bash
# Check resource endpoints (after initialization)
# Server exposes config://settings, stats://server, stats://tools resources
```

## Safety Guidelines

### Dangerous Operations

⚠️ **Always confirm before executing these operations:**

- Dataset deletion (`delete_dataset`)
- Batch data modifications
- System configuration changes
- File system operations

### Confirmation Template

When prompted for dangerous operations:
```
⚠️ WARNING: Dangerous operation detected
Operation: [specific operation]
Impact: [affected data/files]
Risk: [potential consequences]
Confirm to proceed: [yes/no]
```

### Rate Limiting

The server includes built-in rate limiting:
- 60 requests per minute (default)
- 1000 requests per hour (default)
- Configurable via `RATE_LIMIT_*` environment variables

## Maintenance

### Dependency Updates

```bash
# Update lockfile
uv pip compile pyproject.toml --output-file requirements.txt

# Upgrade specific package
uv pip install --upgrade package_name

# Update development dependencies
uv pip install -e ".[dev]" --upgrade
```

### Configuration Management

- Settings are centralized in `config/settings.py`
- Environment variables override defaults
- Use `.env.example` as template for new deployments
- Validate configuration with `LOG_LEVEL=DEBUG`

### Monitoring

```bash
# Enable metrics collection
METRICS_ENABLED=true METRICS_PORT=9090 uv run python main.py

# Access metrics (if monitoring dependencies installed)
curl http://localhost:9090/metrics
```

### Backup and Recovery

- Configuration: Back up `.env` file
- No persistent state (stateless MCP server)
- API credentials should be stored securely

## Contributing

### Code Standards

- **Formatting**: Black (line length: 100)
- **Import sorting**: isort (Black profile)
- **Type checking**: mypy (strict mode)
- **Linting**: flake8
- **Testing**: pytest with asyncio support

### Commit Workflow

```bash
# Before committing
uv run pre-commit run --all-files

# Run full test suite
uv run pytest --cov=core --cov=modules --cov=tools

# Ensure code quality
uv run black . && uv run isort . && uv run flake8 . && uv run mypy .
```

### Documentation Updates

When adding features:
1. Update this WARP.md file
2. Add docstrings to new classes/functions
3. Include examples in tool descriptions
4. Update configuration options if added

---

**Last Updated**: 2025-01-04 | **MCP Protocol**: 2024-11-05 | **Server Version**: 2.0.0
