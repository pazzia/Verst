---
name: changelog
description: Update docs/WHATS-NEW.md, the Russian list of what testers will see, from the `Тестерам:` commit trailers since the last entry. Use after a merge or a release, or when the CEO asks «что нового» / «что изменилось».
---

# /changelog — «Что нового» для людей

1. Read `docs/WHATS-NEW.md`. The comment `<!-- last: <sha> -->` names the last commit already covered.
2. Collect the new items: `python3 tools/ci/whats_new.py --since <sha>` (newest first, de-duplicated).
3. Commits without a `Тестерам:` trailer:
   - Read their subjects: `git log --format='%h %s' <sha>..HEAD`.
   - Add an item only for a change the user can see. Phrase it in plain Russian, as the tester would notice it.
   - Skip refactors, CI, docs and tests.
4. Write a new section on top: `## 0.3.N — ДД.ММ.ГГГГ`.
   - Take N from the latest release of that commit; if not released yet, use `## В работе — ДД.ММ.ГГГГ`.
   - One bullet per change, a full sentence, no internal names (no file, ticket or ADR ids).
5. Update `<!-- last: … -->` to the newest commit covered.
6. Commit (no `Тестерам:` trailer on this commit) and show the CEO the new section in the reply.

Never invent a change. When unsure whether something is visible, leave it out and name it in the reply.
