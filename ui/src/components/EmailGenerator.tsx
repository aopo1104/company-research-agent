import { useState } from 'react';
import { Mail, Loader2, Copy, Check, RefreshCw, Send } from 'lucide-react';

interface EmailGeneratorProps {
  reportContent: string;
  companyName: string;
  isResetting: boolean;
}

interface GeneratedEmail {
  subject: string;
  body: string;
  subjectAlternatives: string[];
  targetAudience: string;
  outreachAngle: string;
}

const API_URL = import.meta.env.VITE_API_URL || '/api';

const EmailGenerator = ({ reportContent, companyName, isResetting }: EmailGeneratorProps) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [email, setEmail] = useState<GeneratedEmail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);
  const [isCopiedBody, setIsCopiedBody] = useState(false);

  const generateEmail = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/generate-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_content: reportContent,
          company_name: companyName,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `请求失败 (${response.status})`);
      }

      const data = await response.json();
      setEmail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败');
    } finally {
      setIsGenerating(false);
    }
  };

  const copyEmail = async () => {
    if (!email) return;
    const fullText = `Subject: ${email.subject}\n\n${email.body}`;
    try {
      await navigator.clipboard.writeText(fullText);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      setError('复制失败');
    }
  };

  const copyBody = async () => {
    if (!email) return;
    try {
      await navigator.clipboard.writeText(email.body);
      setIsCopiedBody(true);
      setTimeout(() => setIsCopiedBody(false), 2000);
    } catch {
      setError('复制失败');
    }
  };

  return (
    <div
      className={`rounded-2xl border-2 border-dashed border-[#468BFF]/40 bg-gradient-to-br from-[#468BFF]/5 via-white to-purple-50 p-6 transition-all duration-300 ease-in-out ${
        isResetting ? 'opacity-0 transform -translate-y-4' : 'opacity-100 transform translate-y-0'
      } font-['DM_Sans'] ${email ? 'border-solid border-[#468BFF]/60 shadow-lg shadow-[#468BFF]/10' : ''}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#468BFF] to-purple-600 flex items-center justify-center shadow-sm">
            <Send className="h-4 w-4 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">开发信生成</h2>
            <p className="text-xs text-gray-500">基于分析报告，生成个性化 B2B 冷开发信</p>
          </div>
        </div>
        <button
          onClick={generateEmail}
          disabled={isGenerating}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-[#468BFF] to-[#2563eb] text-white hover:from-[#3a7ae0] hover:to-[#1d4ed8] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-semibold shadow-md shadow-[#468BFF]/20"
        >
          {isGenerating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              生成中...
            </>
          ) : email ? (
            <>
              <RefreshCw className="h-4 w-4" />
              重新生成
            </>
          ) : (
            <>
              <Mail className="h-4 w-4" />
              一键生成开发信
            </>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Generated Email */}
      {email && (
        <div className="space-y-4 mt-4">
          {/* Target & Angle tags */}
          <div className="flex flex-wrap gap-2">
            {email.targetAudience && (
              <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#468BFF]/10 border border-[#468BFF]/30 rounded-lg text-xs font-medium text-[#468BFF]">
                🎯 目标: {email.targetAudience}
              </span>
            )}
            {email.outreachAngle && (
              <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-50 border border-purple-200 rounded-lg text-xs font-medium text-purple-700">
                💡 角度: {email.outreachAngle}
              </span>
            )}
          </div>

          {/* Subject Line */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">SUBJECT LINE</span>
              <button
                onClick={copyEmail}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium text-gray-500 hover:text-[#468BFF] hover:bg-[#468BFF]/5 transition-all"
              >
                {isCopied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                {isCopied ? '已复制' : '复制全文'}
              </button>
            </div>
            <p className="text-base font-bold text-gray-900">{email.subject}</p>
            {email.subjectAlternatives && email.subjectAlternatives.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-gray-100">
                <span className="text-[10px] text-gray-400 self-center">备选:</span>
                {email.subjectAlternatives.map((alt, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 bg-gray-50 border border-gray-150 rounded text-gray-600">
                    {alt}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Email Body */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <Mail className="h-3.5 w-3.5 text-gray-400" />
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">EMAIL BODY</span>
              </div>
              <button
                onClick={copyBody}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium text-gray-500 hover:text-[#468BFF] hover:bg-[#468BFF]/5 transition-all"
              >
                {isCopiedBody ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                {isCopiedBody ? '已复制' : '复制正文'}
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans leading-7">
              {email.body}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmailGenerator;
