"""
================================================================================
curator.py - 内容筛选阶段 (Stage 5)
================================================================================
对收集的文档进行评分、去重、过滤，保留高质量的相关文档

输入: company_data, industry_data, financial_data, news_data (~80个文档)
输出: curated_*_data (~55个文档), reference_titles, reference_info

筛选规则:
  1. URL规范化去重: 统一格式，移除query/fragment
  2. 低价值URL过滤: 登录页、搜索结果、社交媒体等
  3. 评分筛选: Tavily score ≥ 0.4 或 官网来源
  4. 垃圾内容检测: 过滤Dictionary.com定义页等
  5. 行业相关性检查: industry类别需验证内容相关性
  6. Top 30限制: 每个类别最多保留30个文档
  7. 引用收集: 保存所有URL的标题和元信息

效果: 73文档 → 55文档 (75%通过率)
"""

import logging
import re
from typing import Dict
from urllib.parse import urljoin, urlparse

from langchain_core.messages import AIMessage

from ..classes import ResearchState
from ..classes.state import job_status
from ..utils.references import process_references_from_search_results
from ..utils.url_filters import is_low_value_url

logger = logging.getLogger(__name__)

# Generic words that should not be used as company-identity tokens
GENERIC_COMPANY_TOKENS = {
    "company", "co", "corp", "corporation", "inc", "ltd", "llc", "group", "global",
    "official", "store", "shop", "brand", "business",
    "office", "furniture", "market", "markets", "industry", "industries",
}


def _is_industry_relevant(doc: dict, company: str, industry: str, company_url: str | None) -> bool:
    """检测文档是否与行业/公司相关
    
    用途: 对industry_data进行额外的内容相关性检查
         过滤明显无关的页面（如Dictionary.com的定义页）
    
    逻辑:
      1. 官网域名优先: 官网所有页面都保留
      2. 关键词匹配: 公司名 + 行业词出现在标题/内容
      3. 业务关键词: market, industry, revenue, growth等
      4. 返回True: 保留, False: 舍弃
    """
    url = doc.get('url', '').lower()
    title = (doc.get('title', '') or '').lower()
    content = (doc.get('raw_content', '') or doc.get('content', '') or '')[:3000].lower()

    # Always keep company domain pages
    if company_url:
        try:
            company_domain = urlparse(company_url).netloc.replace('www.', '')
            doc_domain = urlparse(url).netloc.replace('www.', '')
            if company_domain and company_domain in doc_domain:
                return True
        except Exception:
            pass

    # Build relevance tokens from company name + industry
    tokens = []
    company_lower = company.lower()
    tokens.append(company_lower)
    words = [w for w in re.split(r'[\s\-&+.,]+', company_lower) if len(w) > 2]
    tokens.extend(words)
    
    # Add industry tokens
    if industry:
        industry_lower = industry.lower()
        tokens.append(industry_lower)
        industry_words = [w for w in re.split(r'[\s\-&+.,]+', industry_lower) if len(w) > 3]
        tokens.extend(industry_words)

    # Check if any relevant token appears in title or content
    text = title + ' ' + content
    for token in tokens:
        if token in text:
            return True

    # Also check for common industry-related keywords that indicate market/business content
    # 业务关键词检查: 如果标题包含industry/market等，即使未提及公司名也认为相关
    business_keywords = ['market', 'industry', 'revenue', 'growth', 'competitor', 'trend', 'forecast',
                         'furniture', 'office', 'ergonomic', 'workspace', 'commercial', 'b2b',
                         'supplier', 'manufacturer', 'retail', 'wholesale', 'distribution']
    for kw in business_keywords:
        if kw in title:
            return True

    return False


