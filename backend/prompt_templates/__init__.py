"""
backend/prompt_templates package
---------------------------------
All LLM prompts are maintained here, organized by purpose.

Files:
  briefings.py      — COMPANY/NEWS/SOCIAL_MEDIA briefing prompts
  editor.py         — EDITOR system message, COMPILE and SWEEP prompts
  queries.py        — Search query generation prompts for 3 researcher nodes
  email_outreach.py — B2B cold email generation system prompt
  quick_research.py — Single-shot quick research system prompt
"""

from .briefings import (
    COMPANY_BRIEFING_PROMPT,
    NEWS_BRIEFING_PROMPT,
    SOCIAL_MEDIA_BRIEFING_PROMPT,
    BRIEFING_ANALYSIS_INSTRUCTION,
)

from .editor import (
    EDITOR_SYSTEM_MESSAGE,
    COMPILE_CONTENT_PROMPT,
    CONTENT_SWEEP_SYSTEM_MESSAGE,
    CONTENT_SWEEP_PROMPT,
)

from .queries import (
    QUERY_FORMAT_GUIDELINES,
    RESEARCHER_SYSTEM_MESSAGE,
    COMPANY_ANALYZER_QUERY_PROMPT,
    NEWS_SCANNER_QUERY_PROMPT,
    SOCIAL_MEDIA_ANALYZER_QUERY_PROMPT,
)

from .email_outreach import EMAIL_GENERATION_SYSTEM_PROMPT
from .quick_research import QUICK_RESEARCH_SYSTEM_PROMPT

__all__ = [
    # Briefings
    "COMPANY_BRIEFING_PROMPT",
    "NEWS_BRIEFING_PROMPT",
    "SOCIAL_MEDIA_BRIEFING_PROMPT",
    "BRIEFING_ANALYSIS_INSTRUCTION",
    # Editor
    "EDITOR_SYSTEM_MESSAGE",
    "COMPILE_CONTENT_PROMPT",
    "CONTENT_SWEEP_SYSTEM_MESSAGE",
    "CONTENT_SWEEP_PROMPT",
    # Queries
    "QUERY_FORMAT_GUIDELINES",
    "RESEARCHER_SYSTEM_MESSAGE",
    "COMPANY_ANALYZER_QUERY_PROMPT",
    "NEWS_SCANNER_QUERY_PROMPT",
    "SOCIAL_MEDIA_ANALYZER_QUERY_PROMPT",
    # Standalone
    "EMAIL_GENERATION_SYSTEM_PROMPT",
    "QUICK_RESEARCH_SYSTEM_PROMPT",
]
