# Windows.Media.Ocr 批量识别（PowerShell 5.1 / WinRT）
# 用法: powershell.exe -NoProfile -ExecutionPolicy Bypass -File ocr_winrt.ps1 -InDir <dir> -OutJson <file>
param(
    [Parameter(Mandatory = $true)][string]$InDir,
    [Parameter(Mandatory = $true)][string]$OutJson,
    [string]$Lang = "zh-Hans-CN"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    [void]$netTask.Wait(-1)
    $netTask.Result
}

# 加载 WinRT 类型
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime] | Out-Null

$language = New-Object Windows.Globalization.Language($Lang)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) {
    # 退回用户配置语言
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $engine) { throw "no OCR engine available for $Lang" }

Write-Host ("engine: " + $engine.RecognizerLanguage.LanguageTag + "  maxDim=" + [Windows.Media.Ocr.OcrEngine]::MaxImageDimension)

$files = Get-ChildItem -Path $InDir -Filter *.png | Sort-Object Name
$results = @()

foreach ($f in $files) {
    $sf = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f.FullName)) ([Windows.Storage.StorageFile])
    $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    try {
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocr = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

        $lines = @()
        foreach ($ln in $ocr.Lines) {
            $words = @()
            foreach ($w in $ln.Words) {
                $words += [pscustomobject]@{
                    t = $w.Text
                    x = [math]::Round($w.BoundingRect.X, 1)
                    y = [math]::Round($w.BoundingRect.Y, 1)
                    w = [math]::Round($w.BoundingRect.Width, 1)
                    h = [math]::Round($w.BoundingRect.Height, 1)
                }
            }
            if ($words.Count -gt 0) {
                $x0 = ($words | Measure-Object -Property x -Minimum).Minimum
                $y0 = ($words | Measure-Object -Property y -Minimum).Minimum
                $x1 = ($words | ForEach-Object { $_.x + $_.w } | Measure-Object -Maximum).Maximum
                $y1 = ($words | ForEach-Object { $_.y + $_.h } | Measure-Object -Maximum).Maximum
                $lines += [pscustomobject]@{
                    text = $ln.Text
                    x = $x0; y = $y0; x2 = $x1; y2 = $y1
                    words = $words
                }
            }
        }
        $results += [pscustomobject]@{
            file = $f.Name
            width = $decoder.PixelWidth
            height = $decoder.PixelHeight
            lines = $lines
        }
        Write-Host ("  " + $f.Name + " -> " + $lines.Count + " lines")
    }
    finally {
        if ($stream) { $stream.Dispose() }
    }
}

$json = $results | ConvertTo-Json -Depth 8 -Compress
[System.IO.File]::WriteAllText($OutJson, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ("wrote " + $OutJson)
