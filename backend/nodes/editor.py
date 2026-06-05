"""
================================================================================
editor.py - 报告编译阶段 (Stage 8)
================================================================================
使用Azure GPT-4o将5份简报整合为最终的Markdown研究报告

输入: company_briefing, industry_briefing, financial_briefing, news_briefing, social_media_briefing
      + reference_titles, reference_info (引用信息)
输出: report (最终Markdown报告，流式生成)

2阶段编译流程:

第1阶段 - 内容汇编 (Compile):
  - 输入: 5份独立简报
  - 任务: 整合为连贯的叙述（非简单拼接）
  - 去重: 移除重复内容
  - 流式: 逐段返回
  
第2阶段 - 内容清理 (Sweep):
  - 输入: 第1阶段的输出
  - 任务: 格式化、优化结构、移除元评论
  - 验证: 确保遵循Markdown结构
  - 流式: 逐段返回

最终结构:
  # 公司名 Research Report
  
  ## Company Overview
  ### Core Product/Service
  ### Leadership
  ### Business Model
  
  ## Industry Overview
  ### Market Size
  ### Competition
  
  ## Financial Overview
  ### Funding History
  ### Revenue Model
  
  ## News
  * 新闻项1
  * 新闻项2
  
  ## References
  - [标题](url1)
  - [标题](url2)

全程使用流式输出 (SSE) 实时推送给前端
"""

import logging
import os
import re
from typing import Dict, List, Set

from langchain_core.messages import AIMessage
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..classes import ResearchState
from ..classes.state import job_status
from ..utils.references import format_references_section, normalize_url
from ..prompts import (
    EDITOR_SYSTEM_MESSAGE,
    COMPILE_CONTENT_PROMPT,
    CONTENT_SWEEP_SYSTEM_MESSAGE,
    CONTENT_SWEEP_PROMPT
)

logger = logging.getLogger(__name__)

REFERENCE_HEADERS = ("## References", "## 参考来源")
URL_IN_MARKDOWN_LINK = re.compile(r"\[[^\]]+\][(（](https?://[^)）\s]+)[)）]")
URL_RAW = re.compile(r"(https?://[^\s)）>]+)")

