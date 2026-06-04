import { useState } from 'react';
import { ChevronDown, ChevronUp, Loader2, CheckCircle2, XCircle, ExternalLink } from 'lucide-react';
import type { EnrichmentCounts } from '../types';
import { glassStyle } from '../styles';

type UrlInfo = {
  url: string;
  title: string;
  score: number;
  kept: boolean;
};

interface CurationExtractionProps {
  enrichmentCounts: EnrichmentCounts | undefined;
  curationDetails: Record<string, UrlInfo[]>;
  isExpanded: boolean;
  onToggleExpand: () => void;
  isResetting: boolean;
  loaderColor: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  company: '公司',
  industry: '行业',
  financial: '财务',
  news: '新闻',
  social_media: '社媒'
};

const CurationExtraction = ({
  enrichmentCounts,
  curationDetails,
  isExpanded,
  onToggleExpand,
  isResetting,
  loaderColor
}: CurationExtractionProps) => {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  const toggleCategory = (category: string) => {
    setExpandedCategory(prev => prev === category ? null : category);
  };

  return (
    <div 
      className={`${glassStyle.card} transition-all duration-300 ease-in-out ${
        isResetting ? 'opacity-0 transform -translate-y-4' : 'opacity-100 transform translate-y-0'
      }`}
    >
      <div 
        className="flex items-center justify-between cursor-pointer"
        onClick={onToggleExpand}
      >
        <h2 className="text-xl font-semibold text-gray-900">
          精选与内容强化
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
        isExpanded ? 'mt-4 max-h-[3000px] opacity-100' : 'max-h-0 opacity-0'
      }`}>
        {/* Summary cards */}
        <div className="grid grid-cols-5 gap-4 mb-4">
          {['company', 'industry', 'financial', 'news', 'social_media'].map((category) => {
            const counts = enrichmentCounts?.[category as keyof EnrichmentCounts];
            const details = curationDetails[category];
            const hasDetails = details && details.length > 0;
            return (
              <div 
                key={category} 
                className={`backdrop-blur-2xl bg-white/95 border rounded-xl p-3 shadow-none transition-all duration-200 ${
                  hasDetails ? 'cursor-pointer hover:border-[#468BFF]/50 hover:shadow-sm' : ''
                } ${expandedCategory === category ? 'border-[#468BFF] shadow-sm' : 'border-gray-200/50'}`}
                onClick={() => hasDetails && toggleCategory(category)}
              >
                <h3 className="text-sm font-medium text-gray-700 mb-2">{CATEGORY_LABELS[category] || category}</h3>
                <div className="text-gray-900">
                  <div className="text-2xl font-bold mb-1">
                    {counts ? (
                      <span className="text-[#468BFF]">
                        {counts.enriched}
                      </span>
                    ) : (
                      <Loader2 className="animate-spin h-6 w-6 mx-auto loader-icon" style={{ stroke: loaderColor }} />
                    )}
                  </div>
                  <div className="text-sm text-gray-600">
                    {counts ? (
                      `从 ${counts.total} 中精选`
                    ) : (
                      "等待中..."
                    )}
                  </div>
                  {hasDetails && (
                    <div className="text-xs text-[#468BFF] mt-1">
                      {expandedCategory === category ? '收起详情 ▲' : '查看链接 ▼'}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Expanded URL list for selected category */}
        {expandedCategory && curationDetails[expandedCategory] && (
          <div className="backdrop-blur-2xl bg-white/95 border border-gray-200/50 rounded-xl p-4 shadow-none">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-800">
                {CATEGORY_LABELS[expandedCategory]} - 所有链接 
                <span className="text-xs font-normal text-gray-500 ml-2">
                  (共 {curationDetails[expandedCategory].length} 条，
                  精选 {curationDetails[expandedCategory].filter(u => u.kept).length} 条)
                </span>
              </h3>
            </div>
            <div className="max-h-[400px] overflow-y-auto space-y-1.5">
              {curationDetails[expandedCategory].map((item, idx) => (
                <div 
                  key={idx}
                  className={`flex items-start gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                    item.kept 
                      ? 'bg-[#468BFF]/5 border border-[#468BFF]/20' 
                      : 'bg-gray-50 border border-gray-100 opacity-60'
                  }`}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    {item.kept ? (
                      <CheckCircle2 className="h-4 w-4 text-[#468BFF]" />
                    ) : (
                      <XCircle className="h-4 w-4 text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`font-medium truncate ${item.kept ? 'text-gray-900' : 'text-gray-500'}`}>
                        {item.title || '(无标题)'}
                      </span>
                      <span className={`flex-shrink-0 text-xs px-1.5 py-0.5 rounded ${
                        item.score >= 0.7 ? 'bg-green-100 text-green-700' :
                        item.score >= 0.4 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-600'
                      }`}>
                        {item.score.toFixed(2)}
                      </span>
                    </div>
                    <a 
                      href={item.url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-xs text-gray-400 hover:text-[#468BFF] truncate block mt-0.5 flex items-center gap-1"
                    >
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                      <span className="truncate">{item.url}</span>
                    </a>
                  </div>
                  {item.kept && (
                    <span className="flex-shrink-0 text-xs bg-[#468BFF] text-white px-2 py-0.5 rounded-full">
                      已选
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {!isExpanded && enrichmentCounts && (
        <div className="mt-2 text-sm text-gray-600">
          共 {Object.values(enrichmentCounts).reduce((acc, curr) => acc + curr.total, 0)} 篇文档中精选 {Object.values(enrichmentCounts).reduce((acc, curr) => acc + curr.enriched, 0)} 篇
        </div>
      )}
    </div>
  );
};

export default CurationExtraction; 