# ============================================
# PM2 进程管理配置
# 宝塔面板部署后用 PM2 保持程序运行
# ============================================
module.exports = {
  apps: [{
    name: "hot-topic-agent",
    script: "main.py",
    interpreter: "python3",
    cwd: __dirname,
    
    // 环境变量
    env: {
      NON_INTERACTIVE: "1",
      TZ: "Asia/Shanghai",
    },
    
    // 从 .env 文件加载（PM2 5.3+ 支持）
    env_file: ".env",
    
    // 重启策略
    max_restarts: 10,
    restart_delay: 5000,
    min_uptime: "30s",
    
    // 日志
    error_file: "./data/logs/pm2-error.log",
    out_file: "./data/logs/pm2-out.log",
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    
    // 内存限制（超限自动重启）
    max_memory_restart: "1G",
  }]
};
