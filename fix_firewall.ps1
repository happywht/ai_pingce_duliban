# 防火墙配置脚本
Write-Host "=== 配置防火墙规则 ===" -ForegroundColor Green

# 删除可能存在的旧规则
Write-Host "删除旧规则..." -ForegroundColor Yellow
Remove-NetFirewallRule -DisplayName "Backend Service Port 5000" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "Python Flask Port 5000" -ErrorAction SilentlyContinue

# 添加入站规则
Write-Host "添加入站规则..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "Backend Service Port 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Enabled True

# 添加出站规则
Write-Host "添加出站规则..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "Backend Service Port 5000" -Direction Outbound -Protocol TCP -LocalPort 5000 -Action Allow -Enabled True

# 验证规则
Write-Host "验证规则..." -ForegroundColor Green
$rules = Get-NetFirewallRule -DisplayName "*5000*"
$rules | ForEach-Object {
    Write-Host "规则: $($_.DisplayName)" -ForegroundColor Cyan
    Write-Host "  方向: $($_.Direction)" -ForegroundColor Cyan
    Write-Host "  状态: $($_.Enabled)" -ForegroundColor Cyan
    Write-Host "  协议: $($_.Protocol)" -ForegroundColor Cyan
    Write-Host "  端口: $($_.LocalPort)" -ForegroundColor Cyan
    Write-Host "---" -ForegroundColor Cyan
}

Write-Host "✅ 防火墙配置完成" -ForegroundColor Green