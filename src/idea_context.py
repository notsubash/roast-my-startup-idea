"""Assemble startup idea text for judges, debate, and research."""


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
    return "\n\n".join(sections)
