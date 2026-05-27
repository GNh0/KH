---
name: antigravity-bridge
description: Allows Claude Code, Cursor, Codex, or any other external agent to discover and use Antigravity's massive built-in skill ecosystem (Science, Android, etc.).
---
# Antigravity Ecosystem Bridge

This skill acts as a universal portal. It allows YOU (the external agent) to tap into Antigravity's deep pool of native skills, such as AlphaFold analysis, Literature Search, and Android CLI tools, regardless of what LLM or framework you are running on.

## Instructions
If you need to perform a complex task (like searching scientific databases, fetching protein structures, or managing Android builds), follow these steps to see if an Antigravity tool already exists for it:

1. **Discover Available Skills:**
   Run the bridge script to list all installed Antigravity skills in JSON format:
   `python -m src.skills.antigravity_bridge --list`

2. **Select the Right Skill:**
   Look through the JSON output. Find the `name` of the skill whose `description` matches your current task.

3. **Read the Skill Manual (SOP):**
   To learn exactly how to use that skill, run:
   `python -m src.skills.antigravity_bridge --read <skill_name>`

4. **Execute:**
   The output will be a Markdown SOP (`SKILL.md`). Read it carefully and execute the terminal commands or python scripts it recommends just as if you were native to Antigravity!