def _is_company_relevant(doc: dict, company: str, company_url: str | None) -> bool:
    """检测文档是否与目标公司直接相关
    
    用途: 对company_data和financial_data进行严格相关性过滤
    
    逻辑:
      1. 官网页面: 直接保留 (source == 'company_website')
      2. 官网域名: 来自公司官网域名的所有页面保留
      3. 公司名匹配: 全名/部分词/无空格版本匹配标题/URL/内容
      4. 短名特殊处理: 长度≤4的token需要词边界匹配，避免误匹配（如 bol 匹配到 boliden）
      4. 返回True: 保留, False: 舍弃（不相关）
    """
    url = doc.get('url', '')
    title = (doc.get('title', '') or '').lower()
    content = (doc.get('raw_content', '') or doc.get('content', '') or '')[:2000].lower()

    # Always keep company website pages
    if doc.get('source') == 'company_website':
        return True

    # If we have the company's URL domain, keep pages from that domain
    if company_url:
        try:
            company_domain = urlparse(company_url).netloc.replace('www.', '')
            doc_domain = urlparse(url).netloc.replace('www.', '')
            if company_domain and company_domain in doc_domain:
                return True
        except Exception:
            pass

    # Build search tokens from company name (drop generic words to avoid false positives)
    company_lower = company.lower()
    company_tokens = []

    # Full company phrase is always a strong signal
    if company_lower:
        company_tokens.append(company_lower)

    # Individual distinctive words
    words = [w for w in re.split(r'[\s\-&+.,]+', company_lower) if len(w) > 2]
    distinct_words = [w for w in words if w not in GENERIC_COMPANY_TOKENS]
    company_tokens.extend(distinct_words)

    # No-space slug for URL/identifier matching
    company_slug = re.sub(r'[\s\-&+.,]+', '', company_lower)
    if len(company_slug) > 3:
        company_tokens.append(company_slug)

    # Check stronger signals first
    url_lower = url.lower()
    title_url_text = f"{title} {url_lower}"

    # Full company phrase or slug appearing anywhere is strong enough
    if company_lower and (company_lower in title_url_text or company_lower in content):
        return True
    if company_slug and len(company_slug) > 4 and (company_slug in title_url_text or company_slug in content):
        return True

    # For short company names (<=4 chars), use word-boundary regex to avoid substring matches
    # e.g. "bol" should NOT match "boliden", "bolt", "bolttech"
    def _word_boundary_match(token: str, text: str) -> bool:
        if len(token) <= 4:
            pattern = r'\b' + re.escape(token) + r'\b'
            return bool(re.search(pattern, text))
        return token in text

    # Distinctive tokens appearing in title or URL are acceptable
    distinctive_tokens = [t for t in company_tokens if t not in {company_lower, company_slug}]
    for token in distinctive_tokens:
        if _word_boundary_match(token, title_url_text):
            return True

    # Content-only match requires at least two distinctive tokens to avoid generic matches
    if distinctive_tokens:
        content_hits = sum(1 for token in distinctive_tokens if _word_boundary_match(token, content))
        if content_hits >= 2:
            return True

    # Legacy fallback: never use generic words alone
    for token in company_tokens:
        if token in GENERIC_COMPANY_TOKENS:
            continue
        if _word_boundary_match(token, title_url_text):
            return True

    return False

