import { useState, useRef } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import {
  Upload,
  FileSpreadsheet,
  Download,
  CheckCircle2,
  XCircle,
  RotateCw,
  FileText,
  X,
} from 'lucide-react'

const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 // 2 MB

/**
 * Reusable CsvUpload component supporting drag-and-drop, client-side size & type validation,
 * authenticated blob template downloads, and row-by-row execution reports.
 *
 * @param {Object} props
 * @param {string} [props.title='Upload CSV Batch']
 * @param {string} [props.description='Upload a valid UTF-8 CSV file. Maximum file size 2 MB.']
 * @param {Array<string>} [props.columnsHint] - Required column headers hint
 * @param {Function} props.onUpload - Async upload handler receiving (file) => uploadReport
 * @param {Function} props.onDownloadTemplate - Async handler returning Blob
 * @param {string} [props.templateFilename='template.csv']
 * @param {Function} [props.onSuccess] - Callback invoked on successful upload
 */
export function CsvUpload({
  title = 'Upload CSV Batch',
  description = 'Upload a valid UTF-8 CSV file. Maximum file size 2 MB.',
  columnsHint = [],
  onUpload,
  onDownloadTemplate,
  templateFilename = 'template.csv',
  onSuccess,
}) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [uploadReport, setUploadReport] = useState(null)
  const fileInputRef = useRef(null)

  const validateAndSetFile = (file) => {
    if (!file) return

    // Type check
    const isCsv = file.name.toLowerCase().endsWith('.csv') || file.type === 'text/csv'
    if (!isCsv) {
      toast.error('Invalid file type. Only standard .csv files are accepted.')
      return
    }

    // Size check: max 2 MB
    if (file.size > MAX_FILE_SIZE_BYTES) {
      toast.error('File size exceeds the maximum limit of 2 MB.')
      return
    }

    setSelectedFile(file)
    setUploadReport(null)
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const handleDownloadTemplate = async () => {
    if (!onDownloadTemplate) return
    setIsDownloading(true)
    try {
      const blob = await onDownloadTemplate()
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/csv;charset=utf-8;' }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', templateFilename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('CSV template downloaded successfully.')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to download CSV template.')
    } finally {
      setIsDownloading(false)
    }
  }

  const handleUploadSubmit = async () => {
    if (!selectedFile || !onUpload) return
    setIsUploading(true)
    try {
      const report = await onUpload(selectedFile)
      setUploadReport(report)
      setSelectedFile(null)
      toast.success(
        `Batch processed: ${report.created_count} created, ${report.updated_count} updated, ${report.rejected_count} rejected.`
      )
      if (report?.message) {
        toast.info(report.message)
      }
      if (onSuccess) onSuccess(report)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to process CSV upload.')
    } finally {
      setIsUploading(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setUploadReport(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="space-y-6">
      {/* Upload Dropzone Card */}
      <Card className="border-border bg-white shadow-card">
        <CardHeader className="p-6 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <CardTitle className="text-base font-bold text-zinc-950 flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-zinc-800" />
                {title}
              </CardTitle>
              <CardDescription className="text-xs text-zinc-500 mt-1">
                {description}
              </CardDescription>
            </div>

            {onDownloadTemplate && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadTemplate}
                disabled={isDownloading}
                className="text-xs gap-1.5 h-8 border-border bg-white text-zinc-800 hover:bg-zinc-50 shrink-0"
              >
                {isDownloading ? (
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5" />
                )}
                Download Template (.csv)
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent className="p-6 pt-2 space-y-4 text-xs">
          {/* Required Column Format Hint */}
          {columnsHint.length > 0 && (
            <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-200 text-zinc-700 space-y-1.5">
              <span className="font-semibold text-zinc-900 block text-[11px] uppercase tracking-wider">
                Required CSV Column Format:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {columnsHint.map((col) => (
                  <Badge
                    key={col}
                    variant="outline"
                    className="font-mono text-[11px] bg-white text-zinc-800 border-zinc-300"
                  >
                    {col}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Interactive Drag & Drop Area */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              dragActive
                ? 'border-black bg-zinc-50'
                : 'border-zinc-200 hover:border-zinc-400 bg-white'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="max-w-sm mx-auto space-y-2">
              <div className="w-10 h-10 rounded-full bg-zinc-100 text-zinc-700 flex items-center justify-center mx-auto">
                <Upload className="w-5 h-5" />
              </div>
              <p className="font-semibold text-sm text-zinc-900">
                {selectedFile ? selectedFile.name : 'Choose a CSV file or drag & drop here'}
              </p>
              <p className="text-zinc-500 text-xs">
                {selectedFile
                  ? `${(selectedFile.size / 1024).toFixed(1)} KB • Ready to upload`
                  : 'Accepts standard UTF-8 encoded .csv files up to 2 MB'}
              </p>
            </div>
          </div>

          {/* Selected File Pill */}
          {selectedFile && (
            <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-50 border border-zinc-200">
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="w-4 h-4 text-zinc-600 shrink-0" />
                <span className="font-medium text-xs text-zinc-900 truncate">
                  {selectedFile.name}
                </span>
                <span className="text-[11px] text-zinc-500 font-mono shrink-0">
                  ({(selectedFile.size / 1024).toFixed(1)} KB)
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  handleReset()
                }}
                className="h-6 w-6 p-0 text-zinc-400 hover:text-zinc-900"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          )}
        </CardContent>

        <CardFooter className="p-6 pt-0 border-t border-zinc-100 flex items-center justify-between">
          <span className="text-xs text-zinc-400">
            Shri Vishwakarma Skill University • Batch Processing
          </span>
          <Button
            size="sm"
            onClick={handleUploadSubmit}
            disabled={!selectedFile || isUploading}
            className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-2 font-semibold shadow-xs"
          >
            {isUploading ? (
              <>
                <RotateCw className="w-3.5 h-3.5 animate-spin" />
                Processing Batch...
              </>
            ) : (
              <>
                <Upload className="w-3.5 h-3.5" />
                Upload and Process
              </>
            )}
          </Button>
        </CardFooter>
      </Card>

      {/* Row-by-Row Upload Execution Report */}
      {uploadReport && (
        <Card className="border-border bg-white shadow-card">
          <CardHeader className="p-6 pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base font-bold text-zinc-950">
                  Batch Execution Report
                </CardTitle>
                <CardDescription className="text-xs text-zinc-500">
                  Row-level summary of processed CSV records.
                </CardDescription>
              </div>

              {/* Stat Summary Badges */}
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono text-xs bg-zinc-50 border-zinc-200">
                  Total: {uploadReport.total_rows}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs bg-emerald-50 text-emerald-800 border-emerald-200">
                  Created: {uploadReport.created_count}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs bg-blue-50 text-blue-800 border-blue-200">
                  Updated: {uploadReport.updated_count}
                </Badge>
                {uploadReport.rejected_count > 0 && (
                  <Badge variant="outline" className="font-mono text-xs bg-rose-50 text-rose-800 border-rose-200">
                    Rejected: {uploadReport.rejected_count}
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-6 pt-0 space-y-3">
            {uploadReport.message && (
              <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-zinc-700 text-xs leading-relaxed">
                {uploadReport.message}
              </div>
            )}
            {(!uploadReport.rows || uploadReport.rows.length === 0) ? (
              <p className="text-xs text-zinc-500 italic py-2">
                No individual row diagnostic details were returned.
              </p>
            ) : (
              <div className="max-h-96 overflow-y-auto rounded-lg border border-border divide-y divide-zinc-100">
                {uploadReport.rows.map((r, i) => {
                  const statusUpper = String(r.status || '').toUpperCase()
                  const isCreated = statusUpper === 'CREATED'
                  const isUpdated = statusUpper === 'UPDATED'
                  const isRejected = statusUpper === 'REJECTED'

                  return (
                    <div
                      key={i}
                      className="p-3 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-zinc-50/50"
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-zinc-400 w-12 shrink-0">
                          Row {r.row_number || i + 1}
                        </span>
                        <div>
                          <span className="font-semibold text-zinc-900 font-mono">
                            {r.registration_number || r.code || 'Record'}
                          </span>
                          {r.name && (
                            <span className="text-zinc-600 ml-2">
                              • {r.name}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 sm:self-center">
                        {isCreated && (
                          <Badge variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-200 text-[10px] gap-1">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Created
                          </Badge>
                        )}
                        {isUpdated && (
                          <Badge variant="outline" className="bg-blue-50 text-blue-800 border-blue-200 text-[10px] gap-1">
                            <RotateCw className="w-3 h-3 text-blue-600" />
                            Updated
                          </Badge>
                        )}
                        {isRejected && (
                          <Badge variant="outline" className="bg-rose-50 text-rose-800 border-rose-200 text-[10px] gap-1">
                            <XCircle className="w-3 h-3 text-rose-600" />
                            Rejected
                          </Badge>
                        )}
                        {r.reason && (
                          <span className="text-[11px] text-zinc-500 font-mono max-w-sm truncate">
                            {r.reason}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default CsvUpload
