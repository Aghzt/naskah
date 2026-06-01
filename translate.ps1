# =====================================================================
#  Jurnal Translator - skrip 1-perintah
#  Terjemah PDF jurnal EN -> ID (layout & gambar terjaga) via DeepSeek/Sumopod
#
#  Contoh pakai:
#    .\translate.ps1 -Pdf "samples\s41586-020-1969-6.pdf"
#    .\translate.ps1 -Pdf "samples\jurnal.pdf" -Pages "1-5"
#    .\translate.ps1 -Pdf "samples\jurnal.pdf" -Thread 12
# =====================================================================
param(
    [Parameter(Mandatory = $true)] [string]$Pdf,
    [string]$Pages = "",
    [int]$Thread = 8,
    [string]$Output = "output"
)

$dir = $PSScriptRoot
$exe = Join-Path $dir ".venv\Scripts\pdf2zh.exe"
$promptFile = Join-Path $dir "prompts\prompt_akademik.txt"

# --- Muat .env ---
$envPath = Join-Path $dir ".env"
if (-not (Test-Path $envPath)) { throw "File .env tidak ditemukan. Salin dari .env.example dan isi." }
Get-Content $envPath | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
$env:PYTHONIOENCODING = "utf-8"

# --- Susun argumen ---
$pdfPath = if ([IO.Path]::IsPathRooted($Pdf)) { $Pdf } else { Join-Path $dir $Pdf }
$outDir = if ([IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $dir $Output }
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory $outDir | Out-Null }

$args = @($pdfPath, "--service", "openai", "--lang-in", "en", "--lang-out", "id",
    "--thread", $Thread, "--prompt", $promptFile, "--output", $outDir)
if ($Pages -ne "") { $args += @("--pages", $Pages) }

Write-Host "Menerjemahkan: $pdfPath" -ForegroundColor Cyan
Write-Host "Model: $env:OPENAI_MODEL | Thread: $Thread | Halaman: $(if($Pages){$Pages}else{'semua'})" -ForegroundColor DarkGray

# pdf2zh menulis progress bar ke stderr; jangan anggap itu sebagai error fatal.
$ErrorActionPreference = "Continue"
& $exe @args
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host "Selesai. Hasil ada di: $outDir (-mono.pdf = full ID, -dual.pdf = bilingual)" -ForegroundColor Green
} else {
    Write-Host "Gagal (exit code $code). Cek pesan di atas." -ForegroundColor Red
}
exit $code