class Curator:
    """文档筛选器 - 基于相关性评分筛选高质量文档"""
    
    def __init__(self) -> None:
        """初始化Curator
        
        relevance_threshold: Tavily评分阈值 (≥0.4保留)
        """
        self.relevance_threshold = 0.4
        logger.info(f"Curator initialized with relevance threshold: {self.relevance_threshold}")

    def evaluate_documents(self, docs: list, context: Dict[str, str], category: str = "") -> list:
        """评估文档的相关性
        
        核心逻辑:
          1. 低价值URL过滤: 登录页、搜索结果等直接跳过
          2. 评分检查: Tavily score ≥ 0.4 或 官网来源保留
          3. 官网加分: source='company_website'的文档给0.5基础分
          4. 相关性验证: 严格类别(company/financial/news)需要验证公司提及
          5. 排序: 按score降序排列
        
        Args:
            docs: 文档列表
            context: {company, company_url, industry, ...}
            category: 类别 (company/financial/news/industry) - 决定严格程度
            
        Returns:
            过滤后的文档列表 (已排序)
        """
        if not docs:
            return []

        company = context.get('company', '')
        company_url = context.get('company_url')
        industry = context.get('industry', '')
        logger.info(f"Evaluating {len(docs)} documents for relevance to '{company}' (category={category})")
        
        # For industry data, we allow general market/industry reports
        # For company/financial/news data, we strictly require company mention
        strict_filter = category in ('company', 'financial', 'news')
        
        evaluated_docs = []
        skipped_irrelevant = 0
        try:
            # Evaluate each document using Tavily's score
            for doc in docs:
                try:
                    if is_low_value_url(doc.get('url', '')):
                        logger.info(f"Skipping low-value URL during curation: {doc.get('url', '')}")
                        continue

                    # Ensure score is a valid float
                    tavily_score = float(doc.get('score', 0))  # Default to 0 if no score
                    
                    # Always keep company website data regardless of score (first-party information)
                    is_company_website = doc.get('source') == 'company_website'
                    
                    # Give company website pages a base score so they don't sink to bottom in sorting
                    if is_company_website and tavily_score == 0:
                        tavily_score = 0.5  # Base score for first-party data
                        doc['score'] = tavily_score
                    
                    # Keep documents with good Tavily score or company website data
                    if tavily_score >= self.relevance_threshold or is_company_website:
                        # ADDITIONAL CHECK: verify the document is actually about the target company
                        # For company/financial/news categories, strictly require company mention
                        # For industry category, allow general market reports but filter obvious garbage
                        if not is_company_website and strict_filter and not _is_company_relevant(doc, company, company_url):
                            skipped_irrelevant += 1
                            logger.info(f"Document REJECTED (not about {company}) score {tavily_score:.4f}: '{doc.get('title', 'No title')}' URL={doc.get('url', '')}")
                            continue
                        
                        # For industry category: filter pages that are clearly unrelated to the industry
                        if not is_company_website and not strict_filter and category == 'industry':
                            if not _is_industry_relevant(doc, company, industry, company_url):
                                skipped_irrelevant += 1
                                logger.info(f"Document REJECTED (not industry relevant) score {tavily_score:.4f}: '{doc.get('title', 'No title')}' URL={doc.get('url', '')}")
                                continue

                        reason = "company website" if is_company_website else f"score {tavily_score:.4f}"
                        logger.info(f"Document kept ({reason}) for '{doc.get('title', 'No title')}')")
                        
                        evaluated_doc = {
                            **doc,
                            "evaluation": {
                                "overall_score": tavily_score,  # Store as float
                                "query": doc.get('query', '')
                            }
                        }
                        evaluated_docs.append(evaluated_doc)
                    else:
                        logger.info(f"Document below threshold with score {tavily_score:.4f} for '{doc.get('title', 'No title')}'")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing score for document: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error during document evaluation: {e}")
            return []

        if skipped_irrelevant > 0:
            logger.info(f"⚠️ Filtered out {skipped_irrelevant} documents not relevant to '{company}'")

        # Sort evaluated docs by score before returning
        evaluated_docs.sort(key=lambda x: float(x['evaluation']['overall_score']), reverse=True)
        logger.info(f"Returning {len(evaluated_docs)} evaluated documents")
        
        return evaluated_docs

    async def curate_data(self, state: ResearchState) -> ResearchState:
        """Curate all collected data based on Tavily scores."""
        company = state.get('company', 'Unknown Company')
        job_id = state.get('job_id')
        logger.info(f"Starting curation for company: {company}, job_id={job_id}")

        industry = state.get('industry', 'Unknown')
        context = {
            "company": company,
            "industry": industry,
            "hq_location": state.get('hq_location', 'Unknown'),
            "company_url": state.get('company_url')
        }

        msg = [f"🔍 Curating research data for {company}"]
        
        data_types = {
            'financial_data': ('💰 Financial', 'financial'),
            'news_data': ('📰 News', 'news'),
            'industry_data': ('🏭 Industry', 'industry'),
            'company_data': ('🏢 Company', 'company'),
            'social_media_data': ('📱 Social Media', 'social_media')
        }

        # Process each data type
        for data_field, (emoji, doc_type) in data_types.items():
            data = state.get(data_field, {})
            if not data:
                continue

            # Filter and normalize URLs
            unique_docs = {}
            for url, doc in data.items():
                try:
                    parsed = urlparse(url)
                    if not parsed.scheme:
                        url = urljoin('https://', url)
                    clean_url = parsed._replace(query='', fragment='').geturl()
                    if clean_url not in unique_docs:
                        doc['url'] = clean_url
                        doc['doc_type'] = doc_type
                        unique_docs[clean_url] = doc
                except Exception:
                    continue

            docs = list(unique_docs.values())
            msg.append(f"\n{emoji}: Found {len(docs)} documents")
            
            evaluated_docs = self.evaluate_documents(docs, context, category=doc_type)
            
            # Emit curation event with total count
            if job_id:
                try:
                    if job_id in job_status:
                        job_status[job_id]["events"].append({
                            "type": "curation",
                            "category": doc_type,
                            "total": len(evaluated_docs) if evaluated_docs else 0,
                            "message": f"Curating {doc_type} documents"
                        })
                except Exception as e:
                    logger.error(f"Error appending curation event: {e}")

            if not evaluated_docs:
                msg.append("  ⚠️ No relevant documents found")
                # Emit curation_details with all docs rejected
                if job_id and job_id in job_status:
                    all_urls_info = [
                        {"url": doc.get('url', ''), "title": doc.get('title', ''), "score": float(doc.get('score', 0)), "kept": False}
                        for doc in docs
                    ]
                    job_status[job_id]["events"].append({
                        "type": "curation_details",
                        "category": doc_type,
                        "all_urls": all_urls_info,
                        "kept_count": 0,
                        "total_count": len(docs)
                    })
                continue

            # Filter and sort by Tavily score
            relevant_docs = {doc['url']: doc for doc in evaluated_docs}
            sorted_items = sorted(relevant_docs.items(), key=lambda item: item[1]['evaluation']['overall_score'], reverse=True)
            
            # Limit to top 30 documents per category
            if len(sorted_items) > 30:
                sorted_items = sorted_items[:30]
            relevant_docs = dict(sorted_items)

            if relevant_docs:
                msg.append(f"  ✓ Kept {len(relevant_docs)} relevant documents")
                logger.info(f"Kept {len(relevant_docs)} documents for {doc_type} with scores above threshold")
            else:
                msg.append("  ⚠️ No documents met relevance threshold")
                logger.info(f"No documents met relevance threshold for {doc_type}")

            # Emit curation_details event with all URLs and their kept/rejected status
            if job_id and job_id in job_status:
                kept_urls = set(relevant_docs.keys())
                all_urls_info = [
                    {
                        "url": doc.get('url', ''),
                        "title": doc.get('title', ''),
                        "score": float(doc.get('score', 0)),
                        "kept": doc.get('url', '') in kept_urls
                    }
                    for doc in docs
                ]
                # Sort: kept first (by score desc), then rejected (by score desc)
                all_urls_info.sort(key=lambda x: (-int(x['kept']), -x['score']))
                job_status[job_id]["events"].append({
                    "type": "curation_details",
                    "category": doc_type,
                    "all_urls": all_urls_info,
                    "kept_count": len(relevant_docs),
                    "total_count": len(docs)
                })

            # Store curated documents in state
            state[f'curated_{data_field}'] = relevant_docs
            
        # Process references using the references module
        top_reference_urls, reference_titles, reference_info = process_references_from_search_results(state)
        logger.info(f"Selected top {len(top_reference_urls)} references for the report")
        
        # Update state with references and their titles
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        state['references'] = top_reference_urls
        state['reference_titles'] = reference_titles
        state['reference_info'] = reference_info

        return state

    async def run(self, state: ResearchState) -> ResearchState:
        return await self.curate_data(state)
