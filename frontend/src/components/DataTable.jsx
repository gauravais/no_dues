import { useState, useMemo } from 'react'
import { flexRender } from '@tanstack/react-table'
import {
  useLegacyTable as useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
} from '@tanstack/react-table/legacy'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EmptyState } from '@/components/EmptyState'
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Inbox,
} from 'lucide-react'

/**
 * Shared accessible data table component.
 *
 * @param {Object} props
 * @param {Array} props.columns - TanStack column definitions
 * @param {Array} props.data - Array of row data
 * @param {boolean} [props.isLoading=false] - Skeleton loader state
 * @param {boolean} [props.manualPagination=false] - Server-driven pagination
 * @param {number} [props.pageCount] - Total page count for manual pagination
 * @param {number} [props.totalItems] - Total record count
 * @param {number} [props.pageIndex=0] - 0-based page index
 * @param {number} [props.pageSize=10] - Rows per page
 * @param {Function} [props.onPageChange] - Page change handler
 * @param {Function} [props.onPageSizeChange] - Page size change handler
 * @param {Object} [props.statusTabs] - Status tabs filter: { currentTab, onTabChange, tabs: [{ value, label, count }] }
 * @param {Function} [props.renderMobileCard] - Custom mobile card renderer: (row) => ReactNode
 * @param {string|Object} [props.emptyTitle='No records found']
 * @param {string} [props.emptyDescription='There are no items matching the selected criteria.']
 * @param {React.ReactNode} [props.toolbarRight] - Extra actions or search input in header
 */
