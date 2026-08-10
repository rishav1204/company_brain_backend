"""Prompt optimization — dedupe, compress, budget enforce (Wave 6)."""

from __future__ import annotations

import hashlib
import re


_WS_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")
_DUP_LINE_RE = re.compile(r"(?m)^(.*)$\n(?:\1\n)+")


class PromptOptimizer:
    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text or "") // 4)

    def fingerprint(self, system: str, user: str) -> str:
        raw = f"{system}\n---\n{user}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def optimize(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        budget_tokens: int,
        preserve_correctness: bool = True,
    ) -> tuple[str, str, list[str], int]:
        """Return (system, user, notes, estimated_tokens). Never invents facts."""
        notes: list[str] = []
        system = self._normalize(system_prompt or "")
        user = self._normalize(user_prompt or "")

        # Deduplicate exact repeated lines in user (context dumps)
        user2, n_dup = self._dedupe_lines(user)
        if n_dup:
            notes.append(f"deduped_lines={n_dup}")
            user = user2

        # Collapse excessive whitespace
        before = len(system) + len(user)
        system = _BLANK_RE.sub("\n\n", system)
        user = _BLANK_RE.sub("\n\n", user)
        after = len(system) + len(user)
        if after < before:
            notes.append("collapsed_whitespace")

        # Instruction reuse: strip redundant trust rules if already in system
        if "untrusted" in system.lower() and "untrusted" in user.lower():
            user = re.sub(r"(?i).*untrusted.*\n?", "", user, count=3)
            notes.append("stripped_redundant_trust_echo")

        est = self.estimate_tokens(system) + self.estimate_tokens(user)
        if est > budget_tokens:
            # Prefer truncating user (data), keep system intact for correctness
            system_tokens = self.estimate_tokens(system)
            user_budget = max(200, budget_tokens - system_tokens)
            user = self._truncate_to_tokens(user, user_budget, preserve_tail=True)
            notes.append(f"truncated_user_to={user_budget}_tokens")
            est = self.estimate_tokens(system) + self.estimate_tokens(user)

        if not notes:
            notes.append("no_change")
        return system, user, notes, est

    def _normalize(self, text: str) -> str:
        t = text.replace("\r\n", "\n").strip()
        t = _WS_RE.sub(" ", t)
        return t

    def _dedupe_lines(self, text: str) -> tuple[str, int]:
        seen: set[str] = set()
        out: list[str] = []
        dups = 0
        for line in text.split("\n"):
            key = line.strip()
            if not key:
                out.append(line)
                continue
            if key in seen and len(key) > 40:
                dups += 1
                continue
            seen.add(key)
            out.append(line)
        return "\n".join(out), dups

    def _truncate_to_tokens(self, text: str, budget: int, *, preserve_tail: bool = True) -> str:
        chars = max(80, budget * 4)
        if len(text) <= chars:
            return text
        if preserve_tail:
            # Keep head (instructions) + tail (user question often last)
            head = text[: int(chars * 0.65)]
            tail = text[-int(chars * 0.30) :]
            return head + "\n…[context truncated for budget]…\n" + tail
        return text[:chars] + "\n…[truncated]…"


prompt_optimizer = PromptOptimizer()
