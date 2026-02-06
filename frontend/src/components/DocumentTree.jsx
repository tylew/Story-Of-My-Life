import { useState, useEffect } from 'react'
import { 
  ChevronRight, 
  ChevronDown, 
  FileText, 
  Folder, 
  FolderOpen,
  User, 
  Briefcase, 
  Target, 
  Calendar,
  Link2,
  Tag,
  AlertCircle
} from 'lucide-react'

const API_BASE = '/api'

// Entity type icons
const ENTITY_TYPE_ICONS = {
  person: User,
  project: Briefcase,
  goal: Target,
  event: Calendar,
  period: Calendar,
  organization: Briefcase,
}

const ENTITY_TYPE_COLORS = {
  person: '#8B5CF6',
  project: '#10B981',
  goal: '#F59E0B',
  event: '#EC4899',
  period: '#6366F1',
  organization: '#14B8A6',
}

/**
 * DocumentTree - Hierarchical sidebar for document navigation
 * 
 * Structure:
 * - All Documents (count)
 *   - By Entity Type
 *     - People
 *       - Person Name (count)
 *         - Folders
 *         - Documents
 *     - Projects
 *     - ...
 *   - Relationships
 *     - Entity A ↔ Entity B (count)
 *   - By Tag
 *     - #tag-name (count)
 *   - Orphan Documents
 */
