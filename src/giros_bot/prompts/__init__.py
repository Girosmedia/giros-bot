"""Todos los prompts del bot — punto de entrada centralizado."""

from .scout import SCOUT_PROMPT_TEMPLATE
from .social import SOCIAL_PROMPT_TEMPLATE
from .strategist import STRATEGIST_PROMPT_TEMPLATE
from .system import SYSTEM_IDENTITY
from .validator import VALIDATOR_PROMPT_TEMPLATE
from .visual import VISUAL_PROMPT_TEMPLATE
from .writer import WRITER_PROMPT_TEMPLATE

__all__ = [
    "SYSTEM_IDENTITY",
    "SCOUT_PROMPT_TEMPLATE",
    "STRATEGIST_PROMPT_TEMPLATE",
    "WRITER_PROMPT_TEMPLATE",
    "SOCIAL_PROMPT_TEMPLATE",
    "VISUAL_PROMPT_TEMPLATE",
    "VALIDATOR_PROMPT_TEMPLATE",
]