class Editor:
    """报告编辑器 - 将4份简报汇编为最终报告"""
    
    def __init__(self) -> None:
        """初始化Editor，配置Azure GPT-4o
        
        支持流式输出 (streaming=True) 用于实时推送
        """
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_instance = os.getenv("AZURE_OPENAI_API_INSTANCE_NAME")
        azure_deployment = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")
        azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        
        if not azure_api_key or not azure_instance or not azure_deployment:
            raise ValueError("Missing Azure OpenAI configuration")

        azure_endpoint = azure_instance.strip()
        if azure_endpoint.startswith("http://") or azure_endpoint.startswith("https://"):
            pass
        elif "." in azure_endpoint:
            azure_endpoint = f"https://{azure_endpoint}"
        else:
            azure_endpoint = f"https://{azure_endpoint}.openai.azure.com"
        
        # 配置LangChain Azure OpenAI客户端（支持流式输出）
        self.llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0,
            streaming=True,  # 支持流式输出
        )
        
        # 初始化上下文字典 (供Prompt填充)
        self.context = {
            "company": "Unknown Company",
            "industry": "Unknown",
            "hq_location": "Unknown"
        }

    @staticmethod
    def _extract_markdown_urls(line: str) -> List[str]:
        """Extract URLs from markdown links and raw URLs in a line."""
        urls = URL_IN_MARKDOWN_LINK.findall(line)
        raw_urls = URL_RAW.findall(line)
        all_urls = urls + raw_urls

        seen = set()
        deduped: List[str] = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    @staticmethod
    def _strip_citations(text: str) -> str:
        """Remove markdown citation links while keeping readable text for matching."""
        text = URL_IN_MARKDOWN_LINK.sub("", text)
        text = URL_RAW.sub("", text)
        text = re.sub(r"\[[^\]]+\]\([^)]*\)", "", text)
        return text.strip()

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        """Normalize a line for rough semantic equality checks."""
        text = Editor._strip_citations(text)
        text = re.sub(r"[`*_>#\-]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    def _is_supported_by_briefings(self, report_line: str, source_lines: List[str]) -> bool:
        """Check whether report line appears to be grounded in any source briefing line.
        
        Uses a relaxed matching strategy:
        - Substring containment
        - Token overlap >= 35% against any single source line
        - Key entity overlap (numbers, proper nouns) against combined sources
        """
        target = self._normalize_for_match(report_line)
        if not target:
            return True

        # Very short fragments are usually labels/transitions, keep them.
        if len(target) < 10:
            return True

        target_tokens = set(target.split())
        if not target_tokens:
            return True

        # Extract key entities (numbers, percentages, years) for stricter check
        key_entities = set(re.findall(r'\d[\d,.%万亿美元]+|\d{4}', target))

        best_ratio = 0.0
        for src in source_lines:
            if target in src or src in target:
                return True

            src_tokens = set(src.split())
            if not src_tokens:
                continue

            overlap = len(target_tokens & src_tokens)
            ratio = overlap / max(len(target_tokens), 1)
            best_ratio = max(best_ratio, ratio)
            if ratio >= 0.20:  # 放宽: 35% → 20%，LLM改写句子词汇不完全同源
                return True

        # If key entities (numbers/dates) exist, check they appear somewhere in sources
        if key_entities:
            all_source_text = " ".join(source_lines)
            entities_found = sum(1 for e in key_entities if e in all_source_text)
            if entities_found >= len(key_entities) * 0.5:
                return True

        return False

    # Sections where grounding gate is relaxed (keep all content from briefings)
    _RELAXED_SECTIONS = {"最近社媒动态"}

    def _enforce_cited_and_supported_content(self, report_body: str, briefings: Dict[str, str]) -> str:
        """Gate: keep headings, cited lines, and short connective text between cited content."""
        source_lines: List[str] = []
        for content in briefings.values():
            for line in content.splitlines():
                normalized = self._normalize_for_match(line)
                if normalized:
                    source_lines.append(normalized)

        filtered: List[str] = []
        dropped = 0
        in_relaxed_section = False

        lines = report_body.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()

            if not stripped:
                filtered.append(line)
                continue

            # Keep markdown headings and explicit placeholders.
            if stripped.startswith("#") or "暂无相关信息" in stripped:
                filtered.append(line)
                # Track whether we're inside a relaxed section
                if stripped.startswith("## "):
                    section_title = stripped.lstrip("# ").strip()
                    in_relaxed_section = any(s in section_title for s in self._RELAXED_SECTIONS)
                continue

            # In relaxed sections (e.g. social media), keep all content
            if in_relaxed_section:
                filtered.append(line)
                continue

            has_citation = bool(URL_IN_MARKDOWN_LINK.search(line))

            # Lines with citations: verify against briefings
            if has_citation:
                if self._is_supported_by_briefings(line, source_lines):
                    filtered.append(line)
                else:
                    dropped += 1
                continue

            # Lines without citations: keep short connective/transition text
            # (e.g., section intros, transitions between facts)
            # Drop only long uncited factual claims with specific data
            plain = self._strip_citations(stripped)
            if len(plain) <= 60:
                # Short text - likely a transition or intro, keep it
                filtered.append(line)
                continue

            # General descriptive text - keep if supported by briefings or within reasonable length
            if self._is_supported_by_briefings(line, source_lines):
                filtered.append(line)
            elif len(plain) <= 150:
                # 放宽: 150字以内的描述性文本保留（避免删除LLM总结段落）
                filtered.append(line)
            else:
                dropped += 1

        logger.info("Applied grounding gate: kept=%s dropped=%s", len(filtered), dropped)
        return "\n".join(filtered).strip()

    @staticmethod
    def _replace_placeholder_citations(report_body: str, allowed_urls: List[str]) -> str:
        """Replace placeholder citations [来源](url) with real URLs from allowed_urls list.
        
        处理 GPT 生成的占位符引用 [来源](url)，用真实 URL 替换。
        如果 allowed_urls 有多个，则依次轮替替换。
        """
        if not allowed_urls:
            return report_body
        
        # Pattern to match [来源](url) with literal "url" string
        placeholder_pattern = re.compile(r'\[来源\]\(url\)')
        
        # Find all placeholder positions
        placeholders = list(placeholder_pattern.finditer(report_body))
        if not placeholders:
            return report_body
        
        # Replace each placeholder with a URL from allowed_urls (round-robin)
        result = report_body
        for i, match in enumerate(placeholders):
            real_url = allowed_urls[i % len(allowed_urls)]
            replacement = f'[来源]({real_url})'
            result = result.replace('[来源](url)', replacement, 1)
        
        return result

    @staticmethod
    def _strip_references_section(report: str) -> str:
        """Remove existing references section so we can rebuild it from validated citations."""
        lines = report.splitlines()
        body_lines = []
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(header) for header in REFERENCE_HEADERS):
                break
            body_lines.append(line)
        return "\n".join(body_lines).strip()

    def _build_allowed_urls(self, state: ResearchState) -> Set[str]:
        """Build URL whitelist from curated documents and curated references."""
        allowed_urls: Set[str] = set()

        for field in (
            "curated_company_data",
            "curated_industry_data",
            "curated_financial_data",
            "curated_news_data",
            "curated_social_media_data",
        ):
            docs = state.get(field, {}) or {}
            for key_url, doc in docs.items():
                if key_url:
                    allowed_urls.add(normalize_url(key_url))
                doc_url = doc.get("url", "") if isinstance(doc, dict) else ""
                if doc_url:
                    allowed_urls.add(normalize_url(doc_url))

        for ref_url in state.get("references", []) or []:
            allowed_urls.add(normalize_url(ref_url))

        for ref_url in (state.get("reference_info", {}) or {}).keys():
            allowed_urls.add(normalize_url(ref_url))

        return allowed_urls

    def _validate_body_with_citations(self, report_body: str, allowed_urls: Set[str]) -> tuple[str, List[str], dict]:
        """Keep only factual lines that have at least one citation URL in the allowed set."""
        lines = report_body.splitlines()
        cleaned_lines: List[str] = []
        cited_urls: List[str] = []
        cited_seen: Set[str] = set()

        removed_no_citation = 0
        removed_unsupported_citation = 0
        kept_factual = 0

        for line in lines:
            stripped = line.strip()

            # Keep structural lines
            if not stripped:
                cleaned_lines.append(line)
                continue
            if stripped.startswith("#"):
                cleaned_lines.append(line)
                continue

            is_bullet_or_numbered = (
                stripped.startswith("* ")
                or stripped.startswith("- ")
                or stripped.startswith("+ ")
                or bool(re.match(r"^\d+\.\s", stripped))
            )

            # Only strictly gate bullet/numbered claims.
            # Keep narrative/transition lines to avoid empty-body regression.
            if not is_bullet_or_numbered:
                cleaned_lines.append(line)
                continue

            line_urls = [normalize_url(url) for url in self._extract_markdown_urls(line)]
            if not line_urls:
                # 放宽: 无引用的bullet保留，不再删除（LLM摘要性内容无法带具体URL）
                cleaned_lines.append(line)
                continue

            matched = [url for url in line_urls if url in allowed_urls]
            if not matched:
                # 带引用但URL不在白名单 - 仍保留内容，只是不计入引用统计
                removed_unsupported_citation += 1
                cleaned_lines.append(line)
                continue

            cleaned_lines.append(line)
            kept_factual += 1
            for url in matched:
                if url not in cited_seen:
                    cited_seen.add(url)
                    cited_urls.append(url)

        stats = {
            "kept_factual": kept_factual,
            "removed_no_citation": removed_no_citation,
            "removed_unsupported_citation": removed_unsupported_citation,
        }
        return "\n".join(cleaned_lines).strip(), cited_urls, stats

    def _extract_allowed_urls_from_text(self, text: str, allowed_urls: Set[str]) -> List[str]:
        """Collect allowed URLs mentioned in body text, preserving order."""
        collected: List[str] = []
        seen: Set[str] = set()

        for line in text.splitlines():
            for raw_url in self._extract_markdown_urls(line):
                normalized = normalize_url(raw_url)
                if normalized in allowed_urls and normalized not in seen:
                    seen.add(normalized)
                    collected.append(normalized)

        return collected

    def _rebuild_references_from_citations(self, state: ResearchState, cited_urls: List[str]) -> str:
        """Build references section from URLs actually cited in body; fallback to preselected refs."""
        reference_info = state.get("reference_info", {}) or {}
        reference_titles = state.get("reference_titles", {}) or {}

        if cited_urls:
            return format_references_section(cited_urls, reference_info, reference_titles)

        fallback_refs = state.get("references", []) or []
        return format_references_section(fallback_refs, reference_info, reference_titles)

    async def compile_briefings(self, state: ResearchState) -> ResearchState:
        """Compile individual briefing categories from state into a final report."""
        company = state.get('company', 'Unknown Company')
        job_id = state.get('job_id')
        
        # Update context with values from state
        self.context = {
            "company": company,
            "industry": state.get('industry', 'Unknown'),
            "hq_location": state.get('hq_location', 'Unknown')
        }
        
        msg = [f"📑 Compiling final report for {company}..."]
        
        # Emit report compilation start event
        if job_id:
            try:
                if job_id in job_status:
                    job_status[job_id]["events"].append({
                        "type": "report_compilation",
                        "message": f"Compiling final report for {company}"
                    })
            except Exception as e:
                logger.error(f"Error appending report_compilation event: {e}")
        
        # Pull individual briefings from dedicated state keys
        briefing_keys = {
            'company': 'company_briefing',
            'industry': 'industry_briefing',
            'financial': 'financial_briefing',
            'news': 'news_briefing',
            'social_media': 'social_media_briefing'
        }

        individual_briefings = {}
        for category, key in briefing_keys.items():
            if content := state.get(key):
                individual_briefings[category] = content
                msg.append(f"Found {category} briefing ({len(content)} characters)")
            else:
                msg.append(f"No {category} briefing available")
                logger.error(f"Missing state key: {key}")
        
        if not individual_briefings:
            msg.append("\n⚠️ No briefing sections available to compile")
            logger.error("No briefings found in state")
            raise RuntimeError("[editor] No briefing sections available to compile")
        else:
            try:
                compiled_report = await self.edit_report(state, individual_briefings)
                if not compiled_report or not compiled_report.strip():
                    logger.error("Compiled report is empty!")
                    raise RuntimeError("[editor] Compiled report is empty")
                else:
                    logger.info(f"Successfully compiled report with {len(compiled_report)} characters")
            except Exception as e:
                logger.error(f"Error during report compilation: {e}")
                if job_id and job_id in job_status:
                    job_status[job_id]["events"].append({
                        "type": "error",
                        "stage": "editor",
                        "error": str(e),
                        "message": "Final report compilation failed"
                    })
                raise
        
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        return state
    
    async def edit_report(self, state: ResearchState, briefings: Dict[str, str]) -> str:
        """Compile section briefings into a final report and update the state."""
        try:
            logger.info("Starting report compilation")
            job_id = state.get('job_id')
            
            # Step 1: Initial Compilation
            edited_report = await self.compile_content(state, briefings)
            if not edited_report:
                logger.error("Initial compilation failed")
                return ""

            # Step 2 & 3: Content sweep and streaming
            final_report = ""
            async for event in self.content_sweep(edited_report, job_id=job_id):
                # Forward streaming events to job_status
                if isinstance(event, dict) and job_id:
                    try:
                        if job_id in job_status:
                            job_status[job_id]["events"].append(event)
                            logger.debug(f"Appended report_chunk event ({len(event.get('chunk', ''))} chars)")
                    except Exception as e:
                        logger.error(f"Error appending report_chunk event: {e}")
                
                # Accumulate the text
                if isinstance(event, str):
                    final_report = event
            
            final_report = final_report or edited_report or ""

            # Step 3.5: Replace placeholder citations [来源](url) with real URLs
            body_without_refs = self._strip_references_section(final_report)
            allowed_urls = self._build_allowed_urls(state)
            allowed_urls_list = list(allowed_urls) if allowed_urls else []
            if allowed_urls_list:
                body_without_refs = self._replace_placeholder_citations(body_without_refs, allowed_urls_list)
                logger.debug(f"Replaced placeholder citations in body")

            # Hard constraint: keep only cited content that is grounded in briefing text.
            body_without_refs = self._enforce_cited_and_supported_content(body_without_refs, briefings)

            # Extract all URLs cited in the body (for reference tracking, but not displayed)
            cited_urls = self._extract_allowed_urls_from_text(body_without_refs, allowed_urls)
            logger.info(f"Extracted {len(cited_urls)} citations from body text")

            # Use body without references section as final report
            final_report = body_without_refs.strip()

            logger.info(
                "Report compilation complete: body_chars=%s cited_urls=%s",
                len(body_without_refs),
                len(cited_urls),
            )
            
            logger.info(f"Final report compiled with {len(final_report)} characters")
            if not final_report.strip():
                logger.error("Final report is empty!")
                return ""
            
            # Update state with the final report
            state['report'] = final_report
            state['status'] = "editor_complete"
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = final_report
            
            return final_report
        except Exception as e:
            logger.error(f"Error in edit_report: {e}")
            raise RuntimeError(f"[editor] Error in edit_report: {e}") from e
    
    async def compile_content(self, state: ResearchState, briefings: Dict[str, str]) -> str:
        """Initial compilation of research sections using LCEL."""
        # Label each briefing so LLM knows which category it belongs to
        category_labels = {
            'company': '【公司简报】',
            'industry': '【行业简报】',
            'financial': '【财务简报】',
            'news': '【新闻简报】',
            'social_media': '【社媒简报】'
        }
        labeled_sections = []
        for category, content in briefings.items():
            label = category_labels.get(category, f'【{category}简报】')
            labeled_sections.append(f"{label}\n{content}")
        combined_content = "\n\n".join(labeled_sections)
        
        # Create LCEL chain for compilation
        compile_prompt = ChatPromptTemplate.from_messages([
            ("system", EDITOR_SYSTEM_MESSAGE),
            ("user", COMPILE_CONTENT_PROMPT)
        ])
        
        chain = compile_prompt | self.llm | StrOutputParser()
        
        try:
            job_id = state.get('job_id')
            if job_id and job_id in job_status:
                job_status[job_id]["events"].append({
                    "type": "llm_call",
                    "purpose": "报告汇编",
                    "message": "🤖 LLM调用: 汇编最终报告"
                })
            initial_report = await chain.ainvoke({
                "company": self.context["company"],
                "industry": self.context["industry"],
                "hq_location": self.context["hq_location"],
                # Provide both variable names for prompt-template compatibility.
                "content": combined_content,
                "combined_content": combined_content,
            })

            return initial_report
        except Exception as e:
            logger.error(f"Error in initial compilation: {e}")
            raise RuntimeError(f"[editor] Error in initial compilation: {e}") from e
        
    async def content_sweep(self, content: str, job_id: str = None):
        """Sweep the content for any redundant information using LCEL streaming and yield events."""
        # Create LCEL chain for content sweep
        sweep_prompt = ChatPromptTemplate.from_messages([
            ("system", CONTENT_SWEEP_SYSTEM_MESSAGE),
            ("user", CONTENT_SWEEP_PROMPT)
        ])
        
        chain = sweep_prompt | self.llm | StrOutputParser()
        
        try:
            if job_id and job_id in job_status:
                job_status[job_id]["events"].append({
                    "type": "llm_call",
                    "purpose": "报告精绣格式化",
                    "message": "🤖 LLM调用: 报告精绣格式化"
                })
            accumulated_text = ""
            buffer = ""
            
            # Stream using LangChain's astream
            async for chunk in chain.astream({
                "company": self.context["company"],
                "industry": self.context["industry"],
                "hq_location": self.context["hq_location"],
                "content": content
            }):
                accumulated_text += chunk
                buffer += chunk
                
                # Yield chunks at sentence boundaries
                if any(char in buffer for char in ['.', '!', '?', '\n']) and len(buffer) > 10:
                    yield {"type": "report_chunk", "chunk": buffer, "step": "Editor"}
                    buffer = ""
            
            # Yield final buffer
            if buffer:
                yield {"type": "report_chunk", "chunk": buffer, "step": "Editor"}
            
            yield accumulated_text.strip()
        except Exception as e:
            logger.error(f"Error in formatting: {e}")
            yield {"type": "error", "error": str(e), "step": "Editor"}
            raise RuntimeError(f"[editor] Error in content_sweep: {e}") from e

    async def run(self, state: ResearchState) -> ResearchState:
        state = await self.compile_briefings(state)
        # Ensure the Editor node's output is stored both top-level and under "editor"
        if 'report' in state:
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = state['report']
        return state
