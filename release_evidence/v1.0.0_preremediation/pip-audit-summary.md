# pip-audit summary

- Candidate: `agentic-financial-intelligence:1.0.0`
- Immutable local image ID: `sha256:b05d7725d17df2da7b94f8b73afc0aa9d6bcc384a227b48a1d031640104c3b0f`
- Input: 21 exact package versions captured from `/opt/venv/bin/python -m pip freeze --all`, excluding only the local application itself (`agentic-financial-intelligence @ file:///build`)
- Tool: `pip-audit 2.10.1`
- Vulnerability service: PyPI advisory service
- Result: no known vulnerabilities reported; exit code 0
- Finding disposition: no application-dependency findings to classify

This result is not a CVE-free claim. It covers the pinned Python distributions in the active
`/opt/venv` release environment. The container scan separately covers Debian packages, base-layer
Python tooling, and vendored packages that `pip-audit` does not enumerate as independent installed
distributions.
