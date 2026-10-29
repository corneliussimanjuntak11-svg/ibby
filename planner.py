from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from datetime import date, timedelta
import json
import os
import re

from guardrail import is_ib_related
from dates import parse_natural_date, format_natural_date

load_dotenv()

model = ChatAnthropic(model="claude-haiku-4-5-20251001")

PLANS_FILE = "plans.json"


def load_plans():
    if os.path.exists(PLANS_FILE):
        with open(PLANS_FILE, "r") as f:
            return json.load(f)
    return []


def save_plans(plans):
    with open(PLANS_FILE, "w") as f:
        json.dump(plans, f, indent=2)


def parse_index(choice, length):
    """Turns a 1-based number typed by the user into a 0-based list index, or None if invalid."""
    try:
        n = int(choice)
    except ValueError:
        return None
    if 1 <= n <= length:
        return n - 1
    return None


def display_date(date_str):
    """Converts a stored YYYY-MM-DD string into natural format for display, falling back to the raw string."""
    parsed = parse_natural_date(date_str)
    return format_natural_date(parsed) if parsed else date_str


def strip_code_fences(text):
    """Removes a leading/trailing ``` or ```json fence, if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.lower().startswith("json"):
            text = text[4:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def generate_milestones_raw(goal, deadline_str):
    """Asks Claude for a realistic weekly milestone plan, returned as strict JSON."""
    today = date.today().isoformat()

    prompt = f"""A student wants to break down a goal into realistic weekly milestones.

Today's date: {today}
Goal: {goal}
Deadline: {deadline_str}

Break this goal down into a realistic list of WEEKLY milestones leading up to the deadline,
using today's date to calculate when the first milestone should start.
Each milestone needs:
- title: a short milestone title
- description: a short description of what to do for that milestone
- estimated_hours: a realistic estimated number of hours to complete it (a number)
- due_date: the date this milestone should be completed by, written as YYYY-MM-DD

Respond with ONLY a valid JSON array, nothing else before or after it. Example format:
[
  {{"title": "...", "description": "...", "estimated_hours": 5, "due_date": "2026-09-01"}},
  {{"title": "...", "description": "...", "estimated_hours": 4, "due_date": "2026-09-08"}}
]"""

    return model.invoke(prompt).content


def parse_milestones(raw_text):
    """Turns Claude's JSON response into a Python list of milestone dicts, or None if invalid."""
    text = strip_code_fences(raw_text)
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None

    try:
        milestones = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    if not isinstance(milestones, list) or not milestones:
        return None

    return milestones


def create_plan():
    while True:
        goal = input("\nWhat's your goal? ").strip()
        if goal.lower() == "back":
            return

        related = is_ib_related(goal)
        if related is None:
            print("I couldn't quite tell if that's IB-related — could you rephrase it?")
            continue
        if related is False:
            print("Ibby only plans IB-related goals — things like finishing a Math IA, or revising for a Biology exam.")
            print("Type 'back' to return to the menu, or try a different goal.")
            continue
        break

    deadline = None
    while deadline is None:
        deadline_input = input("Deadline (for example: May 5th 2026): ").strip()
        if deadline_input.lower() == "back":
            return

        deadline = parse_natural_date(deadline_input)
        if deadline is None:
            print("I couldn't understand that date. Try something like 'May 5th 2026', 'May 5, 2026', "
                  "'5 May 2026', or 2026-05-05 (numeric-only dates like 5/5/2026 are ambiguous — please spell out the month).")
            continue

        if deadline <= date.today():
            print("That deadline needs to be in the future. Please try again.")
            deadline = None
            continue

        confirm = input(f"Got it: {format_natural_date(deadline)}. Is that right? (yes/no): ").strip().lower()
        if confirm != "yes":
            deadline = None

    deadline_str = deadline.isoformat()

    while True:
        raw = generate_milestones_raw(goal, deadline_str)
        milestones = parse_milestones(raw)
        if milestones is None:
            print("\nHmm, I couldn't read that as a valid milestone plan.")
            retry = input("Try generating the plan again? (yes/no): ").strip().lower()
            if retry == "yes":
                continue
            print("Cancelled — no plan was saved.")
            return
        break

    for m in milestones:
        m["completed"] = False

    plans = load_plans()
    plans.append({
        "goal": goal,
        "deadline": deadline_str,
        "milestones": milestones,
    })
    save_plans(plans)
    print(f"\nPlan saved! '{goal}' now has {len(milestones)} weekly milestones, due by {format_natural_date(deadline)}.")


def view_plans():
    plans = load_plans()
    if not plans:
        print("\nYou don't have any saved plans yet. Create one from the main menu!")
        return

    today = date.today()
    for i, plan in enumerate(plans, 1):
        milestones = plan["milestones"]
        done = sum(1 for m in milestones if m.get("completed"))
        total = len(milestones)
        print(f"\n{i}. {plan['goal']} (deadline: {display_date(plan['deadline'])}) — {done}/{total} done")

        for m in milestones:
            box = "[x]" if m.get("completed") else "[ ]"
            line = f"   {box} {m.get('title', 'Untitled')} — due {display_date(m.get('due_date', ''))}, ~{m.get('estimated_hours', '?')}h"

            if not m.get("completed"):
                due = parse_natural_date(m.get("due_date", ""))
                if due is not None and due < today:
                    line += "  [OVERDUE — consider requesting an extension]"

            print(line)
            if m.get("extension_reason"):
                print(f"       extended: {m['extension_reason']}")


