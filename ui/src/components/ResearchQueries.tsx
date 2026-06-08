import { ChevronDown, ChevronUp } from 'lucide-react';
import type { ResearchQueriesProps } from '../types';
import { fadeInAnimation } from '../styles';

const ResearchQueries = ({
  queries,
  streamingQueries,
  isExpanded,
  onToggleExpand,
  isResetting,
  glassStyle
}: ResearchQueriesProps) => {
  const glassCardStyle = `${glassStyle} rounded-2xl p-6`;

  return (
    <div 
      className={`${glassCardStyle} ${fadeInAnimation.fadeIn} ${isResetting ? 'opacity-0 transform -translate-y-4' : 'opacity-100 transform translate-y-0'} font-['DM_Sans']`}
    >
      <div 
        className="flex items-center justify-between cursor-pointer"
        onClick={onToggleExpand}
      >
        <h2 className="text-xl font-semibold text-gray-900">
          已生成搜索查询
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
        isExpanded ? 'mt-4 max-h-[9999px] opacity-100' : 'max-h-0 opacity-0'
      }`}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {['company', 'news', 'social_media'].map((category) => (
            <div key={category} className={`${glassStyle} rounded-xl p-3`}>
              <h3 className="text-base font-medium text-gray-900 mb-3">
                {({'company':'公司','news':'新闻','social_media':'社媒'} as Record<string,string>)[category] || category}查询
              </h3>
              <div className="space-y-2">
                {/* Show streaming queries first */}
                {Object.entries(streamingQueries)
                  .filter(([key]) => key.startsWith(category))
                  .map(([key, query]) => (
                    <div key={key} className="backdrop-filter backdrop-blur-lg bg-white/80 border border-[#468BFF]/30 rounded-lg p-2">
                      <span className="text-gray-600 text-sm leading-relaxed whitespace-pre-wrap break-words">{query.text}</span>
                      <span className="animate-pulse ml-1 text-[#8FBCFA]">|</span>
                    </div>
                  ))}
                {/* Then show completed queries */}
                {queries
                  .filter((q) => q.category.startsWith(category))
                  .map((query, idx) => (
                    <div key={idx} className="backdrop-filter backdrop-blur-lg bg-white/80 border border-gray-200 rounded-lg p-2">
                      <span className="text-gray-600 text-sm leading-relaxed whitespace-pre-wrap break-words">{query.text}</span>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {!isExpanded && (
        <div className="mt-2 text-sm text-gray-600">
          已在 {['company', 'news', 'social_media'].length} 个类别中生成 {queries.length} 条查询
        </div>
      )}
    </div>
  );
};

export default ResearchQueries; 