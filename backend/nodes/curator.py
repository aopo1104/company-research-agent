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


def _is_industry_relevant(doc: dict, company: str, industry: str, company_url: str | None) -> bool:
    """
    For industry category: check if a document is at least related to the industry/company.
    Filters out obviously unrelated pages (e.g., dictionary definitions, tech tutorials).
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
    business_keywords = ['market', 'industry', 'revenue', 'growth', 'competitor', 'trend', 'forecast',
                         'furniture', 'office', 'ergonomic', 'workspace', 'commercial', 'b2b',
                         'supplier', 'manufacturer', 'retail', 'wholesale', 'distribution']
    for kw in business_keywords:
        if kw in title:
            return True

    return False


def _is_company_relevant(doc: dict, company: str, company_url: str | None) -> bool:
    """
    Check if a document is directly relevant to the target company.
    Returns True if the doc likely pertains to the company, False if it's clearly unrelated.
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

    # Build search tokens from company name (handle multi-word names)
    company_lower = company.lower()
    # Create variants: full name, individual significant words (>2 chars), abbreviation
    company_tokens = [company_lower]
    words = [w for w in re.split(r'[\s\-&+.,]+', company_lower) if len(w) > 2]
    company_tokens.extend(words)
    # Also create a no-space version for URL matching
    company_slug = re.sub(r'[\s\-&+.,]+', '', company_lower)
    if len(company_slug) > 3:
        company_tokens.append(company_slug)

    # Check if any company token appears in title, URL, or content
    url_lower = url.lower()
    for token in company_tokens:
        if token in title or token in url_lower or token in content:
            return True

    return False

class Curator:
    def __init__(self) -> None:
        self.relevance_threshold = 0.4
        logger.info(f"Curator initialized with relevance threshold: {self.relevance_threshold}")

    def evaluate_documents(self, docs: list, context: Dict[str, str], category: str = "") -> list:
        """Evaluate documents based on Tavily's scoring and company relevance."""
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
            'company_data': ('🏢 Company', 'company')
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
