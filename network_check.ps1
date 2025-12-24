# 网络检查脚本
Write-Host "=== 网络连通性检查 ===" -ForegroundColor Green

# 1. 检查端口监听状态
Write-Host "1. 检查5000端口监听状态..." -ForegroundColor Yellow
$netstat = netstat -an | findstr ":5000"
if ($netstat) {
    Write-Host "端口监听状态:" -ForegroundColor Green
    $netstat | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }
} else {
    Write-Host "❌ 5000端口未监听" -ForegroundColor Red
}

# 2. 检查防火墙规则
Write-Host "2. 检查防火墙5000端口规则..." -ForegroundColor Yellow
$firewall = Get-NetFirewallRule -DisplayName "*5000*" -ErrorAction SilentlyContinue
if ($firewall) {
    Write-Host "防火墙规则:" -ForegroundColor Green
    $firewall | ForEach-Object {
        Write-Host "  $($_.DisplayName): $($_.Enabled)" -ForegroundColor Cyan
    }
} else {
    Write-Host "❌ 未找到5000端口防火墙规则" -ForegroundColor Red
}

# 3. 测试本地连接
Write-Host "3. 测试本地连接..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/api/task_statistics" -TimeoutSec 5
    Write-Host "✅ 本地连接正常" -ForegroundColor Green
} catch {
    Write-Host "❌ 本地连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "=== 检查完成 ===" -ForegroundColor Green