def mark_milestone():
    plans = load_plans()
    if not plans:
        print("\nYou don't have any saved plans yet.")
        return

    print("\nYour plans:")
    for i, plan in enumerate(plans, 1):
        print(f"{i}. {plan['goal']}")

    pidx = parse_index(input("\nWhich plan? (number): ").strip(), len(plans))
    if pidx is None:
        print("Invalid selection.")
        return

    plan = plans[pidx]
    milestones = plan["milestones"]
    if not milestones:
        print("This plan has no milestones.")
        return

    print(f"\nMilestones for '{plan['goal']}':")
    for i, m in enumerate(milestones, 1):
        box = "[x]" if m.get("completed") else "[ ]"
        print(f"{i}. {box} {m.get('title', 'Untitled')} — due {display_date(m.get('due_date', ''))}")

    midx = parse_index(input("\nWhich milestone do you want to toggle? (number): ").strip(), len(milestones))
    if midx is None:
        print("Invalid selection.")
        return

    milestones[midx]["completed"] = not milestones[midx].get("completed", False)
    save_plans(plans)
    state = "complete" if milestones[midx]["completed"] else "not complete"
    print(f"\nMarked '{milestones[midx].get('title', 'Untitled')}' as {state}.")


def request_extension():
    plans = load_plans()
    if not plans:
        print("\nYou don't have any saved plans yet.")
        return

    print("\nYour plans:")
    for i, plan in enumerate(plans, 1):
        print(f"{i}. {plan['goal']}")

    pidx = parse_index(input("\nWhich plan? (number): ").strip(), len(plans))
    if pidx is None:
        print("Invalid selection.")
        return

    plan = plans[pidx]
    milestones = plan["milestones"]
    if not milestones:
        print("This plan has no milestones.")
        return

    print(f"\nMilestones for '{plan['goal']}':")
    for i, m in enumerate(milestones, 1):
        print(f"{i}. {m.get('title', 'Untitled')} — due {display_date(m.get('due_date', ''))}")

    midx = parse_index(input("\nWhich milestone needs an extension? (number): ").strip(), len(milestones))
    if midx is None:
        print("Invalid selection.")
        return

    try:
        extra_days = int(input("How many extra days? ").strip())
    except ValueError:
        print("Please enter a whole number of days.")
        return
    if extra_days <= 0:
        print("Extension must be a positive number of days.")
        return

    reason = input("Short reason for the extension: ").strip()

    target_due = parse_natural_date(milestones[midx].get("due_date", ""))
    if target_due is None:
        print("That milestone doesn't have a valid due date to shift.")
        return

    delta = timedelta(days=extra_days)
    for m in milestones[midx:]:
        d = parse_natural_date(m.get("due_date", ""))
        if d is not None:
            m["due_date"] = (d + delta).isoformat()

    milestones[midx]["extension_reason"] = reason

    plan_deadline = parse_natural_date(plan.get("deadline", ""))
    at_risk = False
    if plan_deadline is not None:
        at_risk = any(
            (parse_natural_date(m.get("due_date", "")) or plan_deadline) > plan_deadline
            for m in milestones
        )

    if at_risk:
        print(f"\nHeads up: this pushes some milestones past your plan's final deadline "
              f"({format_natural_date(plan_deadline)}).")
        choice = input("Do you want to (a) keep the original deadline or (b) extend the final deadline too? ").strip().lower()
        if choice == "b":
            latest = max(
                (parse_natural_date(m.get("due_date", "")) for m in milestones if parse_natural_date(m.get("due_date", ""))),
                default=plan_deadline,
            )
            plan["deadline"] = latest.isoformat()
            print(f"Final deadline extended to {format_natural_date(latest)}.")
        else:
            print("Keeping the original final deadline — just know some milestones now run past it.")

    save_plans(plans)
    print(f"\nExtension saved: '{milestones[midx].get('title', 'Untitled')}' moved to "
          f"{display_date(milestones[midx]['due_date'])}.")


def delete_plan():
    plans = load_plans()
    if not plans:
        print("\nYou don't have any saved plans yet.")
        return

    print("\nYour plans:")
    for i, plan in enumerate(plans, 1):
        print(f"{i}. {plan['goal']} (deadline: {display_date(plan['deadline'])})")

    idx = parse_index(input("\nWhich plan would you like to delete? (number): ").strip(), len(plans))
    if idx is None:
        print("Invalid selection.")
        return

    confirm = input(f"Are you sure you want to delete '{plans[idx]['goal']}'? (yes/no): ").strip().lower()
    if confirm == "yes":
        removed = plans.pop(idx)
        save_plans(plans)
        print(f"Deleted '{removed['goal']}'.")
    else:
        print("Cancelled — nothing was deleted.")


def main():
    while True:
        print("\n=== Planner ===")
        print("1. Create a new plan")
        print("2. View my plans")
        print("3. Mark a milestone complete or not complete")
        print("4. Request an extension")
        print("5. Delete a plan")
        print("6. Exit")

        choice = input("Choose an option (1-6): ").strip()

        if choice == "1":
            create_plan()
        elif choice == "2":
            view_plans()
        elif choice == "3":
            mark_milestone()
        elif choice == "4":
            request_extension()
        elif choice == "5":
            delete_plan()
        elif choice == "6":
            print("Goodbye!")
            break
        else:
            print("Please choose a number from 1 to 6.")


if __name__ == "__main__":
    main()
