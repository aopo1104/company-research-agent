import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.graph import Graph
from backend.services.mongodb import MongoDBService
from backend.services.pdf_service import PDFService
from backend.classes.state import job_status
from backend.prompt_templates import EMAIL_GENERATION_SYSTEM_PROMPT, QUICK_RESEARCH_SYSTEM_PROMPT

# Load environment variables from .env file at startup
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)

app = FastAPI(title="Tavily Company Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
pdf_service = PDFService({"pdf_output_dir": "pdfs"})


def extract_failed_stage(error_message: str, fallback: str | None = None) -> str:
    if error_message.startswith("[") and "]" in error_message:
        return error_message[1:error_message.index("]")]
    return fallback or "unknown"

mongodb = None
if mongo_uri := os.getenv("MONGODB_URI"):
    try:
        mongodb = MongoDBService(mongo_uri)
        logger.info("MongoDB integration enabled")
    except Exception as e:
        logger.warning(f"Failed to initialize MongoDB: {e}. Continuing without persistence.")

class ResearchRequest(BaseModel):
    company: str | None = None
    company_url: str | None = None
    industry: str | None = None
    hq_location: str | None = None
    
    def validate_input(self):
        """Validate that at least company name or URL is provided."""
        if not self.company and not self.company_url:
            raise ValueError("Must provide either company name or company URL")
        return True

class PDFGenerationRequest(BaseModel):
    report_content: str
    company_name: str | None = None

class CompanyInfoExtractionRequest(BaseModel):
    company_url: str

@app.post("/extract-company-info")
async def extract_company_info(data: CompanyInfoExtractionRequest):
    """Extract company name, industry, and location from website URL using AI."""
    try:
        from backend.nodes.company_info_extractor import CompanyInfoExtractor
        
        logger.info(f"Extracting company info from {data.company_url}")
        
        extractor = CompanyInfoExtractor()
        result = await extractor.extract_from_url(data.company_url)
        
        response = JSONResponse(content=result)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
        
    except Exception as e:
        logger.error(f"Error extracting company info: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"信息提取失败：{str(e)}",
                "company_name": "",
                "industry": "",
                "hq_location": "",
            }
        )

@app.options("/research")
async def preflight():
    response = JSONResponse(content=None, status_code=200)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.post("/research")
