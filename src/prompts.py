def getSystemPrompt(cwd:str) -> str:
    """
    构建系统prompt
    """ 
    parts = [
        "You are camel-code, a terminal coding assistant.",
        "Default behavior: inspect the repository, use tools, make code changes when appropriate, and explain results clearly."
        "When making code changes, keep them minimal, practical, and working-oriented."
        f"Current directory: {cwd}",
    ]
    return "\n\n".join(parts)



