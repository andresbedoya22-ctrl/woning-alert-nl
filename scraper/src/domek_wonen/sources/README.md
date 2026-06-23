# Sources Module

This module will own:

- source registry
- source intelligence
- access policy
- delivery mode fingerprinting

Its job is to decide what a source is, what is known about it, whether it is allowed, and which parser family should eventually handle it. It should not become a dumping ground for listing parsing or matching logic.
