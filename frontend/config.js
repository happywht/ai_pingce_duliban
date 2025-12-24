/**
 * 统一配置管理系统
 * 支持多级配置优先级：URL参数 > localStorage > 默认配置
 */

(function(window) {
    'use strict';

    // ==================== 配置存储键名 ====================
    const CONFIG_KEY = 'AI_PINGCE_CONFIG';
    const CONFIG_VERSION = '1.0.0';

    // ==================== 默认配置 ====================
    const DEFAULT_CONFIG = {
        // API基础地址
        apiBase: '',

        // API超时设置（毫秒）
        apiTimeout: 30000,

        // 是否启用调试模式
        debugMode: false,

        // 是否启用Mock数据（开发测试用）
        enableMock: false,

        // 分页配置
        pagination: {
            pageSize: 20,
            maxPageSize: 100
        },

        // 自动刷新间隔（毫秒，0表示不自动刷新）
        autoRefreshInterval: 0
    };

    // ==================== 配置管理器类 ====================
    class ConfigManager {
        constructor() {
            this.config = this.loadConfig();
            this.observers = [];
        }

        /**
         * 加载配置（优先级：URL参数 > localStorage > 默认配置）
         */
        loadConfig() {
            let config = { ...DEFAULT_CONFIG };

            // 1. 从localStorage加载用户保存的配置
            const savedConfig = this.getFromLocalStorage();
            if (savedConfig) {
                config = { ...config, ...savedConfig };
            }

            // 2. 从URL参数加载（优先级最高）
            const urlConfig = this.getFromURL();
            if (urlConfig) {
                config = { ...config, ...urlConfig };
            }

            // 3. 如果apiBase仍为空，使用智能检测
            if (!config.apiBase) {
                config.apiBase = this.detectApiBase();
            }

            return config;
        }

        /**
         * 智能检测API地址
         */
        detectApiBase() {
            const hostname = window.location.hostname;
            const protocol = window.location.protocol;
            const port = window.location.port || '5000';

            // 本地开发环境 - 使用与页面相同的hostname避免CORS问题
            if (hostname === 'localhost' || hostname === '127.0.0.1') {
                return `${protocol}//${hostname}:${port}/api`;
            }

            // 内网服务器
            if (hostname === '10.1.2.198') {
                return 'http://10.1.2.198:5000/api';
            }

            // 其他环境：使用同服务器的5000端口
            return `${protocol}//${hostname}:5000/api`;
        }

        /**
         * 从localStorage读取配置
         */
        getFromLocalStorage() {
            try {
                const stored = localStorage.getItem(CONFIG_KEY);
                if (stored) {
                    const parsed = JSON.parse(stored);
                    // 版本检查
                    if (parsed.version === CONFIG_VERSION) {
                        return parsed.data;
                    }
                }
            } catch (error) {
                console.warn('读取本地配置失败:', error);
            }
            return null;
        }

        /**
         * 从URL参数读取配置
         */
        getFromURL() {
            try {
                const params = new URLSearchParams(window.location.search);
                const urlConfig = {};

                // 支持的URL参数
                if (params.has('api_base')) {
                    urlConfig.apiBase = params.get('api_base');
                }
                if (params.has('debug')) {
                    urlConfig.debugMode = params.get('debug') === 'true';
                }
                if (params.has('mock')) {
                    urlConfig.enableMock = params.get('mock') === 'true';
                }

                return Object.keys(urlConfig).length > 0 ? urlConfig : null;
            } catch (error) {
                console.warn('读取URL配置失败:', error);
                return null;
            }
        }

        /**
         * 保存配置到localStorage
         */
        saveToLocalStorage(config) {
            try {
                const toSave = {
                    version: CONFIG_VERSION,
                    data: config,
                    timestamp: Date.now()
                };
                localStorage.setItem(CONFIG_KEY, JSON.stringify(toSave));
                return true;
            } catch (error) {
                console.error('保存配置失败:', error);
                return false;
            }
        }

        /**
         * 获取配置项
         */
        get(key) {
            if (key) {
                return this.config[key];
            }
            return { ...this.config };
        }

        /**
         * 设置配置项
         */
        set(key, value, persist = true) {
            if (typeof key === 'object') {
                // 批量设置
                Object.assign(this.config, key);
            } else {
                this.config[key] = value;
            }

            // 保存到localStorage
            if (persist) {
                this.saveToLocalStorage(this.config);
            }

            // 通知观察者
            this.notifyObservers();
        }

        /**
         * 重置配置为默认值
         */
        reset() {
            this.config = { ...DEFAULT_CONFIG };
            this.config.apiBase = this.detectApiBase();
            this.saveToLocalStorage(this.config);
            this.notifyObservers();
        }

        /**
         * 获取API基础地址
         */
        getApiBase() {
            return this.config.apiBase;
        }

        /**
         * 构建完整的API URL
         */
        getApiUrl(endpoint) {
            const apiBase = this.getApiBase();
            if (!endpoint) {
                return apiBase;
            }
            // 确保endpoint以/开头
            const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
            return `${apiBase}${normalizedEndpoint}`;
        }

        /**
         * 测试API连接
         */
        async testConnection() {
            try {
                const response = await fetch(this.getApiUrl('/projects'), {
                    method: 'GET',
                    timeout: 5000
                });
                return {
                    success: response.ok,
                    status: response.status,
                    message: response.ok ? '连接成功' : '连接失败'
                };
            } catch (error) {
                return {
                    success: false,
                    status: 0,
                    message: error.message || '网络连接失败'
                };
            }
        }

        /**
         * 注册配置变更观察者
         */
        subscribe(observer) {
            if (typeof observer === 'function') {
                this.observers.push(observer);
            }
        }

        /**
         * 通知观察者
         */
        notifyObservers() {
            this.observers.forEach(observer => {
                try {
                    observer(this.config);
                } catch (error) {
                    console.error('配置观察者执行失败:', error);
                }
            });
        }

        /**
         * 导出配置
         */
        export() {
            return JSON.stringify({
                version: CONFIG_VERSION,
                config: this.config,
                exportedAt: new Date().toISOString()
            }, null, 2);
        }

        /**
         * 导入配置
         */
        import(configJson) {
            try {
                const imported = JSON.parse(configJson);
                if (imported.config) {
                    this.config = { ...DEFAULT_CONFIG, ...imported.config };
                    this.saveToLocalStorage(this.config);
                    this.notifyObservers();
                    return { success: true };
                }
                return { success: false, message: '配置格式不正确' };
            } catch (error) {
                return { success: false, message: error.message };
            }
        }
    }

    // ==================== 全局实例 ====================
    const configManager = new ConfigManager();

    // ==================== 暴露到全局 ====================
    window.AppConfig = {
        // 快捷访问方法
        get: (key) => configManager.get(key),
        set: (key, value, persist) => configManager.set(key, value, persist),
        reset: () => configManager.reset(),
        getApiBase: () => configManager.getApiBase(),
        getApiUrl: (endpoint) => configManager.getApiUrl(endpoint),
        testConnection: () => configManager.testConnection(),
        subscribe: (observer) => configManager.subscribe(observer),
        export: () => configManager.export(),
        import: (configJson) => configManager.import(configJson),

        // 访问管理器实例
        manager: configManager,

        // 版本信息
        version: CONFIG_VERSION
    };

    // ==================== 控制台快捷命令 ====================
    if (window.console) {
        console.log('%c[配置管理]', 'color: #3b82f6; font-weight: bold;', '已加载');
        console.log('%c当前API地址:', 'color: #6b7280;', window.AppConfig.getApiBase());
        console.log('%c提示:', 'color: #10b981;', '使用 AppConfig.get() 查看完整配置');
        console.log('%c提示:', 'color: #10b981;', 'URL参数示例: ?api_base=http://localhost:8000/api');
    }

})(window);
