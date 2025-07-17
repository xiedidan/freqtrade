#!/bin/bash

# 启动价格监控点位管理 Web 服务

# 设置默认配置文件路径
CONFIG_FILE="user_data/price_levels_config.json"
STRATEGY_CONFIG_FILE=""
STRATEGY_NAME=""
STRATEGY_ENABLED=false

# 检查是否需要安装依赖
check_dependencies() {
    echo "检查依赖..."
    python3 -c "import flask" 2>/dev/null || {
        echo "未安装 Flask，正在安装..."
        pip install flask
    }
}

# 创建必要的目录
create_directories() {
    echo "创建必要的目录..."
    mkdir -p user_data/scripts/templates
    mkdir -p user_data/scripts/static
}

# 显示帮助信息
show_help() {
    echo "价格监控点位管理 Web 服务启动脚本"
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -c, --config FILE    指定配置文件路径 (默认: $CONFIG_FILE)"
    echo "  -s, --strategy NAME  指定要启动的策略名称"
    echo "  -f, --strategy-config FILE  指定策略配置文件路径"
    echo "  -h, --help           显示此帮助信息"
    echo ""
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -c|--config)
            CONFIG_FILE="$2"
            shift
            shift
            ;;
        -s|--strategy)
            STRATEGY_NAME="$2"
            STRATEGY_ENABLED=true
            shift
            shift
            ;;
        -f|--strategy-config)
            STRATEGY_CONFIG_FILE="$2"
            shift
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项: $key"
            show_help
            exit 1
            ;;
    esac
done

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo "错误: 配置文件 '$CONFIG_FILE' 不存在"
    exit 1
fi

# 如果启用策略，检查策略配置
if [ "$STRATEGY_ENABLED" = true ]; then
    if [ -z "$STRATEGY_NAME" ]; then
        echo "错误: 需要指定策略名称 (-s 或 --strategy)"
        exit 1
    fi
    
    if [ ! -z "$STRATEGY_CONFIG_FILE" ] && [ ! -f "$STRATEGY_CONFIG_FILE" ]; then
        echo "错误: 策略配置文件 '$STRATEGY_CONFIG_FILE' 不存在"
        exit 1
    fi
fi

# 启动交易策略
start_strategy() {
    if [ "$STRATEGY_ENABLED" = true ]; then
        echo "启动交易策略: $STRATEGY_NAME"
        
        STRATEGY_CMD="freqtrade trade --strategy $STRATEGY_NAME"
        
        if [ ! -z "$STRATEGY_CONFIG_FILE" ]; then
            STRATEGY_CMD="$STRATEGY_CMD --config $STRATEGY_CONFIG_FILE"
        fi
        
        echo "执行命令: $STRATEGY_CMD"
        $STRATEGY_CMD &
        STRATEGY_PID=$!
        echo "策略进程 ID: $STRATEGY_PID"
    fi
}

# 主函数
main() {
    check_dependencies
    create_directories
    
    echo "启动价格监控点位管理 Web 服务..."
    echo "配置文件: $CONFIG_FILE"
    
    # 启动交易策略
    start_strategy
    
    # 启动 Web 服务
    python3 user_data/scripts/price_levels_web.py --config "$CONFIG_FILE"
}

main 