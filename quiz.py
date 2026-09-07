from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
import json
import os

load_dotenv()

model = ChatAnthropic(model="claude-haiku-4-5-20251001")

PROGRESS_DIR = "progress"


def get_progress_path(subject):
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    return os.path.join(PROGRESS_DIR, f"{subject}.json")


def get_progress_key(subject, math_type=None):
    """Mathematics tracks Standard and Extended progress separately, in their own files."""
    if math_type:
        return f"{subject} {math_type}"
    return subject


def load_progress(subject):
    path = get_progress_path(subject)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_progress(subject, progress):
    with open(get_progress_path(subject), "w") as f:
        json.dump(progress, f, indent=2)


def is_ib_related(subject, topic):
    check_prompt = f"""A student wants a quiz question for their IB (International Baccalaureate) MYP studies.

Subject: {subject}
Topic: {topic}

Is this a legitimate school subject and topic (including common abbreviations, e.g. "Math" for "Mathematics")? Answer only "yes" or "no"."""
    result = model.invoke(check_prompt)
    print(f"[is_ib_related] raw model output: {result.content!r}")
    return "yes" in result.content.lower()


DIFFICULTY_INSTRUCTIONS = {
    "Needs Practice": "Make this an EASY, foundational question that reinforces basic concepts and definitions.",
    "Improving": "Make this a STANDARD difficulty question appropriate for an MYP student with a working understanding of the topic.",
    "Mastered": "Make this a HARD, challenging question that tests deeper understanding, application, or analysis — not just recall.",
}

MATH_LEVEL_INSTRUCTIONS = {
    "Standard": "This is MYP Mathematics STANDARD level — keep the problem more straightforward, with a clear, direct method to solve it.",
    "Extended": "This is MYP Mathematics EXTENDED level — make the problem noticeably more challenging than Standard level: require multi-step reasoning, more complex numbers or contexts, and less scaffolding.",
}


def generate_question(subject, topic, math_type=None):
    """
    Returns a dictionary with the question text, options, and correct answer
    separated out, so our code can check answers automatically.
    """
    if not is_ib_related(subject, topic):
        return None

    progress_key = get_progress_key(subject, math_type)
    progress = load_progress(progress_key)
    stats = progress.get(topic, {"correct": 0, "attempted": 0})
    mastery = get_mastery_level(stats["correct"], stats["attempted"])
    difficulty_instruction = DIFFICULTY_INSTRUCTIONS[mastery]

    subject_line = f"Subject: {subject}" + (f" ({math_type})" if math_type else "")
    level_line = f"\n{MATH_LEVEL_INSTRUCTIONS[math_type]}" if math_type else ""

    prompt = f"""Create ONE multiple-choice quiz question for an MYP (IB Middle Years Programme) student.

{subject_line}
Topic: {topic}
Difficulty: {mastery}. {difficulty_instruction}{level_line}

Respond in EXACTLY this format, nothing else:
QUESTION: [question text]
A: [option A]
B: [option B]
C: [option C]
D: [option D]
CORRECT: [just the letter, e.g. B]
EXPLANATION: [short explanation]"""

    response = model.invoke(prompt).content
    return response


def parse_question(raw_text):
    """Turns Claude's formatted response into a usable dictionary."""
    lines = raw_text.strip().split("\n")
    data = {}
    for line in lines:
        if line.startswith("QUESTION:"):
            data["question"] = line.replace("QUESTION:", "").strip()
        elif line.startswith("A:"):
            data["A"] = line.replace("A:", "").strip()
        elif line.startswith("B:"):
            data["B"] = line.replace("B:", "").strip()
        elif line.startswith("C:"):
            data["C"] = line.replace("C:", "").strip()
        elif line.startswith("D:"):
            data["D"] = line.replace("D:", "").strip()
        elif line.startswith("CORRECT:"):
            data["correct"] = line.replace("CORRECT:", "").strip()
        elif line.startswith("EXPLANATION:"):
            data["explanation"] = line.replace("EXPLANATION:", "").strip()
    return data


def generate_hint(q, wrong_answer):
    """Generates a guiding hint for a wrong answer, without revealing the correct one."""
    prompt = f"""A student answered a multiple-choice question incorrectly. Give ONE short, \
guiding hint (1-2 sentences) that helps them think through the problem themselves. \
Do NOT state or imply which option is correct, and do NOT reveal the answer.

Question: {q['question']}
A: {q['A']}
B: {q['B']}
C: {q['C']}
D: {q['D']}
Student's incorrect answer: {wrong_answer}"""

    return model.invoke(prompt).content.strip()


def get_mastery_level(correct, attempted):
    ratio = correct / attempted if attempted else 0
    if ratio < 0.5:
        return "Needs Practice"
    elif ratio < 0.8:
        return "Improving"
    else:
        return "Mastered"


def record_result(subject, topic, correct, math_type=None):
    progress_key = get_progress_key(subject, math_type)
    progress = load_progress(progress_key)
    key = topic
    if key not in progress:
        progress[key] = {"correct": 0, "attempted": 0}
    progress[key]["attempted"] += 1
    if correct:
        progress[key]["correct"] += 1
        progress["_streak"] = progress.get("_streak", 0) + 1
    else:
        progress["_streak"] = 0
    save_progress(progress_key, progress)
    return progress[key], progress["_streak"]


def run_quiz(subject, topic, math_type=None):
    """Runs one full quiz question interaction with a real student."""
    raw = generate_question(subject, topic, math_type)
    if raw is None:
        print("I'm here to help with your IB studies. Try asking me something related to your coursework!")
        return

    q = parse_question(raw)

    print(q["question"])
    print(f"A: {q['A']}")
    print(f"B: {q['B']}")
    print(f"C: {q['C']}")
    print(f"D: {q['D']}")

    max_attempts = 5
    is_correct = False

    for attempt in range(1, max_attempts + 1):
        answer = input("\nYour answer (A/B/C/D): ").strip().upper()
        is_correct = (answer == q["correct"])

        if is_correct:
            print("\n✅ Correct!")
            break
        elif attempt < max_attempts:
            hint = generate_hint(q, answer)
            print(f"\n❌ Not quite. Hint: {hint}")
            print("Give it another try!")
        else:
            print(f"\n❌ Not quite. The correct answer was {q['correct']}.")

    print(f"Explanation: {q['explanation']}")

    stats, streak = record_result(subject, topic, is_correct, math_type)
    mastery = get_mastery_level(stats["correct"], stats["attempted"])
    print(
        f"\nYour progress on {topic}: {stats['correct']}/{stats['attempted']} correct")
    print(f"Current streak: {streak}")
    print(f"Mastery level: {mastery}")


if __name__ == "__main__":
    subject = input("Which subject would you like to be quizzed on? ").strip()

    math_type = None
    if subject.lower() in ("mathematics", "math"):
        math_type = input(
            "Which type — Standard or Extended? ").strip().capitalize()
        while math_type not in ("Standard", "Extended"):
            math_type = input(
                "Please enter Standard or Extended: ").strip().capitalize()

    topic = input("Which topic within that subject? ").strip()
    run_quiz(subject, topic, math_type)
