---
name: hermes-skills-hub
description: "Use when installing Hermes skills from the registry."
tags: [hermes, skills, registro, instalacion, catalogo, hub]
version: 1.0.0
---

# Hermes Agent Skills Hub

## Overview
- **Total Skills:** 649 across 4 registries
- **71 Built-in** (pre-installed with Hermes)
- **57 Optional** (need installation)
- **521 Community** (third-party)

## Categories (17 total)
| Category | Count | Examples |
|----------|-------|----------|
| 📦 Other | 347 | Miscellaneous tools |
| 💻 Software Dev | 69 | plan, TDD, debugging, code review |
| 🎨 Creative | 60 | ASCII art, diagrams, video |
| 🧪 MLOps | 40 | LLM training, inference, evaluation |
| 🔍 Research | 38 | Arxiv, blog monitoring, papers |
| 🌍 Translation | 24 | Multilingual tools |
| ✅ Productivity | 13 | Notion, Google, PDF, PowerPoint |
| 🎮 Gaming | 11 | Minecraft, Pokemon |
| ❤ Health | 8 | Health tracking tools |
| 📱 Social Media | 7 | Twitter/X, Facebook |
| 🤖 AI Agents | 6 | Claude Code, Codex, OpenCode |
| 💻 GitHub | 6 | PR workflow, issues, code review |
| 🎵 Media | 6 | GIFs, music, YouTube |
| 🔒 Security | 6 | Red teaming, security tools |
| 🍎 Apple | 4 | Notes, Reminders, iMessage, FindMy |
| 📝 Copywriting | 4 | Writing assistants |

## How to Install New Skills
1. Visit https://hermes-agent.nousresearch.com/docs/skills/
2. Browse or search for the skill
3. Use `skill_view(name)` to load the skill content
4. The skill is automatically available after loading

## Already Installed (84 skills)
See `/opt/data/skills/` for all installed skills.

## Key Skills for Nexa Labs
- **Software Dev:** plan, writing-plans, subagent-driven-development, test-driven-development, systematic-debugging, requesting-code-review, codebase-inspection
- **Productivity:** notion, google-workspace, nano-pdf, powerpoint, linear, ocr-and-documents
- **Email/Social:** himalaya, xitter, gif-search
- **Creative:** architecture-diagram, popular-web-designs, excalidraw, ascii-art
- **Research:** arxiv, blogwatcher, polymarket
- **MLOps:** huggingface-hub, llama-cpp, vllm, whisper, stable-diffusion, guidance, outlines

## Important Notes
- The Skills Hub is client-side rendered (React/Docusaurus) — need browser to see full list
- Built-in skills come pre-installed
- Optional and Community skills need to be discovered and installed
- Skills are organized by category and can be filtered
- Each skill has a SKILL.md file with usage instructions
