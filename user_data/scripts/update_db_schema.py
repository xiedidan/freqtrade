#!/usr/bin/env python3
"""
数据库迁移脚本：为price_levels表添加confirm_close字段
"""
import argparse
import json
import logging
import sys
import os
from pathlib import Path

# 添加freqtrade目录到搜索路径
sys.path.append(str(Path(__file__).parents[2]))

from sqlalchemy import create_engine, text, Column, Integer
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from freqtrade.persistence.models import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("db_migration")

def setup_db(config_file: str) -> tuple:
    """初始化数据库连接"""
    try:
        # 读取配置文件
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # 获取数据库URL
        db_url = config.get('db_url', None)
        if not db_url:
            logger.error("配置文件中未找到数据库URL")
            return None, None
        
        # 初始化数据库连接
        init_db(db_url)
        
        # 创建引擎
        engine = create_engine(db_url)
        
        logger.info(f"已连接到数据库: {db_url}")
        return engine, config
    except Exception as e:
        logger.error(f"连接数据库失败: {e}")
        return None, None

def check_column_exists(engine, table_name, column_name):
    """检查列是否已存在"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result]
            return column_name in columns
    except SQLAlchemyError as e:
        logger.error(f"检查列时发生错误: {e}")
        return False

def add_confirm_close_column(engine):
    """添加confirm_close列到price_levels表"""
    try:
        with engine.connect() as conn:
            # 检查列是否已存在
            if check_column_exists(engine, 'price_levels', 'confirm_close'):
                logger.info("confirm_close列已存在，跳过添加")
                return True
            
            # 添加列
            conn.execute(text("ALTER TABLE price_levels ADD COLUMN confirm_close INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
            logger.info("成功添加confirm_close列到price_levels表")
            return True
    except OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            logger.info("列已存在，继续执行")
            return True
        logger.error(f"添加列时发生错误: {e}")
        return False
    except SQLAlchemyError as e:
        logger.error(f"添加列时发生SQL错误: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="为price_levels表添加confirm_close字段")
    parser.add_argument('--config', '-c', required=True, help='Freqtrade配置文件路径')
    args = parser.parse_args()
    
    # 设置数据库连接
    engine, config = setup_db(args.config)
    if not engine:
        sys.exit(1)
    
    # 执行迁移
    if add_confirm_close_column(engine):
        logger.info("数据库迁移成功完成")
    else:
        logger.error("数据库迁移失败")
        sys.exit(1)
    
    logger.info("请重新启动price_levels_web.py以使用新功能")

if __name__ == "__main__":
    main() 