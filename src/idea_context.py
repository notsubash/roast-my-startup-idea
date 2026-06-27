"""Assemble startup idea text for judges, debate, and research."""

IDEA_TAG = "idea"


def wrap_untrusted(content: str, tag: str) -> str:
    """Wrap user-supplied text; escape interior close/open tags to prevent delimiter breakout."""
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    stripped = content.strip()
    if stripped.startswith(open_tag) and stripped.endswith(close_tag):
        stripped = stripped[len(open_tag) : -len(close_tag)].strip()
    escaped_open = open_tag.replace("<", "&lt;").replace(">", "&gt;")
    escaped_close = close_tag.replace("<", "&lt;").replace(">", "&gt;")
    sanitized = stripped.replace(close_tag, escaped_close).replace(open_tag, escaped_open)
    return f"{open_tag}\n{sanitized}\n{close_tag}"


def wrap_user_idea(content: str) -> str:
    return wrap_untrusted(content, IDEA_TAG)


def build_startup_idea_context(
    idea: str,
    *,
    target_customer: str | None = None,
    pricing: str | None = None,
    traction: str | None = None,
    competitors: list[str] | None = None,
) -> str:
    sections = [idea.strip()]
    if target_customer and target_customer.strip():
        sections.append(f"Target customer: {target_customer.strip()}")
    if pricing and pricing.strip():
        sections.append(f"Pricing: {pricing.strip()}")
    if traction and traction.strip():
        sections.append(f"Traction: {traction.strip()}")
    if competitors:
        named = ", ".join(competitor.strip() for competitor in competitors if competitor.strip())
        if named:
            sections.append(f"Competitors: {named}")
    return wrap_user_idea("\n\n".join(sections))
