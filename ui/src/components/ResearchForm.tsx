import { useState, useRef, useEffect } from 'react';
import { Building2, Factory, Globe, Loader2, Search, History, X, Sparkles } from 'lucide-react';
import LocationInput from './LocationInput';
import ExamplePopup from './ExamplePopup';
import type { ExampleCompany } from './ExamplePopup';

const API_URL = import.meta.env.VITE_API_URL || '/companyResearchAPI';
const HISTORY_KEY = 'research_history';
const MAX_HISTORY = 10;

interface HistoryEntry {
  companyName: string;
  companyUrl: string;
  companyHq: string;
  companyIndustry: string;
  timestamp: number;
}

function loadHistory(): HistoryEntry[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveToHistory(entry: Omit<HistoryEntry, 'timestamp'>) {
  const history = loadHistory().filter(h => h.companyUrl !== entry.companyUrl);
  history.unshift({ ...entry, timestamp: Date.now() });
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
}

function removeFromHistory(companyUrl: string) {
  const history = loadHistory().filter(h => h.companyUrl !== companyUrl);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

interface FormData {
  companyName: string;
  companyUrl: string;
  companyHq: string;
  companyIndustry: string;
  mode?: 'quick' | 'deep';
}

interface ResearchFormProps {
  onSubmit: (formData: FormData) => Promise<void>;
  isResearching: boolean;
  glassStyle: {
    card: string;
    input: string;
  };
  loaderColor: string;
}

const ResearchForm = ({
  onSubmit,
  isResearching,
  glassStyle,
  loaderColor
}: ResearchFormProps) => {
  const [formData, setFormData] = useState<FormData>({
    companyName: "DIEHL + NICKEL GmbH",
    companyUrl: "https://www.diehlundnickel.de/",
    companyHq: "Frankfurter Straße 26, 65779 Kelkheim",
    companyIndustry: "",
  });

  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);
  const [showHistory, setShowHistory] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  
  // Animation states
  const [showExampleSuggestion, setShowExampleSuggestion] = useState(true);
  const [isExampleAnimating, setIsExampleAnimating] = useState(false);
  
  // Refs for form fields for animation
  const formRef = useRef<HTMLDivElement>(null);
  const exampleRef = useRef<HTMLDivElement>(null);
  
  // Hide example suggestion when form is filled
  useEffect(() => {
    if (formData.companyUrl) {
      setShowExampleSuggestion(false);
    } else if (!isExampleAnimating) {
      setShowExampleSuggestion(true);
    }
  }, [formData.companyUrl, isExampleAnimating]);

  // Close history dropdown when clicking outside
  useEffect(() => {
    if (!showHistory) return;
    const handler = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('[data-history-container]')) {
        setShowHistory(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showHistory]);

  // Keep user input after completion/errors; only restore the example hint when idle and URL is empty.
  useEffect(() => {
    if (!isResearching && !isExampleAnimating && !formData.companyUrl) {
      setShowExampleSuggestion(true);
    }
  }, [isResearching, isExampleAnimating, formData.companyUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    saveToHistory(formData);
    setHistory(loadHistory());
    await onSubmit({ ...formData, mode: 'deep' });
  };

  const handleQuickSubmit = async () => {
    if (!formData.companyUrl || isResearching) return;
    saveToHistory(formData);
    setHistory(loadHistory());
    await onSubmit({ ...formData, mode: 'quick' });
  };

  const fillFromHistory = (entry: HistoryEntry) => {
    setFormData({
      companyName: entry.companyName,
      companyUrl: entry.companyUrl,
      companyHq: entry.companyHq,
      companyIndustry: entry.companyIndustry,
    });
    setShowHistory(false);
  };

  const deleteFromHistory = (e: React.MouseEvent, companyUrl: string) => {
    e.stopPropagation();
    removeFromHistory(companyUrl);
    setHistory(loadHistory());
  };
  
  const fillExampleData = (example: ExampleCompany) => {
    // Start animation
    setIsExampleAnimating(true);
    
    // Animate the suggestion moving into the form
    if (exampleRef.current && formRef.current) {
      const exampleRect = exampleRef.current.getBoundingClientRect();
      const formRect = formRef.current.getBoundingClientRect();
      
      // Calculate the distance to move
      const moveX = formRect.left + 20 - exampleRect.left;
      const moveY = formRect.top + 20 - exampleRect.top;
      
      // Apply animation
      exampleRef.current.style.transform = `translate(${moveX}px, ${moveY}px) scale(0.6)`;
      exampleRef.current.style.opacity = '0';
    }
    
    // Fill in form data after a short delay for animation
    setTimeout(() => {
      const newFormData = {
        companyName: example.name,
        companyUrl: example.url,
        companyHq: example.hq,
        companyIndustry: example.industry
      };
      
      // Update form data
      setFormData(newFormData);
      
      // Start research automatically (only if not already researching)
      if (!isResearching) {
        onSubmit(newFormData);
      }
      
      setIsExampleAnimating(false);
    }, 500);
  };

  const handleExtractFromURL = async () => {
    if (!formData.companyUrl.trim()) {
      setExtractionError('请输入公司网址');
      return;
    }

    setIsExtracting(true);
    setExtractionError(null);
    setFormData((prev) => ({
      ...prev,
      companyName: '',
      companyIndustry: '',
      companyHq: '',
    }));

    try {
      const response = await fetch(`${API_URL}/extract-company-info`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_url: formData.companyUrl
        }),
      });

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        setFormData(prev => ({
          ...prev,
          companyName: data.company_name || '',
          companyIndustry: data.industry || '',
          companyHq: data.hq_location || '',
        }));
        setExtractionError(null);
      } else {
        setExtractionError(data.message || '信息提取失败');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '网络错误';
      setExtractionError(`提取失败: ${message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div className="relative" ref={formRef}>
      {/* Example Suggestion */}
      <ExamplePopup 
        visible={showExampleSuggestion}
        onExampleSelect={fillExampleData}
        glassStyle={glassStyle}
        exampleRef={exampleRef}
      />

      {/* Main Form */}
      <div className={`${glassStyle.card} backdrop-blur-2xl bg-white/90 border-gray-200/50 shadow-xl`}>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Company URL - First, Required */}
            <div className="relative group">
              <label
                htmlFor="companyUrl"
                className="block text-base font-medium text-gray-700 mb-2.5 transition-all duration-200 group-hover:text-gray-900 font-['DM_Sans']"
              >
                公司网址 <span className="text-gray-900/70">*</span>
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <div className="absolute inset-0 bg-gradient-to-r from-gray-50/0 via-gray-100/50 to-gray-50/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-lg"></div>
                  <Globe className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 stroke-[#468BFF] transition-all duration-200 group-hover:stroke-[#8FBCFA] z-10" strokeWidth={1.5} />
                  <input
                    required
                    id="companyUrl"
                    type="text"
                    value={formData.companyUrl}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        companyUrl: e.target.value,
                      }))
                    }
                    className={`${glassStyle.input} transition-all duration-300 focus:border-[#468BFF]/50 focus:ring-1 focus:ring-[#468BFF]/50 group-hover:border-[#468BFF]/30 bg-white/80 backdrop-blur-sm text-lg py-4 pl-12 font-['DM_Sans']`}
                    placeholder="例如 example.com"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleExtractFromURL}
                  disabled={isExtracting || !formData.companyUrl.trim()}
                  className="relative group/btn overflow-hidden rounded-lg bg-white border border-gray-200 transition-all duration-300 hover:border-[#468BFF]/40 hover:bg-[#468BFF]/5 disabled:opacity-50 disabled:cursor-not-allowed px-4 font-['DM_Sans'] min-w-fit whitespace-nowrap"
                  title="从网址识别公司信息（名称、行业、地址）"
                >
                  <div className="relative flex items-center justify-center py-3 gap-1.5">
                    {isExtracting ? (
                      <>
                        <Loader2 className="animate-spin h-4 w-4" style={{ stroke: loaderColor }} />
                        <span className="text-sm font-medium text-gray-600">识别中...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 text-[#468BFF] transition-all duration-200 group-hover/btn:text-[#8FBCFA]" />
                        <span className="text-sm font-medium text-gray-600 group-hover/btn:text-[#468BFF]">识别</span>
                      </>
                    )}
                  </div>
                </button>
              </div>
              {extractionError && (
                <p className="text-sm text-red-500 mt-2">⚠️ {extractionError}</p>
              )}
            </div>

            {/* Company Name - Optional */}
            <div className="relative group">
              <label
                htmlFor="companyName"
                className="block text-base font-medium text-gray-700 mb-2.5 transition-all duration-200 group-hover:text-gray-900 font-['DM_Sans']"
              >
                公司名称
              </label>
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-gray-50/0 via-gray-100/50 to-gray-50/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-lg"></div>
                <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 stroke-[#468BFF] transition-all duration-200 group-hover:stroke-[#8FBCFA] z-10" strokeWidth={1.5} />
                <input
                  id="companyName"
                  type="text"
                  value={formData.companyName}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      companyName: e.target.value,
                    }))
                  }
                  className={`${glassStyle.input} transition-all duration-300 focus:border-[#468BFF]/50 focus:ring-1 focus:ring-[#468BFF]/50 group-hover:border-[#468BFF]/30 bg-white/80 backdrop-blur-sm text-lg py-4 pl-12 font-['DM_Sans']`}
                  placeholder="可选，留空则自动从网址识别"
                />
              </div>
            </div>

            {/* Company HQ */}
            <div className="relative group">
              <label
                htmlFor="companyHq"
                className="block text-base font-medium text-gray-700 mb-2.5 transition-all duration-200 group-hover:text-gray-900 font-['DM_Sans']"
              >
                公司总部
              </label>
              <LocationInput
                value={formData.companyHq}
                onChange={(value) =>
                  setFormData((prev) => ({
                    ...prev,
                    companyHq: value,
                  }))
                }
                className={`${glassStyle.input} transition-all duration-300 focus:border-[#468BFF]/50 focus:ring-1 focus:ring-[#468BFF]/50 group-hover:border-[#468BFF]/30 bg-white/80 backdrop-blur-sm text-lg py-4 pl-12 font-['DM_Sans']`}
              />
            </div>

            {/* Company Industry */}
            <div className="relative group">
              <label
                htmlFor="companyIndustry"
                className="block text-base font-medium text-gray-700 mb-2.5 transition-all duration-200 group-hover:text-gray-900 font-['DM_Sans']"
              >
                所属行业
              </label>
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-gray-50/0 via-gray-100/50 to-gray-50/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-lg"></div>
                <Factory className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 stroke-[#468BFF] transition-all duration-200 group-hover:stroke-[#8FBCFA] z-10" strokeWidth={1.5} />
                <input
                  id="companyIndustry"
                  type="text"
                  value={formData.companyIndustry}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      companyIndustry: e.target.value,
                    }))
                  }
                  className={`${glassStyle.input} transition-all duration-300 focus:border-[#468BFF]/50 focus:ring-1 focus:ring-[#468BFF]/50 group-hover:border-[#468BFF]/30 bg-white/80 backdrop-blur-sm text-lg py-4 pl-12 font-['DM_Sans']`}
                  placeholder="例如 科技、医疗"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-center gap-3 pt-2">
            {/* History button */}
            {history.length > 0 && (
              <div className="relative" data-history-container>
                <button
                  type="button"
                  onClick={() => setShowHistory(v => !v)}
                  className="relative group overflow-hidden rounded-lg bg-white border border-gray-200 transition-all duration-300 hover:border-[#468BFF]/40 hover:bg-[#468BFF]/5 px-4 font-['DM_Sans']"
                  title="查询记录"
                >
                  <div className="relative flex items-center justify-center py-3 gap-1.5">
                    <History className="h-4 w-4 text-gray-500 group-hover:text-[#468BFF]" />
                    <span className="text-sm font-medium text-gray-600 group-hover:text-[#468BFF]">记录</span>
                    <span className="ml-0.5 text-xs bg-[#468BFF]/10 text-[#468BFF] rounded-full px-1.5 py-0.5 font-semibold">{history.length}</span>
                  </div>
                </button>
                {showHistory && (
                  <div className="absolute left-0 top-full mt-2 z-50 w-72 rounded-xl bg-white border border-gray-200 shadow-xl overflow-hidden">
                    <div className="px-3 py-2 border-b border-gray-100 text-xs text-gray-400 font-medium">最近查询记录（点击一键填充）</div>
                    <ul className="max-h-64 overflow-y-auto divide-y divide-gray-50">
                      {history.map(entry => (
                        <li
                          key={entry.companyUrl || entry.companyName}
                          className="flex items-center justify-between px-3 py-2.5 hover:bg-[#468BFF]/5 cursor-pointer group/item transition-colors"
                          onClick={() => fillFromHistory(entry)}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-gray-800 truncate">{entry.companyName || entry.companyUrl}</p>
                            <p className="text-xs text-gray-400 truncate">{entry.companyUrl || entry.companyHq || '—'}</p>
                          </div>
                          <button
                            type="button"
                            onClick={(e) => deleteFromHistory(e, entry.companyUrl)}
                            className="ml-2 p-1 rounded text-gray-300 hover:text-red-400 opacity-0 group-hover/item:opacity-100 transition-all"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={handleQuickSubmit}
              disabled={isResearching || !formData.companyUrl}
              className="relative group overflow-hidden rounded-lg bg-white border border-gray-200 transition-all duration-300 hover:border-[#468BFF]/40 hover:bg-[#468BFF]/5 disabled:opacity-50 disabled:cursor-not-allowed px-6 font-['DM_Sans']"
            >
              <div className="relative flex items-center justify-center py-3">
                {isResearching ? (
                  <>
                    <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4" style={{ stroke: loaderColor }} />
                    <span className="text-sm font-medium text-gray-600">处理中...</span>
                  </>
                ) : (
                  <>
                    <Search className="-ml-1 mr-2 h-4 w-4 text-[#468BFF]" />
                    <span className="text-sm font-medium text-gray-700">快速分析</span>
                  </>
                )}
              </div>
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#468BFF]/20"></div>
            </button>

            <button
              type="submit"
              disabled={isResearching || !formData.companyUrl}
              className="relative group overflow-hidden rounded-lg bg-gradient-to-r from-[#468BFF] to-[#2563eb] text-white transition-all duration-300 hover:from-[#3a7ae0] hover:to-[#1d4ed8] disabled:opacity-50 disabled:cursor-not-allowed px-8 font-['DM_Sans'] shadow-md shadow-[#468BFF]/20"
            >
              <div className="relative flex items-center justify-center py-3">
                {isResearching ? (
                  <>
                    <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" />
                    <span className="text-sm font-semibold">深度研究中...</span>
                  </>
                ) : (
                  <>
                    <Search className="-ml-1 mr-2 h-4 w-4" />
                    <span className="text-sm font-semibold">深度研究</span>
                  </>
                )}
              </div>
            </button>
          </div>

          <div className="flex justify-center gap-6 text-[11px] text-gray-400">
            <span>快速分析: 单次LLM调用，约30秒</span>
            <span>深度研究: 多轮搜索+分析，约90秒</span>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ResearchForm; 