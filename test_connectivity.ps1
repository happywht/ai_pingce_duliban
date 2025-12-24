# 连通性测试脚本
$server_ip = "10.1.2.198"
$port = 5000

Write-Host "=== 端口连通性测试 ===" -ForegroundColor Green

# 1. 测试TCP端口连通性
Write-Host "1. 测试TCP端口连通性..." -ForegroundColor Yellow
try {
    $tcpclient = New-Object System.Net.Sockets.TcpClient
    $tcpclient.Connect($server_ip, $port)
    Write-Host "✅ TCP连接成功: $server_ip`:$port" -ForegroundColor Green
    $tcpclient.Close()
} catch {
    Write-Host "❌ TCP连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

# 2. 测试HTTP连接
Write-Host "2. 测试HTTP连接..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://$($server_ip):$($port)/api/task_statistics" -TimeoutSec 10
    Write-Host "✅ HTTP连接成功" -ForegroundColor Green
    Write-Host "响应: $($response.StatusCode)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ HTTP连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

# 3. 检查服务监听状态
Write-Host "3. 检查服务监听状态..." -ForegroundColor Yellow
$netstat = netstat -an | findstr ":5000"
if ($netstat) {
    Write-Host "监听状态:" -ForegroundColor Green
    $netstat | ForEach-Object {
        if ($_ -match "0.0.0.0:5000") {
            Write-Host "  ✅ 正确监听所有接口" -ForegroundColor Green
        } elseif ($_ -match "127.0.0.1:5000") {
            Write-Host "  ❌ 只监听本地回环地址" -ForegroundColor Red
        } else {
            Write-Host "  $_" -ForegroundColor Cyan
        }
    }
} else {
    Write-Host "❌ 5000端口未监听" -ForegroundColor Red
}

Write-Host "=== 测试完成 ===" -ForegroundColor Green