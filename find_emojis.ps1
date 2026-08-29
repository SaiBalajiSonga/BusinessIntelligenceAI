[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
 = Get-Content 'web/src/pages/Overview.tsx' -Raw
[regex]::Matches(, '[\p{So}\p{Sk}]').Value | Select-Object -Unique