export function DataTable({
  columns,
  data = [],
  isLoading = false,
  manualPagination = false,
  pageCount,
  totalItems,
  pageIndex = 0,
  pageSize = 10,
  onPageChange,
  statusTabs,
  renderMobileCard,
  emptyTitle = 'No records found',
  emptyDescription = 'There are no items matching the selected criteria.',
  toolbarRight,
}) {
  const [sorting, setSorting] = useState([])

  const pagination = useMemo(
    () => ({
      pageIndex,
      pageSize,
    }),
    [pageIndex, pageSize]
  )

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      ...(manualPagination ? { pagination } : {}),
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    ...(manualPagination
      ? {
          manualPagination: true,
          pageCount: pageCount ?? (totalItems ? Math.ceil(totalItems / pageSize) : -1),
        }
      : {
          getPaginationRowModel: getPaginationRowModel(),
        }),
  })

  const rows = table.getRowModel().rows

  const canPreviousPage = manualPagination
    ? pageIndex > 0
    : table.getCanPreviousPage()

  const canNextPage = manualPagination
    ? pageCount !== undefined
      ? pageIndex < pageCount - 1
      : Boolean(totalItems && (pageIndex + 1) * pageSize < totalItems)
    : table.getCanNextPage()

  const currentPageDisplay = (manualPagination ? pageIndex : table.getState().pagination.pageIndex) + 1
  const totalPagesDisplay = manualPagination
    ? (pageCount || (totalItems ? Math.max(1, Math.ceil(totalItems / pageSize)) : 1))
    : Math.max(1, table.getPageCount())

  return (
    <div className="space-y-4">
      {/* Header Toolbar: Status Filter Tabs & Toolbar Actions */}
      {(statusTabs || toolbarRight) && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
          {statusTabs ? (
            <Tabs
              value={statusTabs.currentTab}
              onValueChange={statusTabs.onTabChange}
              className="w-full sm:w-auto"
            >
              <TabsList className="bg-zinc-100 p-1 border border-border h-9">
                {statusTabs.tabs.map((tab) => (
                  <TabsTrigger
                    key={tab.value}
                    value={tab.value}
                    className="text-xs px-3 py-1 font-medium data-[state=active]:bg-white data-[state=active]:text-zinc-950 data-[state=active]:shadow-2xs"
                  >
                    <span>{tab.label}</span>
                    {typeof tab.count === 'number' && (
                      <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-zinc-200/80 text-zinc-700 data-[state=active]:bg-zinc-100">
                        {tab.count}
                      </span>
                    )}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          ) : (
            <div />
          )}

          {toolbarRight && <div className="flex items-center gap-2">{toolbarRight}</div>}
        </div>
      )}

      {/* Desktop Table View (md and above) */}
      <div className="hidden md:block rounded-xl border border-border bg-white shadow-card overflow-hidden">
        <Table>
          <TableHeader className="bg-zinc-50/70 border-b border-border">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent border-border">
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort()
                  const isSorted = header.column.getIsSorted()
                  return (
                    <TableHead
                      key={header.id}
                      className="text-xs font-semibold text-zinc-600 uppercase tracking-wider py-3.5 px-4 h-auto"
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="flex items-center gap-1.5 text-xs font-semibold text-zinc-700 hover:text-zinc-950 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded py-0.5"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {isSorted === 'asc' ? (
                            <ArrowUp className="w-3.5 h-3.5 text-zinc-950" />
                          ) : isSorted === 'desc' ? (
                            <ArrowDown className="w-3.5 h-3.5 text-zinc-950" />
                          ) : (
                            <ArrowUpDown className="w-3.5 h-3.5 text-zinc-400 opacity-60 hover:opacity-100" />
                          )}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>

          <TableBody>
            {isLoading ? (
              // Skeleton loading rows
              Array.from({ length: 5 }).map((_, idx) => (
                <TableRow key={`skeleton-${idx}`} className="border-border">
                  {columns.map((col, cIdx) => (
                    <TableCell key={`skeleton-cell-${cIdx}`} className="py-4 px-4">
                      <Skeleton className="h-5 w-full max-w-[140px] rounded bg-zinc-100" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length > 0 ? (
              rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="hover:bg-zinc-50/80 transition-colors border-border"
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="py-3.5 px-4 text-xs sm:text-sm text-zinc-800">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="border-0">
                <TableCell colSpan={columns.length} className="py-12 text-center">
                  <EmptyState
                    icon={Inbox}
                    title={emptyTitle}
                    description={emptyDescription}
                  />
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Mobile Card Layout (below md breakpoint) */}
      <div className="md:hidden space-y-3">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, idx) => (
            <div
              key={`m-skeleton-${idx}`}
              className="p-4 rounded-xl border border-border bg-white shadow-2xs space-y-3"
            >
              <div className="flex justify-between items-center">
                <Skeleton className="h-4 w-28 bg-zinc-100" />
                <Skeleton className="h-5 w-16 rounded-full bg-zinc-100" />
              </div>
              <Skeleton className="h-4 w-44 bg-zinc-100" />
              <Skeleton className="h-8 w-full bg-zinc-100 rounded-lg" />
            </div>
          ))
        ) : rows.length > 0 ? (
          rows.map((row) =>
            renderMobileCard ? (
              <div key={row.id}>{renderMobileCard(row.original)}</div>
            ) : (
              <div
                key={row.id}
                className="p-4 rounded-xl border border-border bg-white shadow-2xs space-y-2.5"
              >
                {row.getVisibleCells().map((cell) => {
                  const headerTitle = cell.column.columnDef.header
                  return (
                    <div
                      key={cell.id}
                      className="flex items-start justify-between gap-2 text-xs border-b border-zinc-100 pb-1.5 last:border-0 last:pb-0"
                    >
                      <span className="font-medium text-zinc-500 uppercase tracking-wider text-[10px]">
                        {typeof headerTitle === 'string' ? headerTitle : cell.column.id}
                      </span>
                      <div className="text-right text-zinc-800 font-medium">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </div>
                    </div>
                  )
                })}
              </div>
            )
          )
        ) : (
          <div className="p-8 rounded-xl border border-border bg-white shadow-2xs text-center">
            <EmptyState
              icon={Inbox}
              title={emptyTitle}
              description={emptyDescription}
            />
          </div>
        )}
      </div>

      {/* Pagination Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 text-xs text-zinc-500">
        <div>
          {totalItems !== undefined ? (
            <span>
              Showing <span className="font-semibold text-zinc-800 font-mono">{rows.length}</span> of{' '}
              <span className="font-semibold text-zinc-800 font-mono">{totalItems}</span> records
            </span>
          ) : (
            <span>
              Page <span className="font-semibold text-zinc-800 font-mono">{currentPageDisplay}</span> of{' '}
              <span className="font-semibold text-zinc-800 font-mono">{totalPagesDisplay}</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (manualPagination) {
                onPageChange?.(pageIndex - 1)
              } else {
                table.previousPage()
              }
            }}
            disabled={!canPreviousPage || isLoading}
            className="h-8 px-3 text-xs gap-1 border-border bg-white hover:bg-zinc-100"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            Previous
          </Button>

          <span className="px-2 font-mono text-zinc-700">
            {currentPageDisplay} / {totalPagesDisplay}
          </span>

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (manualPagination) {
                onPageChange?.(pageIndex + 1)
              } else {
                table.nextPage()
              }
            }}
            disabled={!canNextPage || isLoading}
            className="h-8 px-3 text-xs gap-1 border-border bg-white hover:bg-zinc-100"
          >
            Next
            <ChevronRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}
export default DataTable