export default function DocumentTree({
  summary = null,
  selectedPath = null,
  onSelect,
  className = '',
}) {
  const [expanded, setExpanded] = useState({
    root: true,
    byType: true,
  })
  const [folderTrees, setFolderTrees] = useState({})

  // Fetch folder trees for entities when expanded
  const fetchFolderTree = async (entityId) => {
    if (folderTrees[entityId]) return
    
    try {
      const res = await fetch(`${API_BASE}/folders?entity_id=${entityId}`)
      const data = await res.json()
      setFolderTrees(prev => ({ ...prev, [entityId]: data.tree || [] }))
    } catch (e) {
      console.error('Failed to fetch folder tree:', e)
    }
  }

  const toggleExpand = (key) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSelect = (type, data = {}) => {
    onSelect?.({ type, ...data })
  }

  // Group entities by type
  const entitiesByType = {}
  if (summary?.by_entity) {
    for (const entity of summary.by_entity) {
      const type = entity.type || 'unknown'
      if (!entitiesByType[type]) {
        entitiesByType[type] = []
      }
      entitiesByType[type].push(entity)
    }
  }

  return (
    <div className={`text-sm ${className}`}>
      {/* Root: All Documents */}
      <TreeNode
        icon={FileText}
        label="All Documents"
        count={summary?.total_count || 0}
        expanded={expanded.root}
        onToggle={() => toggleExpand('root')}
        onClick={() => handleSelect('all')}
        selected={selectedPath?.type === 'all'}
        level={0}
      />

      {expanded.root && (
        <>
          {/* By Entity Type */}
          <TreeNode
            icon={Folder}
            label="By Entity Type"
            expanded={expanded.byType}
            onToggle={() => toggleExpand('byType')}
            level={1}
          />

          {expanded.byType && (
            <>
              {Object.entries(ENTITY_TYPE_ICONS).map(([type, Icon]) => {
                const entities = entitiesByType[type] || []
                const typeCount = summary?.by_entity_type?.[type] || 0
                if (typeCount === 0 && entities.length === 0) return null

                const typeKey = `type-${type}`
                return (
                  <div key={type}>
                    <TreeNode
                      icon={Icon}
                      iconColor={ENTITY_TYPE_COLORS[type]}
                      label={type.charAt(0).toUpperCase() + type.slice(1) + 's'}
                      count={typeCount}
                      expanded={expanded[typeKey]}
                      onToggle={() => toggleExpand(typeKey)}
                      onClick={() => handleSelect('entityType', { entityType: type })}
                      selected={selectedPath?.type === 'entityType' && selectedPath?.entityType === type}
                      level={2}
                    />

                    {expanded[typeKey] && entities.map(entity => {
                      const entityKey = `entity-${entity.id}`
                      return (
                        <div key={entity.id}>
                          <TreeNode
                            icon={Icon}
                            iconColor={ENTITY_TYPE_COLORS[type]}
                            label={entity.name || 'Unknown'}
                            count={entity.count}
                            expanded={expanded[entityKey]}
                            onToggle={() => {
                              toggleExpand(entityKey)
                              if (!expanded[entityKey]) {
                                fetchFolderTree(entity.id)
                              }
                            }}
                            onClick={() => handleSelect('entity', { entityId: entity.id, entityType: type })}
                            selected={selectedPath?.type === 'entity' && selectedPath?.entityId === entity.id}
                            level={3}
                          />

                          {expanded[entityKey] && (
                            <FolderTreeView
                              tree={folderTrees[entity.id] || []}
                              entityId={entity.id}
                              level={4}
                              selectedPath={selectedPath}
                              onSelect={handleSelect}
                            />
                          )}
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </>
          )}

          {/* Relationships */}
          {(summary?.by_relationship?.length || 0) > 0 && (
            <>
              <TreeNode
                icon={Link2}
                iconColor="#06B6D4"
                label="Relationships"
                count={summary.by_relationship.reduce((acc, r) => acc + r.document_count, 0)}
                expanded={expanded.relationships}
                onToggle={() => toggleExpand('relationships')}
                onClick={() => handleSelect('relationships')}
                selected={selectedPath?.type === 'relationships'}
                level={1}
              />

              {expanded.relationships && summary.by_relationship.map(rel => (
                <TreeNode
                  key={rel.id}
                  icon={Link2}
                  iconColor="#06B6D4"
                  label={`${rel.source_name || 'Unknown'} ↔ ${rel.target_name || 'Unknown'}`}
                  count={rel.document_count}
                  onClick={() => handleSelect('relationship', { relationshipId: rel.id })}
                  selected={selectedPath?.type === 'relationship' && selectedPath?.relationshipId === rel.id}
                  level={2}
                />
              ))}
            </>
          )}

          {/* By Tag */}
          {Object.keys(summary?.by_tag || {}).length > 0 && (
            <>
              <TreeNode
                icon={Tag}
                iconColor="#A855F7"
                label="By Tag"
                count={Object.values(summary.by_tag).reduce((a, b) => a + b, 0)}
                expanded={expanded.byTag}
                onToggle={() => toggleExpand('byTag')}
                level={1}
              />

              {expanded.byTag && Object.entries(summary.by_tag).map(([tagName, count]) => (
                <TreeNode
                  key={tagName}
                  icon={Tag}
                  iconColor="#A855F7"
                  label={`#${tagName}`}
                  count={count}
                  onClick={() => handleSelect('tag', { tag: tagName })}
                  selected={selectedPath?.type === 'tag' && selectedPath?.tag === tagName}
                  level={2}
                />
              ))}
            </>
          )}

          {/* Orphan Documents */}
          {(summary?.orphan_count || 0) > 0 && (
            <TreeNode
              icon={AlertCircle}
              iconColor="#EF4444"
              label="Unorganized"
              count={summary.orphan_count}
              onClick={() => handleSelect('orphan')}
              selected={selectedPath?.type === 'orphan'}
              level={1}
            />
          )}
        </>
      )}
    </div>
  )
}

/**
 * TreeNode - Single node in the tree
 */
function TreeNode({
  icon: Icon,
  iconColor,
  label,
  count,
  expanded,
  onToggle,
  onClick,
  selected,
  level = 0,
}) {
  const hasChildren = onToggle !== undefined
  const paddingLeft = level * 16 + 8

  return (
    <div
      className={`
        flex items-center gap-1.5 py-1.5 px-2 cursor-pointer
        hover:bg-slate-800 transition-colors rounded
        ${selected ? 'bg-neon-purple/20 text-neon-purple' : ''}
      `}
      style={{ paddingLeft }}
      onClick={(e) => {
        e.stopPropagation()
        onClick?.()
      }}
    >
      {/* Expand/collapse toggle */}
      {hasChildren ? (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
          className="p-0.5 hover:bg-slate-700 rounded"
        >
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
          )}
        </button>
      ) : (
        <span className="w-4" />
      )}

      {/* Icon */}
      <Icon 
        className="w-4 h-4 flex-shrink-0" 
        style={iconColor ? { color: iconColor } : undefined}
      />

      {/* Label */}
      <span className="flex-1 truncate text-sm">{label}</span>

      {/* Count badge */}
      {count !== undefined && count > 0 && (
        <span className="text-xs text-slate-500 tabular-nums">{count}</span>
      )}
    </div>
  )
}

/**
 * FolderTreeView - Recursive folder tree for an entity
 */
function FolderTreeView({ tree, entityId, level, selectedPath, onSelect }) {
  const [expanded, setExpanded] = useState({})

  const toggleExpand = (folderId) => {
    setExpanded(prev => ({ ...prev, [folderId]: !prev[folderId] }))
  }

  const renderFolder = (folder, currentLevel) => {
    const hasChildren = (folder.children?.length || 0) > 0
    const isExpanded = expanded[folder.id]

    return (
      <div key={folder.id}>
        <TreeNode
          icon={isExpanded ? FolderOpen : Folder}
          iconColor="#F59E0B"
          label={folder.name}
          count={folder.document_count}
          expanded={hasChildren ? isExpanded : undefined}
          onToggle={hasChildren ? () => toggleExpand(folder.id) : undefined}
          onClick={() => onSelect('folder', { folderId: folder.id, entityId })}
          selected={selectedPath?.type === 'folder' && selectedPath?.folderId === folder.id}
          level={currentLevel}
        />

        {isExpanded && folder.children?.map(child => 
          renderFolder(child, currentLevel + 1)
        )}
      </div>
    )
  }

  return (
    <>
      {tree.map(folder => renderFolder(folder, level))}
    </>
  )
}

