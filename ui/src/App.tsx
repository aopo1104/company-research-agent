import { useState, useEffect, useRef } from "react";
import {
  Header,
  ResearchStatus,
  ResearchReport,
  ResearchForm,
  ResearchQueries,
  CurationExtraction,
  ResearchBriefings,
  EmailGenerator
} from './components';
import type { ResearchOutput, ResearchStatusType } from './types';
import { glassStyle, fadeInAnimation } from './styles';

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {

  const [isResearching, setIsResearching] = useState(false);
  const [status, setStatus] = useState<ResearchStatusType | null>(null);
  const [output, setOutput] = useState<ResearchOutput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [originalCompanyName, setOriginalCompanyName] = useState<string>("");
  const [currentPhase, setCurrentPhase] = useState<'search' | 'enrichment' | 'briefing' | 'complete' | null>(null);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const statusRef = useRef<HTMLDivElement>(null);
  const [queries, setQueries] = useState<Array<{ text: string; number: number; category: string }>>([]);
  const [streamingQueries, setStreamingQueries] = useState<Record<string, { text: string; number: number; category: string; isComplete: boolean }>>({});
  const [isQueriesExpanded, setIsQueriesExpanded] = useState(true);
  const [enrichmentCounts, setEnrichmentCounts] = useState<{
    company: { total: number; enriched: number };
    industry: { total: number; enriched: number };
    financial: { total: number; enriched: number };
    news: { total: number; enriched: number };
    social_media: { total: number; enriched: number };
  } | undefined>(undefined);
  const [briefingStatus, setBriefingStatus] = useState({
    company: false,
    industry: false,
    financial: false,
    news: false,
    social_media: false
  });
  const [briefingContents, setBriefingContents] = useState<Record<string, string>>({});
  const [curationDetails, setCurationDetails] = useState<Record<string, Array<{url: string; title: string; score: number; kept: boolean}>>>({});
  const [isEnrichmentExpanded, setIsEnrichmentExpanded] = useState(true);
  const [isBriefingExpanded, setIsBriefingExpanded] = useState(true);
  const [hasScrolledToStatus, setHasScrolledToStatus] = useState(false);
  const [isReportStreaming, setIsReportStreaming] = useState(false);
  const latestStatusRef = useRef<ResearchStatusType | null>(null);
  const streamSettledRef = useRef(false);
  const [loaderColor, setLoaderColor] = useState("#468BFF");
  
  // Scroll helper function
  const scrollToStatus = () => {
    if (!hasScrolledToStatus && statusRef.current) {
      const yOffset = -20;
      const y = statusRef.current.getBoundingClientRect().top + window.pageYOffset + yOffset;
      window.scrollTo({ top: y, behavior: 'smooth' });
      setHasScrolledToStatus(true);
    }
  };

  // Add useEffect for color cycling
  useEffect(() => {
    if (!isResearching) return;
    
    const colors = [
      "#468BFF", // Blue
      "#8FBCFA", // Light Blue
      "#FE363B", // Red
      "#FF9A9D", // Light Red
      "#FDBB11", // Yellow
      "#F6D785", // Light Yellow
    ];
    
    let currentIndex = 0;
    
    const interval = setInterval(() => {
      currentIndex = (currentIndex + 1) % colors.length;
      setLoaderColor(colors[currentIndex]);
    }, 1000);
    
    return () => clearInterval(interval);
  }, [isResearching]);

  useEffect(() => {
    latestStatusRef.current = status;
  }, [status]);

  const resetResearch = () => {
    setIsResetting(true);
    
    // Use setTimeout to create a smooth transition
    setTimeout(() => {
      setStatus(null);
      setOutput(null);
      setError(null);
      setIsComplete(false);
      setCurrentPhase(null);
      setQueries([]);
      setStreamingQueries({});
      setEnrichmentCounts(undefined);
      setBriefingStatus({
        company: false,
        industry: false,
        financial: false,
        news: false,
        social_media: false
      });
      setBriefingContents({});
      setCurationDetails({});
      setIsQueriesExpanded(true);
      setIsEnrichmentExpanded(true);
      setIsBriefingExpanded(true);
      setHasScrolledToStatus(false);
      setIsReportStreaming(false);
      setIsResetting(false);
    }, 300);
  };

  const formatStageError = (stage?: string, message?: string) => {
    if (!message) {
      return 'Unknown error';
    }
    return stage ? `[${stage}] ${message}` : message;
  };

  const syncJobStateAfterStreamError = async (jobId: string) => {
    let lastPayload: Record<string, unknown> | null = null;
    let lastStatusCode: number | null = null;
    let lastFetchError: unknown = null;

    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const response = await fetch(`${API_URL}/research/${jobId}/report`, {
          method: 'GET',
          mode: 'cors',
          credentials: 'omit',
          headers: {
            Accept: 'application/json',
          },
        });

        lastStatusCode = response.status;
        lastPayload = await response.json().catch(() => null);

        if (response.ok && lastPayload && 'report' in lastPayload) {
          setIsReportStreaming(false);
          setOutput({
            summary: '',
            details: { report: String(lastPayload.report || '') },
          });
          setStatus({ step: '\u5b8c\u6210', message: '\u7814\u7a76\u5df2\u6210\u529f\u5b8c\u6210' });
          setIsComplete(true);
          setIsResearching(false);
          setError(null);
          streamSettledRef.current = true;
          return;
        }

        if (lastPayload?.status === 'failed' || response.status >= 500) {
          const message = formatStageError(
            typeof lastPayload?.stage === 'string' ? lastPayload.stage : undefined,
            typeof lastPayload?.error === 'string'
              ? lastPayload.error
              : typeof lastPayload?.message === 'string'
                ? lastPayload.message
                : 'Server error'
          );
          setStatus({ step: typeof lastPayload?.stage === 'string' ? lastPayload.stage : 'Failed', message });
          setError(message);
          setIsResearching(false);
          streamSettledRef.current = true;
          return;
        }

        if (lastPayload?.status === 'processing' || lastPayload?.status === 'pending') {
          await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
          continue;
        }

        if (lastPayload?.status) {
          break;
        }
      } catch (err) {
        lastFetchError = err;
        await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
      }
    }

    const lastKnownStep = latestStatusRef.current?.step || 'Unknown stage';
    const lastKnownMessage = latestStatusRef.current?.message || 'No additional backend status available';

    if (lastPayload?.status) {
      const stage = typeof lastPayload.stage === 'string' ? lastPayload.stage : lastKnownStep;
      const message = formatStageError(
        typeof lastPayload.stage === 'string' ? lastPayload.stage : undefined,
        typeof lastPayload.message === 'string'
          ? lastPayload.message
          : `SSE stream disconnected while backend was in ${stage}`
      );
      setStatus({ step: stage, message });
      setError(message);
      setIsResearching(false);
      streamSettledRef.current = true;
      return;
    }

    const fallbackMessage = lastStatusCode
      ? `Stream disconnected, and job state check returned HTTP ${lastStatusCode}. Last known step: ${lastKnownStep}. ${lastKnownMessage}`
      : `Stream disconnected, and job state could not be fetched. Last known step: ${lastKnownStep}. ${lastKnownMessage}`;

    const detailedMessage = lastFetchError instanceof Error
      ? `${fallbackMessage} Fetch error: ${lastFetchError.message}`
      : fallbackMessage;

    setStatus({ step: lastKnownStep, message: detailedMessage });
    setError(detailedMessage);
    setIsResearching(false);
    streamSettledRef.current = true;
  };

  // Stream research results via SSE
  const streamResults = (jobId: string) => {
    streamSettledRef.current = false;
    const eventSource = new EventSource(`${API_URL}/research/${jobId}/stream`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Helper function to map node names to user-friendly step names
        const getStepName = (nodeName: string): string => {
          const stepMap: Record<string, string> = {
            'grounding': '搜索',
            'financial_analyst': '搜索',
            'news_scanner': '搜索',
            'industry_analyst': '搜索',
            'company_analyst': '搜索',
            'collector': '搜索',
            'curator': '内容增强',
            'enricher': '内容增强',
            'briefing': '生成摘要',
            'editor': '报告编辑'
          };
          return stepMap[nodeName] || nodeName;
        };

        // Handle progress events from backend (node transitions)
        if (data.type === 'progress' && data.step) {
          const stepName = getStepName(data.step);
          setStatus({
            step: stepName,
            message: `正在处理 ${data.step}...`
          });
          
          // Update phase based on step
          if (['grounding', 'financial_analyst', 'news_scanner', 'industry_analyst', 'company_analyst', 'collector'].includes(data.step)) {
            setCurrentPhase('search');
          } else if (['curator', 'enricher'].includes(data.step)) {
            setCurrentPhase('enrichment');
          } else if (data.step === 'briefing') {
            setCurrentPhase('briefing');
          }
          
          scrollToStatus();
        }
        
        // Direct event-to-phase mapping
        if (data.type === 'query_generating') {
          // Show query being generated and update streaming queries
          setCurrentPhase('search');
          setStatus({
            step: '搜索',
            message: `查询 ${data.query_number}: ${data.query}`
          });
          // Update streaming queries with current partial query
          const key = `${data.category}_${data.query_number}`;
          setStreamingQueries(prev => ({
            ...prev,
            [key]: {
              text: data.query,
              number: data.query_number,
              category: data.category,
              isComplete: false
            }
          }));
        } else if (data.type === 'query_generated') {
          // Show completed query and move to queries list
          setCurrentPhase('search');
          setStatus({
            step: '搜索',
            message: `已生成: ${data.query}`
          });
          // Add to completed queries
          setQueries(prev => [...prev, {
            text: data.query,
            number: data.query_number,
            category: data.category
          }]);
          // Remove from streaming queries
          const key = `${data.category}_${data.query_number}`;
          setStreamingQueries(prev => {
            const updated = { ...prev };
            delete updated[key];
            return updated;
          });
          scrollToStatus();
        } else if (data.type === 'research_init') {
          // Show research initialization
          setCurrentPhase('search');
          setStatus({
            step: '初始化',
            message: data.message || `开始研究 ${data.company}`
          });
        } else if (data.type === 'crawl_start') {
          // Show website crawl starting
          setCurrentPhase('search');
          setStatus({
            step: '网站爬取',
            message: data.message || '正在爬取公司官网'
          });
        } else if (data.type === 'curation') {
          // Show curation progress - transition to enrichment phase
          setCurrentPhase('enrichment');
          setStatus({
            step: '精选数据',
            message: data.message || `精选 ${data.category} 文档`
          });
          // Initialize enrichment counts when curation starts for a category
          if (data.category) {
            setEnrichmentCounts(prev => ({
              ...prev,
              [data.category]: {
                total: data.total || 0,
                enriched: 0
              }
            } as typeof enrichmentCounts));
          }
          // Collapse queries section when moving to enrichment
          setTimeout(() => {
            setIsQueriesExpanded(false);
          }, 1000);
          scrollToStatus();
        } else if (data.type === 'enrichment') {
          // Show enrichment progress
          setCurrentPhase('enrichment');
          setStatus({
            step: '内容增强',
            message: data.message || '深度爬取补充内容'
          });
          // Update enriched count if provided
          if (data.category && data.enriched !== undefined) {
            const category = data.category as 'company' | 'industry' | 'financial' | 'news';
            setEnrichmentCounts(prev => {
              if (!prev) return prev;
              return {
                ...prev,
                [category]: {
                  total: prev[category]?.total || data.total || 0,
                  enriched: data.enriched
                }
              } as typeof enrichmentCounts;
            });
          }
        } else if (data.type === 'briefing_start') {
          // Show briefing generation starting
          setCurrentPhase('briefing');
          setStatus({
            step: '生成摘要',
            message: `正在从 ${data.total_docs} 篇文档生成 ${data.category} 摘要`
          });
          // Collapse enrichment section when moving to briefing
          setTimeout(() => {
            setIsEnrichmentExpanded(false);
          }, 1000);
          scrollToStatus();
        } else if (data.type === 'briefing_complete') {
          // Show briefing completion and mark category as complete
          setCurrentPhase('briefing');
          setStatus({
            step: '摘要完成',
            message: `${data.category} 摘要已生成（${data.content_length} 字符）`
          });
          // Store briefing content
          if (data.category && data.content) {
            setBriefingContents(prev => ({
              ...prev,
              [data.category]: data.content
            }));
          }
          // Mark briefing as complete for this category
          if (data.category) {
            setBriefingStatus(prev => {
              const newBriefingStatus = {
                ...prev,
                [data.category]: true
              };
              
              // Check if all briefings are complete
              const allBriefingsComplete = Object.values(newBriefingStatus).every(status => status);
              
              // Collapse briefing section when all briefings are complete
              if (allBriefingsComplete) {
                setTimeout(() => {
                  setIsBriefingExpanded(false);
                }, 2000);
              }
              
              return newBriefingStatus;
            });
          }
        } else if (data.type === 'report_compilation') {
          // Show report compilation
          setCurrentPhase('briefing');
          setStatus({
            step: '报告编辑',
            message: data.message || '正在汇编最终报告'
          });
        } else if (data.type === 'report_chunk' && data.chunk) {
          // Stream report chunks as they arrive
          setIsReportStreaming(true);
          setOutput((prev) => {
            const currentReport = prev?.details?.report || '';
            return {
              summary: "",
              details: { report: currentReport + data.chunk },
            };
          });
          setStatus({
            step: '报告编辑',
            message: '正在生成最终报告...'
          });
        } else if (data.type === 'complete' && data.report) {
          setIsReportStreaming(false);
          setOutput({
            summary: "",
            details: { report: data.report },
          });
          setStatus({ step: "完成", message: "研究已成功完成" });
          setIsComplete(true);
          setIsResearching(false);
          streamSettledRef.current = true;
          eventSource.close();
        } else if (data.type === 'error') {
          const message = formatStageError(data.stage, data.error);
          setStatus({ step: data.stage || '失败', message });
          setError(message);
          setIsResearching(false);
          streamSettledRef.current = true;
          eventSource.close();
        } else if (data.type === 'stage_warning') {
          setStatus({
            step: data.stage || '警告',
            message: data.message || '收到阶段警告'
          });
        } else if (data.type === 'scrape_source' || data.type === 'llm_call' || data.type === 'llm_status' || data.type === 'tavily_search') {
          // Activity log events - ignored
        } else if (data.type === 'curation_details') {
          // Store all URLs with their kept/rejected status for a category
          if (data.category && data.all_urls) {
            setCurationDetails(prev => ({
              ...prev,
              [data.category]: data.all_urls
            }));
          }
        }
      } catch (err) {
        console.error('Error parsing SSE data:', err);
      }
    };

    eventSource.onerror = () => {
      if (streamSettledRef.current) {
        eventSource.close();
        return;
      }

      eventSource.close();
      void syncJobStateAfterStreamError(jobId).catch((err) => {
        const lastKnownStep = latestStatusRef.current?.step || 'Stream';
        const lastKnownMessage = latestStatusRef.current?.message || 'No additional backend status available';
        const message = err instanceof Error
          ? `Stream recovery failed. Last known step: ${lastKnownStep}. ${lastKnownMessage}. ${err.message}`
          : `Stream recovery failed. Last known step: ${lastKnownStep}. ${lastKnownMessage}.`;
        setStatus({ step: lastKnownStep, message });
        setError(message);
        setIsResearching(false);
        streamSettledRef.current = true;
      });
    };
  };

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  // Create a custom handler for the form that receives form data
  const handleFormSubmit = async (formData: {
    companyName: string;
    companyUrl: string;
    companyHq: string;
    companyIndustry: string;
    mode?: 'quick' | 'deep';
  }) => {

    // Clear any existing errors first
    setError(null);

    // If research is complete, reset the UI first
    if (isComplete) {
      resetResearch();
      await new Promise(resolve => setTimeout(resolve, 300)); // Wait for reset animation
    }

    // Clear any existing SSE connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setIsResearching(true);
    setOriginalCompanyName(formData.companyName || formData.companyUrl);
    setStatus({
      step: "处理中",
      message: formData.mode === 'quick' ? "正在快速分析..." : "正在启动深度研究..."
    });

    // Format the company URL if provided
    const formattedCompanyUrl = formData.companyUrl
      ? formData.companyUrl.startsWith('http://') || formData.companyUrl.startsWith('https://')
        ? formData.companyUrl
        : `https://${formData.companyUrl}`
      : undefined;

    const requestData = {
      company: formData.companyName || undefined,
      company_url: formattedCompanyUrl,
      industry: formData.companyIndustry || undefined,
      hq_location: formData.companyHq || undefined,
    };

    try {
      if (formData.mode === 'quick') {
        // Quick mode: single LLM call
        const response = await fetch(`${API_URL}/research-quick`, {
          method: "POST",
          mode: "cors",
          credentials: "omit",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestData),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        setOutput({
          summary: `快速分析: ${formData.companyName}`,
          details: { report: data.report }
        });
        setCurrentPhase('complete');
        setIsComplete(true);
        setIsResearching(false);
        setStatus({ step: "完成", message: "快速分析已完成" });
      } else {
        // Deep mode: full pipeline with SSE
        const url = `${API_URL}/research`;

        const response = await fetch(url, {
          method: "POST",
          mode: "cors",
          credentials: "omit",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestData),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.job_id) {
          streamResults(data.job_id);
        } else {
          throw new Error("No job ID received");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start research");
      setIsResearching(false);
    }
  };

  // Add new function to handle PDF generation
  const handleGeneratePdf = async () => {
    if (!output || isGeneratingPdf) return;
    
    setIsGeneratingPdf(true);
    try {
      const response = await fetch(`${API_URL}/generate-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          report_content: output.details.report,
          company_name: originalCompanyName || output.details.report
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to generate PDF');
      }
      
      // Get the blob from the response
      const blob = await response.blob();
      
      // Create a URL for the blob
      const url = window.URL.createObjectURL(blob);
      
      // Create a temporary link element
      const link = document.createElement('a');
      link.href = url;
      link.download = `${originalCompanyName || 'research_report'}.pdf`;
      
      // Append to body, click, and remove
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Clean up the URL
      window.URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('Error generating PDF:', error);
      setError(error instanceof Error ? error.message : 'Failed to generate PDF');
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  // Add new function to handle copying to clipboard
  const handleCopyToClipboard = async () => {
    if (!output?.details?.report) return;
    
    try {
      await navigator.clipboard.writeText(output.details.report);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000); // Reset after 2 seconds
    } catch (err) {
      console.error('Failed to copy text: ', err);
      setError('Failed to copy to clipboard');
    }
  };


  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 px-4 py-6 relative">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(70,139,255,0.08)_1px,transparent_0)] bg-[length:32px_32px] bg-center"></div>
      <div className="max-w-6xl mx-auto relative">
        {/* Header Component */}
        <Header glassStyle={glassStyle.card} />

        {/* Form Section */}
        <div className="mt-5">
          <ResearchForm 
            onSubmit={handleFormSubmit}
            isResearching={isResearching}
            glassStyle={glassStyle}
            loaderColor={loaderColor}
          />
        </div>

        {/* Error Message */}
        {error && (
          <div 
            className={`mt-4 ${glassStyle.card} border-[#FE363B]/30 bg-[#FE363B]/10 ${fadeInAnimation.fadeIn} ${isResetting ? 'opacity-0 transform -translate-y-4' : 'opacity-100 transform translate-y-0'} font-['DM_Sans']`}
          >
            <p className="text-[#FE363B]">{error}</p>
          </div>
        )}

        {/* Status Box */}
        {status && (
          <div className="mt-4">
            <ResearchStatus
              status={status}
              error={error}
              isComplete={isComplete}
              currentPhase={currentPhase}
              isResetting={isResetting}
              glassStyle={glassStyle}
              loaderColor={loaderColor}
              statusRef={statusRef}
            />
          </div>
        )}

        {/* === MAIN TWO-PANEL LAYOUT === */}
        {(output || queries.length > 0 || Object.keys(streamingQueries).length > 0) && (
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-5">
            
            {/* LEFT PANEL: Research Results (2/3 width) */}
            <div className="lg:col-span-2 space-y-4">
              {/* Section Header */}
              <div className="flex items-center gap-2 px-1">
                <div className="w-1 h-5 bg-[#468BFF] rounded-full"></div>
                <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider">研究分析</h2>
                {isComplete && <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">已完成</span>}
              </div>

              {/* Research Report */}
              {output && output.details && (
                <ResearchReport
                  output={{
                    summary: output.summary,
                    details: {
                      report: output.details.report || ''
                    }
                  }}
                  isResetting={isResetting}
                  isStreaming={isReportStreaming}
                  glassStyle={glassStyle}
                  fadeInAnimation={fadeInAnimation}
                  loaderColor={loaderColor}
                  isGeneratingPdf={isGeneratingPdf}
                  isCopied={isCopied}
                  onCopyToClipboard={handleCopyToClipboard}
                  onGeneratePdf={handleGeneratePdf}
                />
              )}

              {/* Research Briefings */}
              {(currentPhase === 'briefing' || currentPhase === 'complete') && (
                <ResearchBriefings
                  briefingStatus={briefingStatus}
                  briefingContents={briefingContents}
                  isExpanded={isBriefingExpanded}
                  onToggleExpand={() => setIsBriefingExpanded(!isBriefingExpanded)}
                  isResetting={isResetting}
                />
              )}

              {/* Curation and Extraction */}
              {(currentPhase === 'enrichment' || currentPhase === 'briefing' || currentPhase === 'complete') && enrichmentCounts && (
                <CurationExtraction
                  enrichmentCounts={enrichmentCounts}
                  curationDetails={curationDetails}
                  isExpanded={isEnrichmentExpanded}
                  onToggleExpand={() => setIsEnrichmentExpanded(!isEnrichmentExpanded)}
                  isResetting={isResetting}
                  loaderColor={loaderColor}
                />
              )}

              {/* Research Queries */}
              {(queries.length > 0 || Object.keys(streamingQueries).length > 0) && (
                <ResearchQueries
                  queries={queries}
                  streamingQueries={streamingQueries}
                  isExpanded={isQueriesExpanded}
                  onToggleExpand={() => setIsQueriesExpanded(!isQueriesExpanded)}
                  isResetting={isResetting}
                  glassStyle={glassStyle.card}
                />
              )}
            </div>

            {/* RIGHT PANEL: Email & Actions (1/3 width) */}
            <div className="lg:col-span-1 space-y-4">
              {/* Section Header */}
              <div className="flex items-center gap-2 px-1">
                <div className="w-1 h-5 bg-purple-500 rounded-full"></div>
                <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider">开发信</h2>
              </div>

              {/* Email Generator - sticky on desktop */}
              <div className="lg:sticky lg:top-6">
                {output && output.details && isComplete ? (
                  <EmailGenerator
                    reportContent={output.details.report || ''}
                    companyName={originalCompanyName}
                    isResetting={isResetting}
                  />
                ) : (
                  <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50/50 p-6 text-center">
                    <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-gray-100 flex items-center justify-center">
                      <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                      </svg>
                    </div>
                    <p className="text-sm font-medium text-gray-500">等待研究完成</p>
                    <p className="text-xs text-gray-400 mt-1">完成分析后可一键生成开发信</p>
                  </div>
                )}
              </div>


            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;