import { useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import { Check, Copy, Download, Languages, Loader2 } from 'lucide-react';
import type { GlassStyle, AnimationStyle } from '../types';

interface ResearchReportProps {
  output: {
    summary: string;
    details: {
      report: string;
    };
  } | null;
  isResetting: boolean;
  isStreaming: boolean;
  glassStyle: GlassStyle;
  fadeInAnimation: AnimationStyle;
  loaderColor: string;
  isGeneratingPdf: boolean;
  isCopied: boolean;
  onCopyToClipboard: () => void;
  onGeneratePdf: () => void;
}

const ResearchReport = ({
  output,
  isResetting,
  isStreaming,
  glassStyle,
  fadeInAnimation,
  loaderColor,
  isGeneratingPdf,
  isCopied,
  onCopyToClipboard,
  onGeneratePdf
}: ResearchReportProps) => {
  const [translatedReport, setTranslatedReport] = useState<string | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);

  if (!output || !output.details) return null;

  // Report is output in Chinese; translate button switches to English
  const handleTranslate = async () => {
    if (translatedReport) {
      setShowTranslation(!showTranslation);
      return;
    }

    setIsTranslating(true);
    setTranslateError(null);
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: output.details.report,
          target_language: 'en'
        })
      });
      if (response.ok) {
        const data = await response.json();
        setTranslatedReport(data.translated);
        setShowTranslation(true);
      } else {
        const errData = await response.json().catch(() => ({}));
        setTranslateError(errData.detail || `请求失败 (${response.status})`);
      }
    } catch (err) {
      console.error('Translation failed:', err);
      setTranslateError('网络错误，请检查后端连接');
    } finally {
      setIsTranslating(false);
    }
  };

  const displayReport = showTranslation && translatedReport
    ? translatedReport
    : output.details.report;

  return (
    <div 
      className={`${glassStyle.card} ${fadeInAnimation.fadeIn} ${isResetting ? 'opacity-0 transform -translate-y-4' : 'opacity-100 transform translate-y-0'} font-['DM_Sans']`}
    >
      {isStreaming && (
        <div className="flex items-center gap-2 mb-4 px-4 py-2 bg-[#468BFF]/10 rounded-lg border border-[#468BFF]/20">
          <Loader2 className="h-4 w-4 animate-spin" style={{ stroke: loaderColor }} />
          <span className="text-sm text-gray-600">正在生成报告...</span>
        </div>
      )}
      <div className="flex justify-end gap-2 mb-4">
        {output?.details?.report && (
          <>
            <button
              onClick={handleTranslate}
              disabled={isTranslating}
              className={`inline-flex items-center justify-center px-4 py-2 rounded-lg transition-all duration-200 ${
                showTranslation
                  ? 'bg-green-500 text-white hover:bg-green-600'
                  : 'bg-[#7C3AED] text-white hover:bg-[#6D28D9]'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
              title={showTranslation ? '显示中文原文' : '翻译为英文'}
            >
              {isTranslating ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Languages className="h-5 w-5" />
              )}
              <span className="ml-2 text-sm">
                {isTranslating ? '翻译中...' : showTranslation ? '中文原文' : 'English'}
              </span>
            </button>
            {translateError && (
              <span className="text-red-500 text-xs self-center">{translateError}</span>
            )}
            <button
              onClick={onCopyToClipboard}
              className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-[#468BFF] text-white hover:bg-[#8FBCFA] transition-all duration-200"
            >
              {isCopied ? (
                <Check className="h-5 w-5" />
              ) : (
                <Copy className="h-5 w-5" />
              )}
            </button>
            <button
              onClick={onGeneratePdf}
              disabled={isGeneratingPdf}
              className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-[#FFB800] text-white hover:bg-[#FFA800] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGeneratingPdf ? (
                <>
                  <Loader2 className="animate-spin h-5 w-5 mr-2" style={{ stroke: loaderColor }} />
                  生成PDF中...
                </>
              ) : (
                <>
                  <Download className="h-5 w-5" />
                  <span className="ml-2">PDF</span>
                </>
              )}
            </button>
          </>
        )}
      </div>
      <div className="prose prose-invert prose-lg max-w-none">
        <div className="mt-4">
          <ReactMarkdown
            rehypePlugins={[rehypeRaw]}
            remarkPlugins={[remarkGfm]}
            components={{
              div: ({node, ...props}) => (
                <div className="space-y-4 text-gray-800" {...props} />
              ),
              h1: ({node, children, ...props}) => {
                const text = String(children);
                const isFirstH1 = text.includes("Research Report") || text.includes("研究报告");
                const isReferences = text.includes("References") || text.includes("参考来源");
                return (
                  <div>
                    <h1 
                      className={`font-bold text-gray-900 break-words whitespace-pre-wrap ${isFirstH1 ? 'text-5xl mb-10 mt-4 max-w-[calc(100%-8rem)]' : 'text-3xl mb-6'}`} 
                      {...props} 
                    >
                      {children}
                    </h1>
                    {isReferences && (
                      <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-gray-300 to-transparent my-8"></div>
                    )}
                  </div>
                );
              },
              h2: ({node, ...props}) => (
                <h2 className="text-3xl font-bold text-gray-900 first:mt-2 mt-8 mb-4" {...props} />
              ),
              h3: ({node, ...props}) => (
                <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3" {...props} />
              ),
              p: ({node, children, ...props}) => {
                const text = String(children);
                const isSubsectionHeader = (
                  text.includes('\n') === false && 
                  text.length < 50 && 
                  (text.endsWith(':') || /^[A-Z][A-Za-z\s\/]+$/.test(text))
                );
                
                if (isSubsectionHeader) {
                  return (
                    <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">
                      {text.endsWith(':') ? text.slice(0, -1) : text}
                    </h3>
                  );
                }
                
                const isBulletLabel = text.startsWith('•') && text.includes(':');
                if (isBulletLabel) {
                  const [label, content] = text.split(':');
                  return (
                    <div className="text-gray-800 my-2">
                      <span className="font-semibold text-gray-900">
                        {label.replace('•', '').trim()}:
                      </span>
                      {content}
                    </div>
                  );
                }
                
                const urlRegex = /(https?:\/\/[^\s<>"]+)/g;
                if (urlRegex.test(text)) {
                  const parts = text.split(urlRegex);
                  return (
                    <p className="text-gray-800 my-2" {...props}>
                      {parts.map((part, i) => 
                        urlRegex.test(part) ? (
                          <a 
                            key={i}
                            href={part}
                            className="text-[#468BFF] hover:text-[#8FBCFA] underline decoration-[#468BFF] hover:decoration-[#8FBCFA] cursor-pointer transition-colors"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {part}
                          </a>
                        ) : part
                      )}
                    </p>
                  );
                }
                
                return <p className="text-gray-800 my-2" {...props}>{children}</p>;
              },
              ul: ({node, ...props}) => (
                <ul className="text-gray-800 space-y-1 list-disc pl-6" {...props} />
              ),
              li: ({node, ...props}) => (
                <li className="text-gray-800" {...props} />
              ),
              a: ({node, href, ...props}) => (
                <a 
                  href={href}
                  className="text-[#468BFF] hover:text-[#8FBCFA] underline decoration-[#468BFF] hover:decoration-[#8FBCFA] cursor-pointer transition-colors" 
                  target="_blank"
                  rel="noopener noreferrer"
                  {...props} 
                />
              ),
            }}
          >
            {displayReport || "暂无报告内容"}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
};

export default ResearchReport; 