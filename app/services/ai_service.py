import random
from pydantic import BaseModel

class AIReviewResult(BaseModel):
    score: int
    feedback: str

def generate_mock_ai_review(github_url: str, challenge_id: str) -> AIReviewResult:
    """
    MVP AI review service. Generates structured feedback based on the URL 
    and challenge ID to simulate an LLM analyzing the code.
    Designed to be easily replaced with an actual OpenAI/Anthropic call later.
    """
    # Deterministic randomness so the same PR gets the same review
    random.seed(f"{github_url}_{challenge_id}")
    
    score = random.randint(75, 98)
    
    strengths = [
        "Code is well-structured and easy to read.",
        "Good use of modular components.",
        "Error handling is implemented effectively.",
        "Clean logic with no obvious memory leaks.",
        "Nice job following the project's design patterns.",
        "Variables are named descriptively.",
        "Excellent separation of concerns."
    ]
    
    improvements = [
        "Consider adding more inline documentation for complex logic.",
        "You could optimize the database queries to reduce load.",
        "A few magic numbers could be extracted into constants.",
        "Test coverage could be improved for edge cases.",
        "Consider using type hints more consistently.",
        "A couple of functions are slightly too long and could be split."
    ]
    
    selected_strengths = random.sample(strengths, k=2)
    selected_improvements = random.sample(improvements, k=2)
    
    feedback = (
        "### Strengths\n"
        f"- {selected_strengths[0]}\n"
        f"- {selected_strengths[1]}\n\n"
        "### Areas for Improvement\n"
        f"- {selected_improvements[0]}\n"
        f"- {selected_improvements[1]}\n"
    )
    
    return AIReviewResult(score=score, feedback=feedback)
