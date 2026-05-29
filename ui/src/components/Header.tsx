import { Target } from 'lucide-react';

interface HeaderProps {
  glassStyle: string;
}

const Header = ({ glassStyle }: HeaderProps) => {
  return (
    <div className="relative mb-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#468BFF] to-[#2563eb] flex items-center justify-center shadow-md">
            <Target className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 font-['DM_Sans'] tracking-tight">
              LoctekMotion 推广研究平台
            </h1>
            <p className="text-xs text-gray-500 font-['DM_Sans']">
              目标客户分析 → 推广策略 → 开发信生成
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="px-2 py-1 bg-gray-100 rounded text-gray-500">Powered by Azure OpenAI + Tavily</span>
        </div>
      </div>
    </div>
  );
};

export default Header; 