"""Mock LLM used by the final production agent.

The lab focuses on deployment, security, and reliability, so this module
returns deterministic local responses instead of calling a paid LLM API.
"""
import random
import time


MOCK_RESPONSES = {
    "docker": [
        "Container la cach dong goi ung dung cung dependencies de chay nhat quan o moi moi truong."
    ],
    "deploy": [
        "Deployment la qua trinh dua ung dung tu moi truong local len server hoac cloud de nguoi dung co the truy cap."
    ],
    "health": [
        "Health check giup platform biet service con song va co can restart hay khong."
    ],
    "default": [
        "Agent da nhan cau hoi va tra ve cau tra loi mock cho bai lab deployment.",
        "Day la response mock. Trong production co the thay bang OpenAI hoac Anthropic API.",
        "Ung dung dang hoat dong dung, co the tiep tuc test authentication, rate limit va health check.",
    ],
}


def ask(question: str, delay: float = 0.05) -> str:
    """Return a mock answer based on simple keyword matching."""
    time.sleep(delay + random.uniform(0, 0.03))
    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])
