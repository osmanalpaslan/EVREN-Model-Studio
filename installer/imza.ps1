# EVREN Studio imza betigi: verilen dosyayi kullanicinin kendi kod imzalama sertifikasiyla imzalar (Authenticode,
# SHA256, zaman damgali). Sertifika: tools\paketle.py sertifika (Cert:\CurrentUser\My, konu asagida).
# Inno Setup bunu SignTool olarak cagirir (kurulum ve kaldirici dosyasi icin); paketle.py exe icin.
param([Parameter(Mandatory = $true)][string]$Dosya)
$ErrorActionPreference = 'Stop'
$konu = 'CN=EVREN Studio - Osman Alpaslan'
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -eq $konu -and $_.NotAfter -gt (Get-Date) } |
    Sort-Object NotAfter -Descending | Select-Object -First 1
if (-not $cert) { Write-Error "Imza sertifikasi yok: once 'tools\paketle.py sertifika' calistirin."; exit 2 }
$sunucular = @('http://timestamp.digicert.com', 'http://timestamp.sectigo.com', 'http://timestamp.globalsign.com/tsa/r6advanced1')
foreach ($ts in $sunucular) {
    try {
        $s = Set-AuthenticodeSignature -FilePath $Dosya -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $ts
        if ($s.SignerCertificate) { Write-Output "imzalandi: $Dosya ($ts)"; exit 0 }
    } catch { Write-Warning "zaman damgasi sunucusu basarisiz: $ts" }
}
# Zaman damgasi alinamadiysa damgasiz imzala (sertifika suresi dolunca imza gecersiz sayilir)
$s = Set-AuthenticodeSignature -FilePath $Dosya -Certificate $cert -HashAlgorithm SHA256
if ($s.SignerCertificate) { Write-Output "imzalandi (zaman damgasiz): $Dosya"; exit 0 }
Write-Error "imzalanamadi: $Dosya"; exit 1
