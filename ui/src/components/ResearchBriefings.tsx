import { useState } from 'react';
import { ChevronDown, ChevronUp, CheckCircle2, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { glassStyle } from '../styles';

type BriefingStatus = {
  company: boolean;
  industry: boolean;
  financial: boolean;
  news: boolean;
  social_media: boolean;
};

interface ResearchBriefingsProps {
  briefingStatus: BriefingStatus;
  briefingContents: Record<string, string>;
  isExpanded: boolean;
  onToggleExpand: () => void;
  isResetting: boolean;
}

const CATEGORY_LABELS: Record<string, string> = {
  company: '公司',
  industry: '行业',
  financial: '财务',
  news: '新闻',
  social_media: '社媒'
};

const ResearchBriefings = ({
  briefingStatus,
  briefingContents,
  isExpanded,
  onToggleExpand,
  isResetting
}: ResearchBriefingsProps) => {
  const [expandedBriefing, setExpandedBriefing] = useState<string | null>(null);

  const toggleBriefing = (category: string) => {
    setExpandedBriefing(prev => prev === category ? null : category);
  };

  return (
    <div 
      className={`${glassStyle.card} transition-all duration-300 ease-in-out ${
        isResetting ? 'opacity-0 transform -translate-y-4' : 'opacity-100 transform translate-y-0'
      } font-['DM_Sans']`}
    >
      <div 
        className="flex items-center justify-between cursor-pointer"
        onClick={onToggleExpand}
      >
        <h2 className="text-xl font-semibold text-gray-900">
          研究摘要
        </h2>
        <button className="text-gray-600 hover:text-gray-900 transition-colors">
          {isExpanded ? (
            <ChevronUp className="h-6 w-6" />
          ) : (
            <ChevronDown className="h-6 w-6" />
          )}
        </button>
      </div>

      <div className={`overflow-hidden transition-all duration-500 ease-in-out ${
        isExpanded ? 'mt-6 max-h-[5000px] opacity-100' : 'max-h-0 opacity-0'
      }`}>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4 px-1">
          {['company', 'industry', 'financial', 'news', 'social_media'].map((category) => {
            const isComplete = briefingStatus[category as keyof BriefingStatus];
            const hasContent = !!briefingContents[category];
            const isSelected = expandedBriefing === category;
            
            return (
              <div 
                key={category} 
                className={`backdrop-filter backdrop-blur-lg shadow-sm rounded-lg p-4 transition-all duration-500 ease-in-out relative ${
                  isSelected
                    ? 'border-2 border-[#468BFF] bg-gradient-to-br from-[#468BFF]/10 to-[#468BFF]/15 shadow-md ring-2 ring-[#468BFF]/20'
                    : isComplete 
                      ? 'border border-[#468BFF] bg-gradient-to-br from-[#468BFF]/5 to-[#468BFF]/10 shadow-md cursor-pointer hover:shadow-lg hover:border-[#468BFF]/80' 
                      : 'border border-gray-200 bg-white/80 hover:border-gray-300 hover:shadow-sm'
                } backdrop-blur-sm group`}
                onClick={() => hasContent && toggleBriefing(category)}
              >
                {/* Background decoration element (only visible when active) */}
                <div 
                  className={`absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(70,139,255,0.15),transparent_70%)] opacity-0 transition-opacity duration-700 ease-in-out rounded-lg ${
                    isComplete ? 'opacity-100' : ''
                  }`}
                  style={{ pointerEvents: 'none' }}
                />
                
                <div className="relative z-10 flex items-center justify-between">
                  <h3 className={`text-sm font-medium transition-all duration-500 ${
                    isComplete
                      ? 'text-[#468BFF]'
                      : 'text-gray-700 group-hover:text-gray-900'
                  }`}>{CATEGORY_LABELS[category] || category}</h3>
                  {isComplete ? (
                    <CheckCircle2 className="h-4 w-4 text-[#468BFF] transition-all duration-300" />
                  ) : (
                    <div className="h-4 w-4 rounded-full border border-gray-200 group-hover:border-gray-300 transition-all duration-300"></div>
                  )}
                </div>
                {hasContent && (
                  <div className="relative z-10 mt-2 flex items-center gap-1 text-xs text-[#468BFF]">
                    <FileText className="h-3 w-3" />
                    <span>{isSelected ? '点击收起' : '点击查看'}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Expanded briefing content */}
        {expandedBriefing && briefingContents[expandedBriefing] && (
          <div className="mt-4 backdrop-blur-2xl bg-white/95 border border-[#468BFF]/20 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-100">
              <FileText className="h-4 w-4 text-[#468BFF]" />
              <h3 className="text-sm font-semibold text-gray-800">
                {CATEGORY_LABELS[expandedBriefing]} 研究摘要
              </h3>
              <span className="text-xs text-gray-400 ml-auto">
                {briefingContents[expandedBriefing].length} 字符
              </span>
            </div>
            <div className="prose prose-sm max-w-none text-gray-700 max-h-[500px] overflow-y-auto">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({node, href, ...props}) => (
                    <a
                      href={href}
                      className="text-[#468BFF] hover:text-[#8FBCFA] underline cursor-pointer transition-colors"
                      target="_blank"
                      rel="noopener noreferrer"
                      {...props}
                    />
                  ),
                }}
              >
                {briefingContents[expandedBriefing]}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>

      {!isExpanded && (
        <div className="mt-2 text-sm text-gray-600">
          已完成 {Object.values(briefingStatus).filter(Boolean).length}/{Object.keys(briefingStatus).length} 项摘要
        </div>
      )}
    </div>
  );
};

export default ResearchBriefings; 