async def research(data: ResearchRequest):
    try:
        # Validate input
        data.validate_input()
        
        # If company name is missing but URL is provided, extract company info
        if not data.company and data.company_url:
            logger.info(f"No company name provided, extracting from URL: {data.company_url}")
            # First try: extract from domain name directly (fast, no LLM needed)
            from urllib.parse import urlparse
            parsed = urlparse(data.company_url if '://' in data.company_url else f'https://{data.company_url}')
            domain = parsed.hostname or ''
            # Remove www. and TLD to get a rough company name
            domain_name = domain.replace('www.', '').split('.')[0] if domain else ''
            
            # Try LLM-based extraction for better results
            try:
                from backend.nodes.company_info_extractor import CompanyInfoExtractor
                extractor = CompanyInfoExtractor()
                extract_result = await extractor.extract_from_url(data.company_url)
                
                if extract_result["success"] and extract_result["company_name"]:
                    data.company = extract_result["company_name"]
                    if not data.industry and extract_result["industry"]:
                        data.industry = extract_result["industry"]
                    if not data.hq_location and extract_result["hq_location"]:
                        data.hq_location = extract_result["hq_location"]
                    logger.info(f"Extracted company info via LLM: name={data.company}, industry={data.industry}, hq={data.hq_location}")
                else:
                    # Fallback: use domain name
                    data.company = domain_name.capitalize() if domain_name else "Unknown"
                    logger.info(f"LLM extraction failed, using domain name: {data.company}")
            except Exception as e:
                # Fallback: use domain name
                data.company = domain_name.capitalize() if domain_name else "Unknown"
                logger.warning(f"LLM extraction error, using domain name: {data.company}. Error: {e}")
        
        logger.info(f"Received research request for {data.company}")
        job_id = str(uuid.uuid4())
        job_status[job_id].update({
            "status": "pending",
            "company": data.company,
            "current_step": "request_received",
            "last_update": datetime.now().isoformat(),
            "events": [{
                "type": "research_init",
                "company": data.company,
                "message": f"Initiating research for {data.company}",
                "step": "Initializing"
            }]
        })
        asyncio.create_task(process_research(job_id, data))

        response = JSONResponse(content={
            "status": "accepted",
            "job_id": job_id,
            "message": "Research started. Connect to /research/{job_id}/stream for updates."
        })
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error initiating research: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/research-quick")
async def research_quick(data: ResearchRequest):
    """Quick research: single Tavily search + single LLM call for fast results."""
    from langchain_openai import AzureChatOpenAI
    from tavily import AsyncTavilyClient

    try:
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_instance = os.getenv("AZURE_OPENAI_API_INSTANCE_NAME")
        azure_deployment = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")
        azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        tavily_key = os.getenv("TAVILY_API_KEY")

        if not azure_api_key or not azure_instance or not azure_deployment:
            raise HTTPException(status_code=500, detail="Missing Azure OpenAI config")
        if not tavily_key:
            raise HTTPException(status_code=500, detail="Missing Tavily API key")

        # Step 1: Tavily searches combining all research angles
        tavily_client = AsyncTavilyClient(api_key=tavily_key)

        search_queries = [
            f"{data.company} products services overview",
            f"{data.company} company news partnerships",
            f"{data.company} suppliers procurement import China",
        ]
        if data.company_url:
            search_queries.append(f"site:{data.company_url.replace('https://', '').replace('http://', '')}")

        # Run searches in parallel
        search_tasks = [
            tavily_client.search(query=q, max_results=5, include_raw_content=False)
            for q in search_queries
        ]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Combine all results
        combined_content = []
        for result in search_results:
            if isinstance(result, Exception):
                continue
            for item in result.get("results", []):
                combined_content.append(f"[Source: {item.get('url', 'N/A')}]\nTitle: {item.get('title', '')}\n{item.get('content', '')}")

        search_context = "\n\n---\n\n".join(combined_content[:15])

        # Step 2: Single LLM call to generate full report
        llm = AzureChatOpenAI(
            azure_endpoint=f"https://{azure_instance}.openai.azure.com",
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0.3,
        )

        system_prompt = QUICK_RESEARCH_SYSTEM_PROMPT

        company_info = f"Company: {data.company}"
        if data.company_url:
            company_info += f"\nURL: {data.company_url}"
        if data.industry:
            company_info += f"\nIndustry: {data.industry}"
        if data.hq_location:
            company_info += f"\nHQ: {data.hq_location}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{company_info}\n\nSearch Results:\n{search_context}"}
        ]

        result = await llm.ainvoke(messages)
        report = result.content

        return JSONResponse(content={"report": report, "mode": "quick"})

    except Exception as e:
        logger.error(f"Quick research failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def process_research(job_id: str, data: ResearchRequest):
    """Process research request asynchronously and store results"""
    try:
        job_status[job_id].update({
            "status": "processing",
            "company": data.company,
            "current_step": "initializing",
            "last_update": datetime.now().isoformat()
        })

        if mongodb:
            mongodb.create_job(job_id, data.dict())
        
        await asyncio.sleep(0.5)  # Brief delay
        
        logger.info(f"Starting research for {data.company}")

        graph = Graph(
            company=data.company,
            url=data.company_url,
            industry=data.industry,
            hq_location=data.hq_location,
            job_id=job_id
        )

        final_state = {}
        
        # Stream through the graph and update progress
        async for state in graph.run(thread={}):
            final_state.update(state)
            node_name = list(state.keys())[0] if state else 'unknown'
            logger.debug(f"Node completed: {node_name}")
            
            # Update job status with current step
            job_status[job_id].update({
                "status": "processing",
                "current_step": node_name,
                "last_update": datetime.now().isoformat()
            })
        
        # Extract final report
        report_content = final_state.get('report') or (final_state.get('editor') or {}).get('report')
        
        if report_content:
            logger.info(f"Research completed. Report length: {len(report_content)}")
            
            job_status[job_id].update({
                "status": "completed",
                "report": report_content,
                "company": data.company,
                "last_update": datetime.now().isoformat()
            })
            
            if mongodb:
                mongodb.update_job(job_id=job_id, status="completed")
                mongodb.store_report(job_id=job_id, report_data={"report": report_content})
            
            logger.info(f"Research completed successfully for {data.company}")
        else:
            logger.error(f"Research completed without report. State keys: {list(final_state.keys())}")
            job_status[job_id].update({
                "status": "failed",
                "error": "No report generated",
                "last_update": datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Research failed: {str(e)}", exc_info=True)
        stage = extract_failed_stage(str(e), job_status[job_id].get("current_step"))
        job_status[job_id].update({
            "status": "failed",
            "error": str(e),
            "stage": stage,
            "last_update": datetime.now().isoformat()
        })
        
        if mongodb:
            mongodb.update_job(job_id=job_id, status="failed", error=str(e))

@app.get("/")
async def ping():
    return {"message": "Alive"}

@app.get("/research/pdf/{filename}")
async def get_pdf(filename: str):
    pdf_path = os.path.join("pdfs", filename)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type='application/pdf', filename=filename)

@app.get("/research/{job_id}")
async def get_research(job_id: str):
    if not mongodb:
        raise HTTPException(status_code=501, detail="Database persistence not configured")
    job = mongodb.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return job

@app.get("/research/{job_id}/stream")
async def stream_research(job_id: str):
    """Stream research progress via SSE"""
    async def event_generator():
        try:
            # Wait for job to exist
            for _ in range(50):
                if job_id in job_status:
                    break
                await asyncio.sleep(0.1)
            
            last_step = None
            
            # Stream status updates
            while job_id in job_status:
                result = job_status[job_id]
                status = result.get("status")
                current_step = result.get("current_step")
                events = result.get("events", [])
                
                # Send node progress updates when step changes
                if status == "processing" and current_step and current_step != last_step:
                    data = json.dumps({"type": "progress", "step": current_step})
                    yield f"data: {data}\n\n"
                    last_step = current_step
                
                # Send all queued events (FIFO - pop from start)
                while events:
                    event = events.pop(0)
                    data = json.dumps(event)
                    yield f"data: {data}\n\n"
                
                if status == "completed" and (report := result.get("report")):
                    data = json.dumps({"type": "complete", "report": report})
                    yield f"data: {data}\n\n"
                    break
                elif status == "failed":
                    data = json.dumps({
                        "type": "error",
                        "error": result.get("error", "Unknown error"),
                        "stage": result.get("stage", current_step or "unknown")
                    })
                    yield f"data: {data}\n\n"
                    break
                
                await asyncio.sleep(0.1)  # Faster polling for responsive updates
        except Exception as e:
            data = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {data}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/research/{job_id}/report")
async def get_research_report(job_id: str):
    if not mongodb:
        if job_id in job_status:
            result = job_status[job_id]
            if report := result.get("report"):
                return {"report": report}
            if result.get("status") == "failed":
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "failed",
                        "error": result.get("error", "Unknown error"),
                        "stage": result.get("stage", result.get("current_step", "unknown"))
                    }
                )
            # Job exists but report not ready yet
            return JSONResponse(
                status_code=202,
                content={
                    "status": result.get("status", "pending"),
                    "stage": result.get("current_step"),
                    "message": "Report not ready yet"
                }
            )
        raise HTTPException(status_code=404, detail="Job not found")
    
    report = mongodb.get_report(job_id)
    if not report:
        # Check if job exists
        if job := mongodb.get_job(job_id):
            return JSONResponse(
                status_code=202,
                content={"status": job.get("status", "pending"), "message": "Report not ready yet"}
            )
        raise HTTPException(status_code=404, detail="Job not found")
    return report

