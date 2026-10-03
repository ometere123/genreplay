# { "Depends": "py-genlayer:test" }

"""Studionet certification fixture only. It is not part of the GenReplay package."""

from genlayer import gl


class GenreplayFixture(gl.Contract):
    last_decision: str

    def __init__(self):
        self.last_decision = ""

    @gl.public.write
    def decide(self, subject: str) -> str:
        """Store a narrow LLM decision while exercising strict equivalence output."""
        if len(subject) < 1 or len(subject) > 32:
            raise Exception("subject must contain 1 to 32 characters")

        def leader_decision() -> str:
            answer = gl.exec_prompt(
                "Reply with exactly YES or NO. Is this identifier non-empty? Identifier: " + subject
            ).strip().upper()
            if answer not in ("YES", "NO"):
                raise Exception("model returned an invalid decision")
            return answer

        decision = gl.eq_principle_strict_eq(leader_decision)
        self.last_decision = decision
        return decision

    @gl.public.view
    def get_last_decision(self) -> str:
        return self.last_decision
