param(
    [Parameter(Mandatory)][string]$SampleDirectory,
    [Parameter(Mandatory)][string]$OutputDirectory
)

# Controlled RF-036 test with two public, hash-checked blank templates.
$ErrorActionPreference = 'Stop'
if (Get-Process EXCEL -ErrorAction SilentlyContinue) {
    throw 'Close other Excel processes before running this isolated automation test.'
}
$sampleRoot = (Resolve-Path -LiteralPath $SampleDirectory).Path
$outputRoot = (New-Item -ItemType Directory -Force -Path $OutputDirectory).FullName
$cases = @(
    @{
        Name='student-card'; Source='qlnu-0.xls'; Sheet='Sheet1'
        Sha='b4aef5b79e2a0a31c585d4db9db05aa10a703516c6e1939cccce639a04acd5bb'
        Fields=[ordered]@{
            B2='谢予安'; D2='女'; F2='2005年11月8日'; F3='电子信息工程'
            B4='2024级'; F4='4年'; H4='本科'; B5='00003152'
            F5='济南市历城区校内宿舍'
            B6='整理个人材料时发现学生证遗失，已查找未果，现按学院要求申请补办。'
        }
        StudentId='B5'
    },
    @{
        Name='student-status'; Source='bucm-0.xls'; Sheet='休学'
        Sha='c76bec78fe886151d2afe86b130dc580846e3059f20bc2f9a6e012f0b7e795b0'
        Fields=[ordered]@{B3='00004286'; D3='陆清言'; G3='女'}
        StudentId='B3'
    }
)

function Get-SpecialCellCount($range, [int]$kind) {
    try { return [int]$range.SpecialCells($kind).Count }
    catch [System.Runtime.InteropServices.COMException] {
        if ($_.Exception.HResult -ne -2146827284) { throw }
        return 0
    }
}

function Get-WorkbookSnapshot($book) {
    $sheets = foreach ($sheet in $book.Worksheets) {
        $setup = $sheet.PageSetup
        [ordered]@{
            name=$sheet.Name; visible=$sheet.Visible; used=$sheet.UsedRange.Address()
            formulas=(Get-SpecialCellCount $sheet.UsedRange -4123)
            validations=(Get-SpecialCellCount $sheet.UsedRange -4174)
            shapes=$sheet.Shapes.Count
            printArea=$setup.PrintArea; printTitleRows=$setup.PrintTitleRows; printTitleColumns=$setup.PrintTitleColumns
            orientation=$setup.Orientation; paperSize=$setup.PaperSize; zoom=$setup.Zoom
            fitWide=$setup.FitToPagesWide; fitTall=$setup.FitToPagesTall; printGrid=$setup.PrintGridlines
            topMargin=$setup.TopMargin; bottomMargin=$setup.BottomMargin
            leftMargin=$setup.LeftMargin; rightMargin=$setup.RightMargin
        }
    }
    return ConvertTo-Json -InputObject @($sheets) -Depth 4 -Compress
}

$excel = New-Object -ComObject Excel.Application
try {
    $excel.AutomationSecurity = 3
    $excel.DisplayAlerts = $false
    $excel.Visible = $false
    foreach ($case in $cases) {
        $originalPath = Join-Path $sampleRoot $case.Source
        if ((Get-FileHash -LiteralPath $originalPath).Hash -ne $case.Sha) { throw "Template hash changed: $($case.Source)" }
        $sourceBook = $excel.Workbooks.Open($originalPath,0,$true)
        try {
            if ($sourceBook.HasVBProject -or $sourceBook.Excel4MacroSheets.Count -or $sourceBook.LinkSources(1)) {
                throw "Unsupported active content or links in $($case.Source)"
            }
            $originalSnapshot = Get-WorkbookSnapshot $sourceBook
            $originalPrint = Join-Path $outputRoot ($case.Name+'-original.pdf')
            $sourceBook.Worksheets.Item($case.Sheet).ExportAsFixedFormat(0,$originalPrint,0,$true,$false)
        } finally { $sourceBook.Close($false) }

        foreach ($format in @(@{Suffix='xls';Code=56},@{Suffix='xlsx';Code=51})) {
            $target = Join-Path $outputRoot ($case.Name+'-filled.'+$format.Suffix)
            if (Test-Path -LiteralPath $target) { throw "Output already exists: $target" }
            $book = $excel.Workbooks.Open($originalPath,0,$true)
            try {
                $sheet = $book.Worksheets.Item($case.Sheet)
                foreach ($cell in $case.Fields.Keys) {
                    $value = $case.Fields[$cell]
                    $sheet.Range($cell).Value2 = if ($cell -eq $case.StudentId) { "'"+$value } else { $value }
                }
                $book.SaveAs($target,$format.Code)
            } finally { $book.Close($false) }

            $saved = $excel.Workbooks.Open($target,0,$true)
            try {
                $sheet = $saved.Worksheets.Item($case.Sheet)
                foreach ($cell in $case.Fields.Keys) {
                    if ($sheet.Range($cell).Value2 -cne $case.Fields[$cell]) { throw "Readback mismatch at $cell in $target" }
                }
                if ($sheet.Range($case.StudentId).Value2 -isnot [string]) { throw 'Identifier did not stay text' }
                $savedSnapshot = Get-WorkbookSnapshot $saved
                $outputPrint = Join-Path $outputRoot ($case.Name+'-'+$format.Suffix+'.pdf')
                $sheet.ExportAsFixedFormat(0,$outputPrint,0,$true,$false)
                [pscustomobject]@{
                    sample=$case.Name; format=$format.Suffix; workbook=$target
                    excelVersion=$excel.Version; matchedFields=$case.Fields.Count
                    samePrintAndStructure=($savedSnapshot -ceq $originalSnapshot)
                    original=ConvertFrom-Json -InputObject $originalSnapshot
                    converted=ConvertFrom-Json -InputObject $savedSnapshot
                } | ConvertTo-Json -Depth 6 -Compress
            } finally { $saved.Close($false) }
        }
        if ((Get-FileHash -LiteralPath $originalPath).Hash -ne $case.Sha) { throw 'Original changed during experiment' }
    }
} finally {
    $excel.Quit()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
}
