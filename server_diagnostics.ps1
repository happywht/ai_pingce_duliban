# 服务器诊断脚本
Write-Host "=== 服务器网络诊断 ===" -ForegroundColor Green

# 1. 检查Flask进程是否运行
Write-Host "1. 检查Python/Flask进程..." -ForegroundColor Yellow
$processes = Get-Process | Where-Object {$_.ProcessName -like "*python*"}
if ($processes) {
    Write-Host "找到Python进程:" -ForegroundColor Green
    $processes | ForEach-Object {
        Write-Host "  PID: $($_.Id), 名称: $($_.ProcessName), 内存: $($_.WorkingSet/1MB) MB" -ForegroundColor Cyan
    }
} else {
    Write-Host "❌ 未找到Python进程" -ForegroundColor Red
}

# 2. 检查5000端口监听状态
Write-Host "2. 检查5000端口监听..." -ForegroundColor Yellow
$netstat = netstat -ano | findstr ":5000"
if ($netstat) {
    Write-Host "5000端口监听状态:" -ForegroundColor Green
    $netstat | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Cyan

        # 解析监听IP
        if ($_ -match "TCP\s+([\d.]+):5000") {
            $listen_ip = $matches[1]
            Write-Host "    监听IP: $listen_ip" -ForegroundColor White
            if ($listen_ip -eq "0.0.0.0") {
                Write-Host "    ✅ 监听所有网络接口 (正确)" -ForegroundColor Green
            } elseif ($listen_ip -eq "127.0.0.1") {
                Write-Host "    ❌ 只监听本地回环地址 (问题)" -ForegroundColor Red
            } elseif ($listen_ip -match "10\.1\.2\.198") {
                Write-Host "    ✅ 监听服务器IP (正确)" -ForegroundColor Green
            } else {
                Write-Host "    ⚠️ 监听其他IP: $listen_ip" -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "❌ 5000端口未监听" -ForegroundColor Red
}

# 3. 检查本机IP地址
Write-Host "3. 检查服务器本机IP地址..." -ForegroundColor Yellow
$ipconfig = ipconfig | findstr "IPv4"
$ipconfig | ForEach-Object {
    if ($_ -match "10\.1\.2\.198") {
        Write-Host "  ✅ 服务器IP: 10.1.2.198" -ForegroundColor Green
    }
}

# 4. 检查防火墙规则
Write-Host "4. 检查防火墙5000端口规则..." -ForegroundColor Yellow
$firewall = Get-NetFirewallRule -DisplayName "*5000*" -ErrorAction SilentlyContinue
if ($firewall) {
    Write-Host "防火墙规则:" -ForegroundColor Green
    $firewall | ForEach-Object {
        $enabled = if ($_.Enabled) { "启用" } else { "禁用" }
        Write-Host "  $($_.DisplayName): $enabled" -ForegroundColor Cyan
    }
} else {
    Write-Host "❌ 未找到5000端口防火墙规则" -ForegroundColor Red
}

# 5. 测试本机连接
Write-Host "5. 测试本机连接..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5000/api/task_statistics" -TimeoutSec 5
    Write-Host "✅ 本机localhost连接成功" -ForegroundColor Green
} catch {
    Write-Host "❌ 本机localhost连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $response = Invoke-RestMethod -Uri "http://10.1.2.198:5000/api/task_statistics" -TimeoutSec 5
    Write-Host "✅ 本机IP连接成功" -ForegroundColor Green
} catch {
    Write-Host "❌ 本机IP连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "=== 诊断完成 ===" -ForegroundColor Green