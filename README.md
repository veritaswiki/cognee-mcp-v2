# Cognee MCP v2.0 - 企业级模块化重构版

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black)](https://github.com/psf/black)

基于官方API文档的Cognee MCP服务企业级重构版本，采用模块化架构实现四大核心功能。

## 🚀 核心特性

### 四大功能模块
- **🕒 时序感知 (Time Awareness)** - 自动时间戳记录和版本控制
- **🏗️ 本体支持 (Ontology Support)** - OWL/RDF-XML格式本体集成
- **⚡ 异步记忆 (Async Memory)** - Python asyncio非阻塞内存操作
- **🧠 自我改进记忆 (Self-Improving Memory)** - 基于用户反馈的动态优化

### 企业级架构
- **模块化设计** - 可插拔的功能模块
- **异步优先** - 全面async/await支持
- **企业级安全** - 多层认证、权限控制、审计日志
- **可观测性** - 完整监控、日志、指标体系
- **高可扩展** - 插件化工具加载机制

## 📋 项目状态

### 当前版本: v2.0.0-alpha

**✅ 已完成**：
- [x] 架构设计和技术规范
- [x] 项目基础设施 (配置、依赖、目录结构)
- [x] 企业级配置管理系统
- [x] 开发环境和工具链配置

**🚧 进行中**：
- [ ] 核心框架实现 (MCP服务器、认证、API客户端)
- [ ] 四大功能模块实现
- [ ] 工具集实现 (基于官方API)
- [ ] 测试套件和验证

**📋 待完成**：
- [ ] 性能优化和监控
- [ ] 文档完善
- [ ] 部署和配置
- [ ] 生产环境验证

## 🏗️ 架构概览

```
cognee_mcp_v2/
├── config/         # 配置管理
├── core/          # 核心框架
├── modules/       # 四大功能模块
│   ├── base/              # 基础功能
│   ├── time_awareness/    # 时序感知
│   ├── ontology_support/  # 本体支持
│   ├── async_memory/      # 异步记忆
│   └── self_improving/    # 自我改进
├── tools/         # MCP工具实现
├── schemas/       # 数据模型
└── tests/         # 测试套件
```

## 🛠️ 技术栈

- **核心**: Python 3.9+, AsyncIO, Pydantic 2.0+
- **网络**: aiohttp, httpx
- **本体处理**: rdflib, owlrl
- **自然语言**: textblob
- **数据处理**: numpy, pandas
- **测试**: pytest, pytest-asyncio
- **代码质量**: black, isort, flake8, mypy

## ⚡ 快速开始

### 环境准备

```bash
# 克隆项目
git clone https://github.com/veritaswiki/cognee-mcp-v2.git
cd cognee-mcp-v2

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate     # Windows

# 安装依赖
pip install -e ".[dev]"

# 复制配置模板
cp .env.example .env
# 编辑 .env 填写你的配置
```

### 配置设置

编辑 `.env` 文件，配置Cognee API连接：

```bash
# Cognee API配置
COGNEE_API_URL=https://mcp-cognee.veritas.wiki
COGNEE_API_KEY=your_jwt_token_here
COGNEE_API_EMAIL=your_email@example.com
COGNEE_API_PASSWORD=your_password

# 功能开关
FEATURE_TIME_AWARENESS=true
FEATURE_ONTOLOGY_SUPPORT=true
FEATURE_ASYNC_MEMORY=true
FEATURE_SELF_IMPROVING=true
```

### 运行服务

```bash
# 开发模式运行
python main.py

# 或使用安装的命令
cognee-mcp
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=core --cov=modules --cov=tools --cov-report=html
```

## 📊 监控和指标

服务启动后，可以访问：

- **健康检查**: `http://localhost:8080/health`
- **Prometheus指标**: `http://localhost:9090/metrics`
- **API文档**: `http://localhost:8080/docs`

## 🔧 开发

### 代码规范

```bash
# 格式化代码
black .
isort .

# 代码检查
flake8 .
mypy .

# 预提交检查
pre-commit run --all-files
```

### 添加新功能

1. 在相应模块目录下创建功能实现
2. 在`tools/`目录下添加对应的MCP工具
3. 在`tests/`目录下添加测试用例
4. 更新文档和配置

## 📚 文档

- [架构设计](ARCHITECTURE_v2.md) - 详细的架构设计文档
- [API文档](docs/API.md) - API接口文档
- [部署指南](docs/DEPLOYMENT.md) - 部署和运维指南
- [开发指南](docs/DEVELOPMENT.md) - 开发者指南

## 🔗 相关项目

- [Cognee官方文档](https://docs.cognee.ai/api-reference/introduction)
- [MCP协议规范](https://modelcontextprotocol.io/docs)
- [Legacy版本存档](https://github.com/veritaswiki/cognee-mcp-legacy)

## 🤝 贡献

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看[LICENSE](LICENSE)文件了解详情。

## 📞 联系

- **开发者**: 老王暴躁技术流
- **技术支持**: 技术问题找老王，别找别人
- **项目主页**: https://github.com/veritaswiki/cognee-mcp-v2

---

**⚡ 企业级 • 模块化 • 高性能 • 易扩展**