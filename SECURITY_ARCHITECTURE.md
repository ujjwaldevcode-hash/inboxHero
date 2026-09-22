# InboxHero Security-First Architecture

## Processing boundary

```text
INBOX
  |
  v
Rule Gate + Granite Guardian
  |
  +---- THREAT ----> Quarantine / Flagged
  |
  +---- SAFE ------> Irreversible Guard
                         |
                         +---- REFUSE ----> Human Review
                         |
                         +---- ALLOW ----> Owner Preference Security
                                             |
                                             v
                                      Generic Noise Filter
                                             |
                                             v
                                      Q1-Q4 Triage
                                             |
                                             v
                                  Existing InboxHero Agent
```

## Security invariants

1. A threat never reaches persistent preference extraction.
2. A threat never reaches normal agent processing.
3. An irreversible/high-impact instruction is refused before normal agent processing.
4. Irreversible actions remain subject to the existing human approval gate.
5. Only explicit owner-authored preferences can become persistent preferences.
6. Unsafe or unknown preference-security results are not persisted.
7. The dashboard excludes quarantined threats from normal pending actions and commitments.

## Models

- Security gate: Granite Guardian (`granite4.1-guardian:8b`)
- Threat labeling: Gemma (`gemma4:12b`)
- Preference security: Gemma (`gemma4:12b`)
- Existing R1 triage/agent: configured InboxHero local model, default `gemma4:26b`

The full pipeline requires a local Ollama installation with the configured models.
