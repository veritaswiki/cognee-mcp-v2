## Description

Brief description of what this PR does.

Fixes # (issue)

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement
- [ ] Test improvement

## Component(s) Changed

- [ ] MCP Server Core
- [ ] Base Tools (add_text, add_files, cognify, search)
- [ ] Dataset Tools
- [ ] Graph Tools
- [ ] Temporal Tools
- [ ] Ontology Tools
- [ ] Memory Tools
- [ ] Self-improving Tools
- [ ] Diagnostic Tools
- [ ] Configuration/Settings
- [ ] Authentication
- [ ] Documentation
- [ ] Tests
- [ ] CI/CD

## How Has This Been Tested?

Please describe the tests that you ran to verify your changes:

- [ ] Unit tests pass (`uv run pytest`)
- [ ] Integration tests pass
- [ ] MCP protocol compliance tests pass
- [ ] Manual testing performed

**Test Configuration:**
- Python version: 
- OS: 
- uv version:

## Checklist

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## MCP-Specific Checklist (if applicable)

- [ ] New tools are properly registered with `@register_tool_class`
- [ ] Tool input schemas are properly defined and validated
- [ ] Tool responses follow the standard format
- [ ] Error handling follows project conventions
- [ ] Authentication requirements are properly set
- [ ] Timeout values are appropriate

## Security Considerations

- [ ] No sensitive data is logged or exposed
- [ ] Input validation is properly implemented
- [ ] Authentication/authorization is properly handled
- [ ] Rate limiting considerations have been addressed

## Breaking Changes

List any breaking changes and migration steps if applicable:

## Additional Notes

Any additional information that reviewers should know.
