def print_trace(messages):
    for i, m in enumerate(messages):
        m_type = type(m).__name__
        name = getattr(m, "name", None)
        content = getattr(m, "content", None)
        tool_calls = getattr(m, "tool_calls", None)

        print(f"\n[{i}] type={m_type} name={name}")
        if tool_calls:
            print(f"tool_calls={tool_calls}")
        if content:
            print(f"content={content}") 