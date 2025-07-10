#!/bin/bash

# 启动价格监控点位管理 Web 服务

# 设置默认配置文件路径
CONFIG_FILE="user_data/price_levels_config.json"

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

# 主函数
main() {
    check_dependencies
    create_directories
    
    echo "启动价格监控点位管理 Web 服务..."
    echo "配置文件: $CONFIG_FILE"
    
    # 启动 Web 服务
    python3 user_data/scripts/price_levels_web.py --config "$CONFIG_FILE"
}

main 