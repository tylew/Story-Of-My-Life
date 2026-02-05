import { useState, useEffect, useCallback, useMemo } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import Table from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import {
  Bold, Italic, Strikethrough, Code, List, ListOrdered,
  Quote, Heading1, Heading2, Heading3, Link2, Table as TableIcon,
  Undo, Redo, FileText, Eye
} from 'lucide-react'

// Simple Markdown renderer for read-only view
function MarkdownRenderer({ content }) {
  // Very basic markdown to HTML conversion for display
  const html = useMemo(() => {
    if (!content) return ''
    
    let result = content
    
    // Headers
    result = result.replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-4 mb-2 text-white">$1</h3>')
    result = result.replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-6 mb-3 text-white">$1</h2>')
    result = result.replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-6 mb-4 text-white">$1</h1>')
    
    // Bold and italic
    result = result.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-white">$1</strong>')
    result = result.replace(/\*(.+?)\*/g, '<em class="italic">$1</em>')
    result = result.replace(/_(.+?)_/g, '<em class="italic text-slate-300">$1</em>')
    
    // Code
    result = result.replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-slate-dark text-neon-cyan font-mono text-sm">$1</code>')
    
    // Links
    result = result.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-neon-purple hover:underline">$1</a>')
    
    // Wikilinks
    result = result.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '<span class="text-neon-cyan">$2</span>')
    result = result.replace(/\[\[([^\]]+)\]\]/g, '<span class="text-neon-cyan">$1</span>')
    
    // Lists
    result = result.replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    result = result.replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
    
    // Tables
    result = result.replace(/\|(.+)\|/g, (match, content) => {
      const cells = content.split('|').map(cell => cell.trim())
      const isHeaderSep = cells.every(c => c.match(/^-+$/))
      if (isHeaderSep) return ''
      const cellHtml = cells.map(c => `<td class="border border-slate-700 px-3 py-2">${c}</td>`).join('')
      return `<tr>${cellHtml}</tr>`
    })
    
    // Blockquotes
    result = result.replace(/^> (.+)$/gm, '<blockquote class="border-l-2 border-neon-purple pl-4 my-2 text-slate-300 italic">$1</blockquote>')
    
    // Paragraphs (simple)
    result = result.split('\n\n').map(para => {
      if (para.startsWith('<')) return para
      if (!para.trim()) return ''
      return `<p class="mb-3">${para.replace(/\n/g, '<br/>')}</p>`
    }).join('\n')
    
    return result
  }, [content])
  
  return (
    <div 
      className="prose prose-invert max-w-none text-slate-300"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

// Toolbar button component
function ToolbarButton({ onClick, isActive, disabled, title, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`p-1.5 rounded transition-colors ${
        isActive
          ? 'bg-neon-purple/30 text-neon-purple'
          : 'hover:bg-slate-dark text-slate-400 hover:text-white'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {children}
    </button>
  )
}

export default function DocumentEditor({ content, onChange, readOnly = false }) {
  const [viewMode, setViewMode] = useState(readOnly ? 'preview' : 'editor')

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-neon-purple hover:underline cursor-pointer',
        },
      }),
      Placeholder.configure({
        placeholder: 'Start writing...',
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: content || '',
    editable: !readOnly && viewMode === 'editor',
    onUpdate: ({ editor }) => {
      // Convert to markdown-ish format for storage
      const html = editor.getHTML()
      // For now, just pass the HTML - in production you'd convert to markdown
      onChange?.(editor.getText())
    },
  })

  // Update editor content when prop changes
  useEffect(() => {
    if (editor && content !== editor.getText()) {
      // For simplicity, just set the content as text
      // In production, you'd parse markdown to ProseMirror document
      editor.commands.setContent(content || '')
    }
  }, [content, editor])

  // Update editable state
  useEffect(() => {
    if (editor) {
      editor.setEditable(!readOnly && viewMode === 'editor')
    }
  }, [editor, readOnly, viewMode])

  if (readOnly) {
    return (
      <div className="document-content">
        <MarkdownRenderer content={content} />
      </div>
    )
  }

  const addLink = () => {
    const url = window.prompt('Enter URL:')
    if (url) {
      editor?.chain().focus().setLink({ href: url }).run()
    }
  }

  const addTable = () => {
    editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-1 p-2 border-b border-slate-700 bg-slate-dark/50 flex-wrap">
        {/* View toggle */}
        <div className="flex items-center gap-1 mr-2 pr-2 border-r border-slate-700">
          <ToolbarButton
            onClick={() => setViewMode('editor')}
            isActive={viewMode === 'editor'}
            title="Editor"
          >
            <FileText className="w-4 h-4" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => setViewMode('preview')}
            isActive={viewMode === 'preview'}
            title="Preview"
          >
            <Eye className="w-4 h-4" />
          </ToolbarButton>
        </div>

        {viewMode === 'editor' && (
          <>
            {/* History */}
            <ToolbarButton
              onClick={() => editor?.chain().focus().undo().run()}
              disabled={!editor?.can().undo()}
              title="Undo (⌘Z)"
            >
              <Undo className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().redo().run()}
              disabled={!editor?.can().redo()}
              title="Redo (⌘⇧Z)"
            >
              <Redo className="w-4 h-4" />
            </ToolbarButton>

            <div className="w-px h-5 bg-slate-700 mx-1" />

            {/* Headings */}
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
              isActive={editor?.isActive('heading', { level: 1 })}
              title="Heading 1"
            >
              <Heading1 className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
              isActive={editor?.isActive('heading', { level: 2 })}
              title="Heading 2"
            >
              <Heading2 className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
              isActive={editor?.isActive('heading', { level: 3 })}
              title="Heading 3"
            >
              <Heading3 className="w-4 h-4" />
            </ToolbarButton>

            <div className="w-px h-5 bg-slate-700 mx-1" />

            {/* Formatting */}
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleBold().run()}
              isActive={editor?.isActive('bold')}
              title="Bold (⌘B)"
            >
              <Bold className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleItalic().run()}
              isActive={editor?.isActive('italic')}
              title="Italic (⌘I)"
            >
              <Italic className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleStrike().run()}
              isActive={editor?.isActive('strike')}
              title="Strikethrough"
            >
              <Strikethrough className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleCode().run()}
              isActive={editor?.isActive('code')}
              title="Inline Code"
            >
              <Code className="w-4 h-4" />
            </ToolbarButton>

            <div className="w-px h-5 bg-slate-700 mx-1" />

            {/* Lists */}
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleBulletList().run()}
              isActive={editor?.isActive('bulletList')}
              title="Bullet List"
            >
              <List className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleOrderedList().run()}
              isActive={editor?.isActive('orderedList')}
              title="Numbered List"
            >
              <ListOrdered className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={() => editor?.chain().focus().toggleBlockquote().run()}
              isActive={editor?.isActive('blockquote')}
              title="Quote"
            >
              <Quote className="w-4 h-4" />
            </ToolbarButton>

            <div className="w-px h-5 bg-slate-700 mx-1" />

            {/* Extras */}
            <ToolbarButton
              onClick={addLink}
              isActive={editor?.isActive('link')}
              title="Add Link"
            >
              <Link2 className="w-4 h-4" />
            </ToolbarButton>
            <ToolbarButton
              onClick={addTable}
              title="Insert Table"
            >
              <TableIcon className="w-4 h-4" />
            </ToolbarButton>
          </>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {viewMode === 'editor' ? (
          <EditorContent 
            editor={editor} 
            className="prose prose-invert max-w-none min-h-[200px] focus:outline-none [&_.ProseMirror]:focus:outline-none [&_.ProseMirror]:min-h-[200px]"
          />
        ) : (
          <MarkdownRenderer content={content} />
        )}
      </div>
    </div>
  )
}

