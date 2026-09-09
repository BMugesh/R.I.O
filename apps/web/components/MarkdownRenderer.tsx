'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import { Check, Copy } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
  isUser?: boolean;
}

function preprocessLaTeX(text: string): string {
  if (!text) return '';

  let formatted = text.replace(/\r\n/g, '\n');

  // 1. Replace \[ ... \] with $$ ... $$
  formatted = formatted.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => `\n$$\n${math.trim()}\n$$\n`);

  // 2. Replace \( ... \) with $ ... $
  formatted = formatted.replace(/\\\(([\s\S]*?)\\\)/g, (_, math) => `$${math.trim()}$`);

  // 3. Wrap standalone LaTeX environments in $$ ONLY if they are not already inside a math block
  const parts = formatted.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g);
  formatted = parts
    .map((part) => {
      if (part.startsWith('$')) {
        return part;
      }
      return part.replace(
        /(\\begin\{(?:matrix|bmatrix|pmatrix|vmatrix|Vmatrix|aligned|cases|equation|array)\}[\s\S]*?\\end\{(?:matrix|bmatrix|pmatrix|vmatrix|Vmatrix|aligned|cases|equation|array)\})/g,
        '\n$$\n$1\n$$\n'
      );
    })
    .join('');

  return formatted;
}

const CodeBlock: React.FC<{ language?: string; value: string }> = ({ language, value }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-3 rounded-xl overflow-hidden border border-slate-800 bg-slate-950 font-mono text-xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-900/80 border-b border-slate-800 text-[11px] text-slate-400">
        <span className="font-semibold uppercase tracking-wider text-cyan-400">{language || 'text'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-slate-200 transition-colors"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 text-[10px]">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span className="text-[10px]">Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-slate-200 leading-relaxed text-xs">
        <code>{value}</code>
      </pre>
    </div>
  );
};

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, isUser }) => {
  if (isUser) {
    return <p className="whitespace-pre-wrap leading-relaxed">{content}</p>;
  }

  const processed = preprocessLaTeX(content);

  return (
    <div className="prose prose-invert prose-sm max-w-none text-slate-200 leading-relaxed space-y-2.5 break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { output: 'htmlAndMathml', throwOnError: false }]]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-base font-bold text-white mt-4 mb-2 pb-1 border-b border-slate-800 flex items-center gap-2">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-bold text-cyan-300 mt-3.5 mb-1.5 flex items-center gap-2">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-xs font-semibold text-slate-100 mt-2.5 mb-1 uppercase tracking-wider">
              {children}
            </h3>
          ),
          p: ({ children }) => <p className="mb-2 leading-relaxed text-slate-200">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          em: ({ children }) => <em className="text-cyan-200/90 italic">{children}</em>,
          ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-2 text-slate-300 pl-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside space-y-1.5 my-2 text-slate-300 pl-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed text-slate-300">{children}</li>,
          hr: () => <hr className="my-3 border-slate-800" />,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-cyan-500 pl-3 py-1 my-2 text-slate-400 bg-slate-900/40 rounded-r-lg italic text-xs">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full text-xs text-left border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-900 text-slate-300 uppercase font-mono text-[11px] border-b border-slate-800">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-slate-800/60">{children}</tbody>,
          tr: ({ children }) => <tr className="hover:bg-slate-900/40 transition-colors">{children}</tr>,
          th: ({ children }) => <th className="px-3 py-2 font-semibold">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 text-slate-300">{children}</td>,
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            const codeString = String(children).replace(/\n$/, '');

            if (!inline && match) {
              return <CodeBlock language={match[1]} value={codeString} />;
            } else if (!inline && codeString.includes('\n')) {
              return <CodeBlock language="" value={codeString} />;
            }
            return (
              <code className="px-1.5 py-0.5 rounded-md bg-slate-800/90 text-cyan-300 font-mono text-[11px] border border-slate-700/50" {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
};
