from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

model = ChatAnthropic(model="claude-haiku-4-5-20251001")


def is_ib_related(text):
    """
    Asks Claude whether a request relates to IB (International Baccalaureate) school work.
    Coursework, assignments, exams, the Personal Project, study planning, and school
    service/CAS-style activities all count as IB-related.

    Returns True, False, or None if Claude's reply couldn't be parsed strictly as
    YES or NO — the caller should treat None as "ask the user to rephrase" rather
    than silently blocking them.
    """
    check_prompt = f"""Is this request related to IB (International Baccalaureate) school work?
This includes coursework, assignments, exams, the Personal Project, study planning, and
school service/CAS-style activities.

Reply with EXACTLY one word: YES or NO.

Request: {text}"""

    reply = model.invoke(check_prompt).content.strip().upper()

    if reply.startswith("YES"):
        return True
    elif reply.startswith("NO"):
        return False
    return None