@app.post("/generate-pdf")
async def generate_pdf(data: PDFGenerationRequest):
    """Generate a PDF from markdown content and stream it to the client."""
    try:
        success, result = pdf_service.generate_pdf_stream(data.report_content, data.company_name)
        if success:
            pdf_buffer, filename = result
            return StreamingResponse(
                pdf_buffer,
                media_type='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        else:
            raise HTTPException(status_code=500, detail=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class EmailGenerationRequest(BaseModel):
    report_content: str
    company_name: str | None = None


@app.post("/generate-email")
async def generate_email(data: EmailGenerationRequest):
    """Generate a B2B outreach email based on research report."""
    from langchain_openai import AzureChatOpenAI
    from langchain_core.output_parsers import StrOutputParser

    try:
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_instance = os.getenv("AZURE_OPENAI_API_INSTANCE_NAME")
        azure_deployment = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")
        azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

        if not azure_api_key or not azure_instance or not azure_deployment:
            raise HTTPException(status_code=500, detail="Missing Azure OpenAI config")

        llm = AzureChatOpenAI(
            azure_endpoint=f"https://{azure_instance}.openai.azure.com",
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0.7,
        )

        system_prompt = EMAIL_GENERATION_SYSTEM_PROMPT

        user_message = f"Based on the following research report about {data.company_name or 'the target company'}, generate a personalized B2B outreach email.\n\nResearch Report:\n{data.report_content[:8000]}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        result = await llm.ainvoke(messages)
        result_text = result.content

        # Parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            email_data = json.loads(json_match.group())
            return JSONResponse(content=email_data)
        else:
            raise ValueError("LLM did not return valid JSON")

    except json.JSONDecodeError as e:
        logger.error(f"Email generation JSON parse failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse email response")
    except Exception as e:
        logger.error(f"Email generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TranslateRequest(BaseModel):
    content: str
    target_language: str = "zh"


@app.post("/translate")
async def translate_report(data: TranslateRequest):
    """Translate report content to the target language using Azure OpenAI."""
    from langchain_openai import AzureChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    try:
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_instance = os.getenv("AZURE_OPENAI_API_INSTANCE_NAME")
        azure_deployment = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")
        azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

        if not azure_api_key or not azure_instance or not azure_deployment:
            raise HTTPException(status_code=500, detail="Missing Azure OpenAI config")

        llm = AzureChatOpenAI(
            azure_endpoint=f"https://{azure_instance}.openai.azure.com",
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0,
        )

        lang_map = {"zh": "简体中文", "en": "English", "ja": "日本語"}
        target_name = lang_map.get(data.target_language, data.target_language)

        prompt = ChatPromptTemplate.from_messages([
            ("system", f"You are a professional translator. Translate the following markdown report to {target_name}. "
                       "Preserve all markdown formatting, headers, bullet points, and links. "
                       "Only translate the text content, not URLs or proper nouns that should remain in their original form."),
            ("user", "{content}")
        ])

        chain = prompt | llm | StrOutputParser()
        translated = await chain.ainvoke({"content": data.content})

        return JSONResponse(content={"translated": translated})
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999)
