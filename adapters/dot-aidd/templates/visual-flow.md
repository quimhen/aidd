# Visual Flow — [feature name]

One Mermaid flowchart per US-nnn. Every node cites its SCREEN-XX/CTL-nnn code — never a redescription.
This file is the artifact used for interactive correction in Align: edit the diagram, don't describe the fix in prose.

## US-001 — [use case description]

```mermaid
flowchart TD
  A([Entry point]) --> B[SCREEN-01 Screen name]
  B --> C{CTL-001 Action}
  C -- condition A --> D[Result A]
  C -- condition B --> E[Result B]
```

Status: [Explicit | draft pending user confirmation]

## US-002 — [use case description]

```mermaid
flowchart TD
  A([Entry point]) --> B[SCREEN-XX ...]
```

Status: [Explicit | draft pending user confirmation]
