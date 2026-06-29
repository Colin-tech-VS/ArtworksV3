# Sync .env local → Scalingo artworksv3 (sans committer les secrets)
# Prérequis: scalingo login
$Scalingo = Join-Path $PSScriptRoot "..\tools\scalingo_1.33.0_windows_amd64\scalingo.exe"
$App = "artworksv3"
$EnvFile = Join-Path $PSScriptRoot "..\artworks_site\.env"

if (-not (Test-Path $Scalingo)) { throw "Scalingo CLI introuvable: $Scalingo" }
if (-not (Test-Path $EnvFile)) { throw ".env introuvable: $EnvFile" }

# Générer SECRET_KEY prod si absent
$lines = Get-Content $EnvFile
$map = @{}
foreach ($line in $lines) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $k, $v = $line -split '=', 2
    $map[$k.Trim()] = $v.Trim()
}

# Overrides production
$map['SITE_URL'] = 'https://artworksv3.osc-fr1.scalingo.io'
$map['DEVIANTART_REDIRECT_URI'] = 'https://artworksv3.osc-fr1.scalingo.io/crm/social/oauth/deviantart/callback'
$map['PINTEREST_REDIRECT_URI'] = 'https://artworksv3.osc-fr1.scalingo.io/crm/social/oauth/pinterest/callback'
$map['MAIL_USE_TLS'] = '0'
if (-not $map['SECRET_KEY'] -or $map['SECRET_KEY'] -like '*dev*' -or $map['SECRET_KEY'] -like '*change*') {
    $map['SECRET_KEY'] = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
}

$skip = @('DATABASE_URL')  # Définir manuellement (Supabase)
$keys = @(
    'SECRET_KEY','MISTRAL_API_KEY','MISTRAL_MODEL','MISTRAL_MODEL_HEAVY','AI_PRIMARY',
    'STRIPE_PUBLISHABLE_KEY','STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','SITE_URL',
    'GOOGLE_OAUTH_CLIENT_ID','GOOGLE_OAUTH_CLIENT_SECRET','GOOGLE_PLACES_API_KEY',
    'SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM','SMTP_FROM_NAME',
    'MAIL_USE_TLS','FACEBOOK_PAGE_ACCESS_TOKEN','FACEBOOK_PAGE_ID',
    'INSTAGRAM_ACCESS_TOKEN','INSTAGRAM_USER_ID',
    'PINTEREST_CLIENT_ID','PINTEREST_CLIENT_SECRET','PINTEREST_REDIRECT_URI',
    'DEVIANTART_CLIENT_ID','DEVIANTART_CLIENT_SECRET','DEVIANTART_REDIRECT_URI'
)

Write-Host "=== scalingo --app $App env-set ===" -ForegroundColor Cyan
foreach ($k in $keys) {
    if ($map.ContainsKey($k) -and $map[$k] -and ($skip -notcontains $k)) {
        & $Scalingo --app $App env-set "$k=$($map[$k])"
    }
}

Write-Host "`nN'oubliez pas: scalingo --app $App env-set DATABASE_URL=<supabase-uri>" -ForegroundColor Yellow
Write-Host "GitHub autodeploy: scalingo --app $App integrations github create Colin-tech-VS/ArtworksV3 branch=main" -ForegroundColor Yellow
