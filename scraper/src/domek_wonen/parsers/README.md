# Parsers Module

This module will own:

- parser families
- source configs
- normalized parser output

The architecture rule is simple: no parser per makelaar. Shared technical patterns belong in parser families, while domain-specific adjustments belong in source configs.
