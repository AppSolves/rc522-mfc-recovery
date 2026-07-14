# Security policy

## Authorized use

Use this software only with cards you own or are explicitly authorized to test. Do not use recovered credentials to access systems, services, buildings, accounts, or stored value without permission.

## Sensitive artifacts

Treat the following as secrets:

- card UIDs,
- recovered Key A and Key B values,
- nonce datasets,
- full card dumps,
- solver logs,
- application data decoded from a dump.

They are excluded by `.gitignore`, but Git cannot protect files that were already committed. Review `git status --ignored`, the complete Git history, and release archives before publishing.

## Reporting vulnerabilities

Do not open a public issue containing real credentials or card data. Report software vulnerabilities privately through GitHub Security Advisories when the public repository enables them.

## Read-only scope

The bundled native frontend contains no write command. A raw dump is read-only. Contributions that add writing, cloning, or access-control bypass workflows require separate security review and may be rejected.
