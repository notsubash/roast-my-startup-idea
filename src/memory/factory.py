import logging

from config import get_settings
from memory.store import IdeaStore
from modeling import build_embedding_fn

logger = logging.getLogger(__name__)


def build_idea_store() -> IdeaStore:
    settings = get_settings()
    embed_fn = None
    enable_semantic = settings.enable_semantic_memory
    if enable_semantic:
        try:
            embed_fn = build_embedding_fn(settings)
        except ValueError as exc:
            logger.warning(
                "Semantic memory disabled: %s. Falling back to recency-only memory.",
                exc,
            )
            enable_semantic = False
    return IdeaStore(
        embed_fn=embed_fn,
        embedding_dimension=settings.embedding_dimension,
        enable_semantic=enable_semantic,
    )
