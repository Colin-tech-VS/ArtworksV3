# Copie toutes les variables V2 (artworksdigital) vers V3 (artworksv3)
# avec overrides production V3. Ne modifie pas DATABASE_URL ni SECRET_KEY V3.
$ErrorActionPreference = 'Stop'
$Scalingo = Join-Path $PSScriptRoot "..\tools\scalingo147\scalingo_1.47.0_windows_amd64\scalingo.exe"
$V2App = 'artworksdigital'
$V3App = 'artworksv3'
$V3Site = 'https://artworksv3.osc-fr1.scalingo.io'

if (-not (Test-Path $Scalingo)) { throw "Scalingo CLI: $Scalingo" }

function Parse-ScalingoEnv([string]$App) {
    $map = @{}
    $raw = & $Scalingo --app $App env 2>&1 | ForEach-Object { "$_" }
    foreach ($line in $raw) {
        if ($line -notmatch '^[A-Z][A-Z0-9_]*=') { continue }
        $eq = $line.IndexOf('=')
        $k = $line.Substring(0, $eq)
        $v = $line.Substring($eq + 1)
        $map[$k] = $v
    }
    return $map
}

$v2 = Parse-ScalingoEnv $V2App
$v3 = Parse-ScalingoEnv $V3App

# Ne pas écraser : base V3, secret V3, alias Scalingo interne
$skip = @(
    'DATABASE_URL', 'SECRET_KEY', 'SCALINGO_POSTGRESQL_URL', 'SESSION_COOKIE_DOMAIN'
)

# URLs / identité V3
$overrides = @{
    SITE_URL                  = $V3Site
    ENVIRONMENT               = 'production'
    SITE_NAME                 = 'Artworks Digital'
    DEVIANTART_REDIRECT_URI   = "$V3Site/crm/social/oauth/deviantart/callback"
    PINTEREST_REDIRECT_URI    = "$V3Site/crm/social/oauth/pinterest/callback"
    MAIL_USE_TLS              = '0'
    SMTP_FROM_NAME            = 'Artworks'
}

# Alias email V2 → V3 (config lit EMAIL_ADDRESS / EMAIL_PASSWORD)
if ($v2['EMAIL_ADDRESS']) { $overrides['EMAIL_ADDRESS'] = $v2['EMAIL_ADDRESS'] }
if ($v2['EMAIL_PASSWORD']) { $overrides['EMAIL_PASSWORD'] = $v2['EMAIL_PASSWORD'] }
if ($v2['EMAIL_ADDRESS'] -and -not $v3['SMTP_USER']) { $overrides['SMTP_USER'] = $v2['EMAIL_ADDRESS'] }
if ($v2['EMAIL_PASSWORD'] -and -not $v3['SMTP_PASSWORD']) { $overrides['SMTP_PASSWORD'] = $v2['EMAIL_PASSWORD'] }

# Variables V3 uniquement (OAuth Google) — conserver valeurs actuelles
foreach ($k in @('GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET')) {
    if ($v3[$k]) { $overrides[$k] = $v3[$k] }
}

# Réseaux sociaux déjà sur V3 mais absents de V2 Scalingo
foreach ($k in @(
    'FACEBOOK_PAGE_ACCESS_TOKEN', 'FACEBOOK_PAGE_ID',
    'INSTAGRAM_ACCESS_TOKEN', 'INSTAGRAM_USER_ID',
    'PINTEREST_CLIENT_ID', 'PINTEREST_CLIENT_SECRET', 'PINTEREST_DEFAULT_BOARD_ID'
)) {
    if ($v3[$k]) { $overrides[$k] = $v3[$k] }
}

$merged = @{}
foreach ($k in $v2.Keys) {
    if ($skip -contains $k) { continue }
    $merged[$k] = $v2[$k]
}
foreach ($k in $overrides.Keys) {
    $merged[$k] = $overrides[$k]
}

# Variables V3 sans équivalent V2 Scalingo (valeurs par défaut métier)
$v3Extras = @{
    COMMISSION_RATE = '0.18'   # 18 % — standard marketplace V2
    ADMIN_EMAILS    = 'contact@artworksdigital.fr'
}
foreach ($k in $v3Extras.Keys) {
    $merged[$k] = $v3Extras[$k]
}

Write-Host "=== Sync $($v2.Count) vars V2 -> $V3App ($($merged.Count) apres filtres) ===" -ForegroundColor Cyan

$batch = @()
foreach ($k in ($merged.Keys | Sort-Object)) {
    $v = $merged[$k]
    if ($null -eq $v -or $v -eq '') { continue }
  # Scalingo: echapper les guillemets dans la valeur
    $escaped = $v -replace '"', '\"'
    $batch += "$k=$escaped"
}

# env-set par lots de 8 (limite ligne de commande Windows)
$chunk = 8
for ($i = 0; $i -lt $batch.Count; $i += $chunk) {
    $slice = $batch[$i..([Math]::Min($i + $chunk - 1, $batch.Count - 1))]
    $arg = $slice -join ' '
    Write-Host "  batch $([int]($i/$chunk)+1): $($slice.Count) vars"
    & $Scalingo --app $V3App env-set @slice
}

Write-Host "`n=== Variables V3 finales ===" -ForegroundColor Green
& $Scalingo --app $V3App env 2>&1 | ForEach-Object { "$_" } | Sort-Object
