"""
Prompts for context compaction summaries.

"""


def build_compact_summary_prompt(conversation_text: str) -> str:
    return (
        "You are summarizing a conversation for context compression.\n"
        "Produce a structured summary in <summary> tags.\n\n"
        "Sections:\n"
        "1. Primary Request — What the user asked for\n"
        "2. Key Decisions — Important choices made\n"
        "3. Files Modified — Which files were changed and why\n"
        "4. Errors Encountered — Problems hit and how they were resolved\n"
        "5. Current State — Where things stand right now\n"
        "6. Pending Tasks — What still needs to be done\n\n"
        "Rules:\n"
        "- Be concise but preserve actionable details (file paths, command outputs, error messages)\n"
        "- Use <analysis> tags as scratchpad, then <summary> tags for final output\n"
        "- The summary will replace all messages before the recent tail\n\n"
        f"Conversation to summarize:\n\n{conversation_text}"
    )


def parse_summary_from_response(response: str) -> str | None:
    """Extract summary from model response."""
    import re
    match = re.search(r"<summary>([\s\S]*?)</summary>", response)
    if match:
        return match.group(1).strip()

    analysis = re.search(r"<analysis>([\s\S]*?)</analysis>", response)
    if not analysis:
        trimmed = response.strip()
        if trimmed:
            return trimmed
    return None


def build_context_collapse_summary_prompt(conversation_text: str) -> str:
    return (
        "You are creating a local context-collapse summary for an AI coding session.\n"
        "The summary will replace only this older message span in the model-visible context.\n"
        "The original transcript remains preserved outside the model-visible projection.\n\n"
        "Produce the final summary in <summary> tags.\n\n"
        "Preserve:\n"
        "- User intent and active goals\n"
        "- Completed tasks and current state\n"
        "- Important decisions and constraints\n"
        "- Tool calls and tool results that still matter\n"
        "- File reads/writes and code changes, with paths, function names, config names, and commands\n"
        "- Errors, failures, warnings, and exact messages when relevant\n"
        "- TODOs, uncertainty, follow-up constraints, and anything still relevant later\n\n"
        "Rules:\n"
        "- Do not invent facts or outcomes\n"
        "- Do not omit critical paths, function names, configuration keys, file paths, or error text\n"
        "- Keep it concise, but prefer specificity over vague compression\n"
        "- This is not a full conversation compact; summarize only the provided span\n\n"
        f"Messages to summarize:\n\n{conversation_text}"
    )
