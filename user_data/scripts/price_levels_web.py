#!/usr/bin/env python3
"""
Web service to manage price levels for ATRLevelSignal strategy
"""
import argparse
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import wraps
from datetime import datetime
from flask import session
from sqlalchemy.exc import SQLAlchemyError

# Append freqtrade directory to path
sys.path.append(str(Path(__file__).parents[2]))

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from freqtrade.persistence.models import init_db
from freqtrade.enums import RunMode, TradingMode
from user_data.strategies.atr_level_signal import ATRLevelSignal, LevelDirection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("price_levels_web")

# Initialize Flask app
app = Flask(__name__, 
            template_folder=str(Path(__file__).parent / 'templates'),
            static_folder=str(Path(__file__).parent / 'static'))

# Set secret key for session
app.secret_key = os.urandom(24)

# Set default language
app.config['DEFAULT_LANGUAGE'] = 'zh'  # Default to Chinese

# Global config variable
CONFIG = {}

# Language dictionaries
TRANSLATIONS = {
    'en': {
        'title': 'ATRLevelSignal Price Level Management',
        'add_new_level': 'Add New Level',
        'edit_level': 'Edit Price Level',
        'pair': 'Trading Pair',
        'select_pair': 'Select pair...',
        'search_pairs': 'Type to search pairs...',
        'filter_pairs': 'Filter pairs...',
        'total_pairs': '{0} pairs available',
        'loading_pairs': 'Loading all pairs...',
        'pairs_loaded': 'All {0} pairs loaded',
        'no_pairs_found': 'No trading pairs found. Please check exchange connection.',
        'proxy_error': 'Connection or proxy error. Please check your proxy settings in the config file.',
        'check_config_proxy': 'Make sure you have added the correct proxy configuration to your config file.',
        'test_proxy': 'Test Proxy Connection',
        'testing_proxy': 'Testing proxy connection...',
        'proxy_test_results': 'Proxy Test Results',
        'proxy_test_success': 'Proxy test successful! All connections working.',
        'proxy_test_partial': 'Some proxy tests failed. See details below.',
        'proxy_test_failed': 'All proxy tests failed. Please check your proxy configuration.',
        'proxy_config_fixed': 'Problems were detected in your proxy configuration and automatically fixed. Please update your config file with the correct format shown below.',
        'warning': 'Warning',
        'price_level': 'Price Level',
        'direction': 'Direction',
        'up': 'Up (price crosses from below)',
        'down': 'Down (price crosses from above)',
        'both': 'Both (price crosses from any direction)',
        'wick_up': 'Wick Up Liquidity Sweep',
        'wick_down': 'Wick Down Liquidity Sweep',
        'wick_both': 'Bidirectional Liquidity Sweep',
        'confirm_close': 'Require Close Confirmation',
        'confirm_close_hint': 'If checked, signal will only trigger when candle closes beyond the level',
        'confirm_close_yes': 'Candle close confirmation required',
        'confirm_close_no': 'Trigger on any price cross',
        'add': 'Add',
        'edit': 'Edit',
        'delete': 'Delete',
        'cancel': 'Cancel',
        'save': 'Save Changes',
        'get_current_price': 'Get Current Price',
        'statistics': 'Statistics',
        'total_levels': 'Total Levels',
        'up_levels': 'Up Levels',
        'down_levels': 'Down Levels',
        'existing_levels': 'Existing Levels',
        'show_all': 'Show All',
        'id': 'ID',
        'trading_pair': 'Trading Pair',
        'actions': 'Actions',
        'confirm_delete': 'Are you sure you want to delete this level?',
        'notification': 'Notification',
        'success': 'Success',
        'error': 'Error',
        'added_level': 'Added price level {0} for {1}',
        'add_failed': 'Add failed: {0}',
        'deleted_level': 'Deleted price level',
        'delete_failed': 'Delete failed: {0}',
        'footer': 'ATRLevelSignal Price Level Management',
        'return_home': 'Return Home',
        'error_title': 'Error - ATRLevelSignal',
        'refresh_pairs': 'Refresh Pairs',
        'refresh_binance_usdt_spot': 'Refresh Binance USDT SPOT Pairs',
        'check_inactive_pairs': 'Check Inactive Pairs',
        'inactive_pair': 'INACTIVE',
        'active_pair': 'ACTIVE',
        'inactive_pairs_found': 'Found {0} inactive pairs',
        'all_pairs_active': 'All pairs are active',
        'checking_pairs': 'Checking pairs status...',
        # New translations for signal history page
        'signal_history': 'Signal History',
        'signal_history_title': 'ATRLevelSignal Signal History',
        'filter_signals': 'Filter Signals',
        'signal_type': 'Signal Type',
        'all_signal_types': 'All Signal Types',
        'level_cross_up': 'Level Cross Up',
        'level_cross_down': 'Level Cross Down',
        'level_wick_up': 'Wick Up Liquidity Sweep',
        'level_wick_down': 'Wick Down Liquidity Sweep',
        'atr_surge': 'ATR Surge',
        'start_date': 'Start Date',
        'end_date': 'End Date',
        'apply_filters': 'Apply Filters',
        'reset_filters': 'Reset Filters',
        'signal_time': 'Signal Time',
        'prev_price': 'Previous Price',
        'current_price': 'Current Price',
        'price_change': 'Price Change',
        'price_change_pct': 'Change %',
        'atr_value': 'ATR Value',
        'level_info': 'Level Info',
        'no_signals_found': 'No signals found with the current filters.',
        'manage_levels': 'Manage Price Levels',
        'view_signal_history': 'View Signal History',
        'loading_signals': 'Loading signals...',
        'total_signals': '{0} signals found',
        'export_csv': 'Export to CSV',
        'last_signals': 'Last {0} Signals',
        'page_info': 'Page {0} of {1} (Total: {2} signals)',
        'per_page': 'Per page',
        'prev_page': 'Previous',
        'next_page': 'Next'
    },
    'zh': {
        'title': 'ATRLevelSignal 价格监控点位管理',
        'add_new_level': '添加新监控点位',
        'edit_level': '编辑价格点位',
        'pair': '交易对',
        'select_pair': '选择交易对...',
        'search_pairs': '输入关键字搜索交易对...',
        'filter_pairs': '筛选交易对...',
        'total_pairs': '共有 {0} 个交易对',
        'loading_pairs': '正在加载所有交易对...',
        'pairs_loaded': '已加载全部 {0} 个交易对',
        'no_pairs_found': '未找到任何交易对。请检查交易所连接。',
        'proxy_error': '连接或代理错误。请检查配置文件中的代理设置。',
        'check_config_proxy': '请确保您在配置文件中添加了正确的代理配置。',
        'test_proxy': '测试代理连接',
        'testing_proxy': '正在测试代理连接...',
        'proxy_test_results': '代理测试结果',
        'proxy_test_success': '代理测试成功！所有连接正常。',
        'proxy_test_partial': '部分代理测试失败。请查看下方详情。',
        'proxy_test_failed': '所有代理测试均失败。请检查您的代理配置。',
        'proxy_config_fixed': '在您的代理配置中检测到问题并已自动修复。请使用下方显示的正确格式更新您的配置文件。',
        'warning': '警告',
        'price_level': '价格点位',
        'direction': '监控方向',
        'up': '上穿 (价格从下方穿越)',
        'down': '下穿 (价格从上方穿越)',
        'both': '双向 (价格从任意方向穿越)',
        'wick_up': '上影线流动性清扫',
        'wick_down': '下影线流动性清扫',
        'wick_both': '双向流动性清扫',
        'confirm_close': '收盘确认',
        'confirm_close_hint': '如果选中，只有当K线收盘价突破点位时才会触发信号',
        'confirm_close_yes': '需要收盘确认',
        'confirm_close_no': '任意价格突破即触发',
        'add': '添加',
        'edit': '编辑',
        'delete': '删除',
        'cancel': '取消',
        'save': '保存修改',
        'get_current_price': '获取当前价格',
        'statistics': '统计信息',
        'total_levels': '总点位数',
        'up_levels': '上穿点位',
        'down_levels': '下穿点位',
        'existing_levels': '现有监控点位',
        'show_all': '全部显示',
        'id': 'ID',
        'trading_pair': '交易对',
        'actions': '操作',
        'confirm_delete': '确定要删除此监控点位吗?',
        'notification': '通知',
        'success': '成功',
        'error': '错误',
        'added_level': '已添加 {1} 的价格点位 {0}',
        'add_failed': '添加失败: {0}',
        'deleted_level': '已删除价格点位',
        'delete_failed': '删除失败: {0}',
        'footer': 'ATRLevelSignal 价格监控点位管理',
        'return_home': '返回首页',
        'error_title': '错误 - ATRLevelSignal',
        'refresh_pairs': '刷新交易对',
        'refresh_binance_usdt_spot': '刷新币安USDT现货交易对',
        'check_inactive_pairs': '检查无效交易对',
        'inactive_pair': '已下线',
        'active_pair': '正常',
        'inactive_pairs_found': '发现 {0} 个已下线交易对',
        'all_pairs_active': '所有交易对均正常',
        'checking_pairs': '正在检查交易对状态...',
        # New translations for signal history page
        'signal_history': '信号历史记录',
        'signal_history_title': 'ATRLevelSignal 信号历史',
        'filter_signals': '筛选信号',
        'signal_type': '信号类型',
        'all_signal_types': '所有信号类型',
        'level_cross_up': '上穿点位',
        'level_cross_down': '下穿点位',
        'level_wick_up': '上影线扫动流动性',
        'level_wick_down': '下影线扫动流动性',
        'atr_surge': 'ATR 剧增',
        'start_date': '开始日期',
        'end_date': '结束日期',
        'apply_filters': '应用筛选',
        'reset_filters': '重置筛选',
        'signal_time': '信号时间',
        'prev_price': '前一价格',
        'current_price': '当前价格',
        'price_change': '价格变化',
        'price_change_pct': '变化百分比',
        'atr_value': 'ATR 值',
        'level_info': '点位信息',
        'no_signals_found': '当前筛选条件下没有找到信号。',
        'manage_levels': '管理价格点位',
        'view_signal_history': '查看信号历史',
        'loading_signals': '正在加载信号...',
        'total_signals': '找到 {0} 个信号',
        'export_csv': '导出为 CSV',
        'last_signals': '最近 {0} 个信号',
        'page_info': '第 {0} 页，共 {1} 页（总计：{2} 条信号）',
        'per_page': '每页显示',
        'prev_page': '上一页',
        'next_page': '下一页'
    }
}

def get_translation(key, lang='en'):
    """Get translation for a key in the specified language"""
    if lang not in TRANSLATIONS:
        lang = 'en'
    return TRANSLATIONS[lang].get(key, key)

def setup_db(config_file: str) -> bool:
    """Initialize database connection"""
    global CONFIG
    
    # Read config file to get database URL
    try:
        with open(config_file, 'r') as f:
            CONFIG = json.load(f)
        
        # Get database URL from config
        db_url = CONFIG.get('db_url', None)
        if not db_url:
            logger.error("Database URL not found in config file")
            return False
        
        # Initialize database connection
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker, scoped_session
        from user_data.strategies.atr_level_signal import PriceLevel
        
        # Initialize database connection
        init_db(db_url)
        
        # Create engine and session for PriceLevel
        engine = create_engine(db_url)
        session = scoped_session(sessionmaker(bind=engine))
        
        # Set the session for PriceLevel
        PriceLevel.session = session
        
        logger.info(f"Connected to database: {db_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return False

def get_available_pairs(usdt_only: bool = False, spot_only: bool = False, include_existing: bool = True) -> List[dict]:
    """Get list of available trading pairs from config and exchange
    
    Args:
        usdt_only: If True, only return USDT pairs
        spot_only: If True, only return SPOT market pairs
        include_existing: If True, include pairs from existing price levels
        
    Returns:
        List of dicts with pair info including volume
    """
    pairs = []
    pair_volumes = {}
    
    # Get pairs from whitelist
    if 'exchange' in CONFIG and 'pair_whitelist' in CONFIG['exchange']:
        whitelist = CONFIG['exchange']['pair_whitelist']
        logger.info(f"Found {len(whitelist)} pairs in whitelist")
        for pair in whitelist:
            if pair not in [p['pair'] for p in pairs]:
                pairs.append({'pair': pair, 'volume': 0})
    
    # Add any pairs from existing price levels that might not be in whitelist
    if include_existing:
        try:
            levels = ATRLevelSignal.get_price_levels()
            existing_pairs = [level['pair'] for level in levels if level['pair'] not in [p['pair'] for p in pairs]]
            
            if existing_pairs:
                logger.info(f"Adding {len(existing_pairs)} pairs from existing price levels")
                for pair in existing_pairs:
                    pairs.append({'pair': pair, 'volume': 0})
        except Exception as e:
            logger.error(f"Error getting pairs from price levels: {e}")
    
    # Try to get all available pairs from exchange with volume data
    try:
        import asyncio
        from freqtrade.exchange import Exchange
        from freqtrade.resolvers.exchange_resolver import ExchangeResolver
        
        # Get exchange name from config
        exchange_name = CONFIG.get('exchange', {}).get('name', 'binance')
        
        # Initialize exchange
        exchange_config = CONFIG.get('exchange', {}).copy()
        
        # Get proxy configuration from config if available
        proxy_config = {}
        ccxt_proxy_config = {}
        
        # 检查exchange部分内的ccxt_config
        if 'exchange' in CONFIG and 'ccxt_config' in CONFIG['exchange']:
            ccxt_proxy_config = CONFIG['exchange']['ccxt_config']
            logger.info(f"Found standard CCXT config in exchange section: {ccxt_proxy_config}")
        
        # 检查顶层的代理配置 (老方式)
        if 'proxy' in CONFIG:
            proxy_config = CONFIG['proxy']
            logger.info(f"Found legacy proxy configuration at top level: {proxy_config}")
        # 检查exchange部分内的代理配置 (老方式)
        elif 'exchange' in CONFIG and 'proxy' in CONFIG['exchange']:
            proxy_config = CONFIG['exchange']['proxy']
            logger.info(f"Found legacy proxy configuration in exchange section: {proxy_config}")
            
        # Create proper config structure as expected by the function
        full_config = {
            'exchange': {'name': exchange_name, **exchange_config},
            'dry_run': True,  # This needs to be at the top level of the config
            'stake_currency': exchange_config.get('stake_currency', 'USDT'),  # Required by exchange validation
            'entry_pricing': {'price_side': 'same'},  # Required by exchange validation
            'exit_pricing': {'price_side': 'same'},  # Required by exchange validation
            'runmode': RunMode.WEBSERVER,  # Required to avoid 'runmode' error
            'trading_mode': TradingMode.SPOT,  # Required by exchange validation
            'candle_type_def': {
                'spot': {
                    '1m': {'timeframe': '1m', 'include_in_strategy': True},
                    '5m': {'timeframe': '5m', 'include_in_strategy': True},
                    '15m': {'timeframe': '15m', 'include_in_strategy': True},
                    '1h': {'timeframe': '1h', 'include_in_strategy': True},
                    '4h': {'timeframe': '4h', 'include_in_strategy': True},
                    '1d': {'timeframe': '1d', 'include_in_strategy': True},
                }
            },  # Required by exchange validation
        }
        
        # 直接使用标准CCXT格式
        if ccxt_proxy_config:
            # 直接使用原始ccxt_config
            full_config['exchange']['ccxt_config'] = ccxt_proxy_config
            logger.info(f"Using standard CCXT config: {ccxt_proxy_config}")
        # 如果有老格式的代理配置，转换为标准CCXT格式
        elif proxy_config:
            # 转换为标准CCXT格式
            ccxt_config = {
                'enableRateLimit': True,
                'timeout': CONFIG.get('exchange_request_timeout', 30000)  # 默认30秒
            }
            
            # 设置代理
            if 'http' in proxy_config:
                ccxt_config['httpProxy'] = proxy_config['http']
            if 'https' in proxy_config:
                ccxt_config['httpsProxy'] = proxy_config['https']
                # 同时设置wsProxy，因为WebSocket通常也需要代理
                ccxt_config['wsProxy'] = proxy_config['https']
                
            full_config['exchange']['ccxt_config'] = ccxt_config
            logger.info(f"Converted legacy proxy config to CCXT format: {ccxt_config}")
        
        # Add exchange request timeout if specified in config
        if 'exchange_request_timeout' in CONFIG:
            timeout = CONFIG['exchange_request_timeout']
            logger.info(f"Using custom exchange request timeout: {timeout} seconds")
            full_config['exchange_requests_params'] = {'timeout': timeout}
        
        # 解决asyncio事件循环问题
        try:
            # 检查是否已有事件循环在运行
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已有循环在运行，创建一个新的循环
                    logger.info("Event loop is already running, creating a new one")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                # 如果没有事件循环，创建一个新的
                logger.info("No event loop found, creating a new one")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Initialize exchange with proper config
            exchange = ExchangeResolver.load_exchange(config=full_config)
            
            # 打印更多诊断信息
            logger.info(f"Exchange instance created: {exchange}")
            logger.info(f"CCXT exchange instance: {exchange._api}")
            
            # 尝试获取交易所配置
            try:
                ccxt_config = exchange._api.options
                logger.info(f"CCXT exchange options: {ccxt_config}")
                logger.info(f"CCXT proxy settings: {exchange._api.proxies if hasattr(exchange._api, 'proxies') else 'None'}")
            except Exception as e:
                logger.error(f"Error getting CCXT config: {e}")
            
            # Get all markets
            logger.info("Attempting to get markets from exchange...")
            markets = exchange.get_markets()
            logger.info(f"Got {len(markets)} raw markets from exchange {exchange_name}")
            
            # 尝试获取交易量数据
            pair_volumes = {}
            logger.info("Attempting to get volume data for pairs...")
            try:
                # 获取24小时交易量数据
                tickers = {}
                # 对于binance使用fetch_tickers，一次性获取所有交易对数据
                if exchange_name.lower() == 'binance':
                    tickers = exchange._api.fetch_tickers()
                    logger.info(f"Got tickers for {len(tickers)} pairs from {exchange_name}")
                else:
                    # 对于其他交易所，可能需要单独获取
                    logger.info(f"Volume data fetching not optimized for {exchange_name}, skipping...")
                
                # 从tickers中提取交易量数据
                for symbol, ticker in tickers.items():
                    if 'quoteVolume' in ticker and ticker['quoteVolume']:
                        # 使用报价货币的交易量（如USDT交易量）
                        pair_volumes[symbol] = float(ticker['quoteVolume'])
                    elif 'baseVolume' in ticker and ticker['baseVolume']:
                        # 如果没有报价货币交易量，使用基础货币交易量
                        pair_volumes[symbol] = float(ticker['baseVolume'])
                    else:
                        # 如果都没有，设置为0
                        pair_volumes[symbol] = 0
                        
                logger.info(f"Successfully obtained volume data for {len(pair_volumes)} pairs")
            except Exception as e:
                logger.error(f"Error getting volume data: {e}")
                logger.error(traceback.format_exc())
            
            # 确保正确关闭exchange
            try:
                # 对于异步交易所，需要正确关闭
                if hasattr(exchange, 'close'):
                    if asyncio.iscoroutinefunction(exchange.close):
                        loop.run_until_complete(exchange.close())
                    else:
                        exchange.close()
                
                # 如果交易所有_api_async属性，也需要关闭它
                if hasattr(exchange, '_api_async') and exchange._api_async is not None:
                    if hasattr(exchange._api_async, 'close'):
                        if asyncio.iscoroutinefunction(exchange._api_async.close):
                            loop.run_until_complete(exchange._api_async.close())
                        else:
                            exchange._api_async.close()
                
                logger.info("Exchange connection closed properly")
            except Exception as e:
                logger.error(f"Error closing exchange connection: {e}")
            
            # Convert markets to list if it's not already (some exchange implementations return dicts)
            if isinstance(markets, dict):
                markets = list(markets.keys())
            
            # Filter for USDT pairs if requested
            if usdt_only:
                markets = [m for m in markets if m.endswith('/USDT')]
                logger.info(f"Filtered to {len(markets)} USDT markets")
            
            # Filter for spot markets if requested
            if spot_only and exchange_name.lower() == 'binance':
                # For Binance, we need to check if the market is spot
                spot_markets = []
                try:
                    # Get markets info to check if spot
                    markets_info = exchange._api.fetch_markets()
                    spot_markets = [m['symbol'] for m in markets_info if m['spot']]
                    markets = [m for m in markets if m in spot_markets]
                    logger.info(f"Filtered to {len(markets)} spot markets")
                except Exception as e:
                    logger.warning(f"Could not filter for spot markets: {e}")
            
            # Clear existing pairs list to ensure we get fresh data
            pairs = []
            
            # Add filtered markets to pairs list with volume data
            for market in markets:
                if market not in [p['pair'] for p in pairs]:
                    volume = pair_volumes.get(market, 0)
                    pairs.append({
                        'pair': market,
                        'volume': volume
                    })
                    
            logger.info(f"Loaded {len(pairs)} pairs from exchange {exchange_name}")
        finally:
            # 关闭事件循环
            try:
                if 'loop' in locals() and loop and not loop.is_closed():
                    # 取消所有未完成的任务
                    for task in asyncio.all_tasks(loop):
                        task.cancel()
                    
                    # 等待所有任务取消完成
                    if asyncio.all_tasks(loop):
                        loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
                    
                    # 关闭循环
                    loop.close()
                    logger.info("Event loop closed properly")
            except Exception as e:
                logger.error(f"Error closing event loop: {e}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Could not load pairs from exchange: {error_msg}")
        
        # Import traceback for detailed error logging
        import traceback
        logger.error(traceback.format_exc())
        
        # Add more helpful error messages for common proxy issues
        if 'proxy' in error_msg.lower() or 'timeout' in error_msg.lower() or 'connection' in error_msg.lower():
            logger.error("This appears to be a proxy or connection issue. Please check your proxy settings.")
            # Add an indicator that this was likely a proxy error
            pairs.append({'pair': "ERROR_PROXY_CONNECTION", 'volume': 0})
    
    # 按照交易量排序，从高到低
    pairs.sort(key=lambda x: x.get('volume', 0), reverse=True)
    logger.info(f"Pairs sorted by volume, highest first")
    
    return pairs

def check_inactive_pairs() -> Dict[str, bool]:
    """Check if existing price level pairs are still active on the exchange
    
    Returns:
        Dict mapping pair names to boolean (True if active, False if inactive)
    """
    result = {}
    
    try:
        # Get all current active pairs from exchange
        all_pairs = get_available_pairs(spot_only=True)
        active_pairs = set(p['pair'] for p in all_pairs)
        
        # Get all pairs from price levels
        levels = ATRLevelSignal.get_price_levels()
        level_pairs = set(level['pair'] for level in levels)
        
        # Check each level pair if it's in active pairs
        for pair in level_pairs:
            result[pair] = pair in active_pairs
            
        logger.info(f"Checked {len(level_pairs)} pairs for activity status")
    except SQLAlchemyError as e:
        logger.error(f"Database error checking inactive pairs: {e}")
        # Return an empty dict in case of database error
        return {}
    except Exception as e:
        logger.error(f"Error checking inactive pairs: {e}")
    
    return result

def check_auth(username, password):
    """Check if a username/password combination is valid."""
    web_config = CONFIG.get('web_config', {})
    expected_username = web_config.get('username', 'admin')
    expected_password = web_config.get('password', 'changeme')
    return username == expected_username and password == expected_password

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        web_config = CONFIG.get('web_config', {})
        # Skip authentication if username is not set
        if not web_config.get('username'):
            return f(*args, **kwargs)
            
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@requires_auth
def index():
    """Main page"""
    try:
        # Get all price levels
        levels = ATRLevelSignal.get_price_levels()
        
        # Start with whitelist pairs first (faster loading)
        pairs = []
        if 'exchange' in CONFIG and 'pair_whitelist' in CONFIG['exchange']:
            pairs.extend(CONFIG['exchange']['pair_whitelist'])
        
        # Add existing pairs from levels
        existing_pairs = []
        for level in levels:
            if level['pair'] not in pairs:
                pairs.append(level['pair'])
                existing_pairs.append(level['pair'])
        
        if existing_pairs:
            logger.info(f"Adding {len(existing_pairs)} pairs from existing price levels to initial display")
        
        pairs = sorted(pairs)
        
        # Flag to indicate if we're loading all exchange pairs (initial value is false to avoid UI confusion)
        loading_all_pairs = False
        
        # Add current date and time for footer
        now = datetime.now()
        
        # Get user's language preference from session or use default
        lang = session.get('language', app.config['DEFAULT_LANGUAGE'])
        
        # Create a translation function for the template
        def t(key, *args):
            text = get_translation(key, lang)
            for i, arg in enumerate(args):
                text = text.replace(f"{{{i}}}", str(arg))
            return text
        
        return render_template('index.html', 
                              levels=levels, 
                              pairs=pairs,
                              directions=[d.value for d in LevelDirection],
                              now=now,
                              lang=lang,
                              loading_all_pairs=loading_all_pairs,
                              t=t)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        lang = session.get('language', app.config['DEFAULT_LANGUAGE'])
        def t(key, *args):
            text = get_translation(key, lang)
            for i, arg in enumerate(args):
                text = text.replace(f"{{{i}}}", str(arg))
            return text
        return render_template('error.html', error=str(e), 
                              lang=lang, 
                              t=t)

@app.route('/signal_history')
@requires_auth
def signal_history_page():
    """Signal history page"""
    try:
        # Get all unique pairs from signal history
        signals = ATRLevelSignal.get_signal_history(limit=1000)
        
        # Extract unique pairs for filtering
        unique_pairs = set()
        for signal in signals:
            unique_pairs.add(signal['pair'])
        
        pairs = sorted(list(unique_pairs))
        
        # Add current date and time for footer
        now = datetime.now()
        
        # Get user's language preference from session or use default
        lang = session.get('language', app.config['DEFAULT_LANGUAGE'])
        
        # Create a translation function for the template
        def t(key, *args):
            text = get_translation(key, lang)
            for i, arg in enumerate(args):
                text = text.replace(f"{{{i}}}", str(arg))
            return text
        
        return render_template('signal_history.html', 
                              signals=signals[:100],  # Only send first 100 for initial page load
                              pairs=pairs,
                              now=now,
                              lang=lang,
                              t=t)
    except Exception as e:
        logger.error(f"Error in signal history route: {e}")
        import traceback
        logger.error(traceback.format_exc())
        lang = session.get('language', app.config['DEFAULT_LANGUAGE'])
        def t(key, *args):
            text = get_translation(key, lang)
            for i, arg in enumerate(args):
                text = text.replace(f"{{{i}}}", str(arg))
            return text
        return render_template('error.html', error=str(e), 
                              lang=lang, 
                              t=t)

@app.route('/api/levels', methods=['GET'])
@requires_auth
def get_levels():
    """API endpoint to get all price levels"""
    try:
        pair = request.args.get('pair', None)
        levels = ATRLevelSignal.get_price_levels(pair)
        return jsonify({"success": True, "levels": levels})
    except SQLAlchemyError as e:
        logger.error(f"Database error getting levels: {e}")
        return jsonify({"success": False, "error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error getting levels: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/levels', methods=['POST'])
@requires_auth
def add_level():
    """API endpoint to add a new price level"""
    try:
        data = request.get_json()
        pair = data.get('pair')
        level = float(data.get('level'))
        direction = data.get('direction', 'both')
        confirm_close = data.get('confirm_close', False)
        
        # Validate inputs
        if not pair:
            return jsonify({"success": False, "error": "Pair is required"})
        if not level:
            return jsonify({"success": False, "error": "Level is required"})
        if direction not in [d.value for d in LevelDirection]:
            return jsonify({"success": False, "error": f"Direction must be one of: {', '.join([d.value for d in LevelDirection])}"})
        
        result = ATRLevelSignal.add_price_level(pair, level, direction, confirm_close)
        
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]})
        else:
            return jsonify({"success": True, "level": result})
    except SQLAlchemyError as e:
        logger.error(f"Database error adding level: {e}")
        return jsonify({"success": False, "error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error adding level: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/levels/<int:level_id>', methods=['DELETE'])
@requires_auth
def delete_level(level_id):
    """API endpoint to delete a price level"""
    try:
        result = ATRLevelSignal.delete_price_level(level_id)
        return jsonify(result)
    except SQLAlchemyError as e:
        logger.error(f"Database error deleting level: {e}")
        return jsonify({"success": False, "error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error deleting level: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/levels/<int:level_id>', methods=['PUT'])
@requires_auth
def update_level(level_id):
    """API endpoint to update an existing price level"""
    try:
        data = request.get_json()
        level_value = float(data.get('level'))
        direction = data.get('direction', 'both')
        confirm_close = data.get('confirm_close', False)
        
        # 验证输入
        if not level_value:
            return jsonify({"success": False, "error": "Level is required"})
        if direction not in [d.value for d in LevelDirection]:
            return jsonify({"success": False, "error": f"Direction must be one of: {', '.join([d.value for d in LevelDirection])}"})
        
        # 更新数据库中的记录
        try:
            from user_data.strategies.atr_level_signal import PriceLevel
            price_level = PriceLevel.session.get(PriceLevel, level_id)
            
            if not price_level:
                return jsonify({"success": False, "error": f"Price level with ID {level_id} not found"})
            
            # 更新数据
            price_level.level = level_value
            price_level.direction = direction
            price_level.confirm_close = 1 if confirm_close else 0
            
            # 保存更改
            PriceLevel.session.commit()
            
            # 返回更新后的记录
            return jsonify({
                "success": True, 
                "level": {
                    "id": price_level.id,
                    "pair": price_level.pair,
                    "level": price_level.level,
                    "direction": price_level.direction,
                    "created_at": price_level.created_at.isoformat(),
                    "active": bool(price_level.active),
                    "confirm_close": bool(price_level.confirm_close)
                }
            })
        except SQLAlchemyError as e:
            logger.error(f"Database error updating level: {e}")
            return jsonify({"success": False, "error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error updating level: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/set_language/<lang>')
def set_language(lang):
    """Set the user's preferred language"""
    # Store the language preference in the session
    if lang in TRANSLATIONS:
        session['language'] = lang
    else:
        session['language'] = app.config['DEFAULT_LANGUAGE']
    
    # Redirect back to the previous page or to the home page
    return redirect(request.referrer or url_for('index'))

@app.route('/api/all_pairs')
@requires_auth
def get_all_pairs():
    """API endpoint to get all available pairs from exchange"""
    try:
        usdt_only = request.args.get('usdt_only', 'false').lower() == 'true'
        spot_only = request.args.get('spot_only', 'false').lower() == 'true'
        
        logger.info(f"Getting all pairs with usdt_only={usdt_only}, spot_only={spot_only}")
        
        # Always get a fresh list from exchange, don't rely on cache
        pairs = get_available_pairs(usdt_only=usdt_only, spot_only=spot_only)
        
        logger.info(f"Returning {len(pairs)} pairs to client")
        
        # Return both the simple pair list (for backwards compatibility) and the full pairs data
        pair_names = [p['pair'] for p in pairs]
        return jsonify({
            "success": True, 
            "pairs": pair_names,
            "pairs_data": pairs
        })
    except Exception as e:
        logger.error(f"Error getting all pairs: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/check_inactive_pairs')
@requires_auth
def api_check_inactive_pairs():
    """API endpoint to check if existing pairs are still active on the exchange"""
    try:
        inactive_pairs = check_inactive_pairs()
        return jsonify({"success": True, "pairs_status": inactive_pairs})
    except Exception as e:
        logger.error(f"Error checking inactive pairs: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/signal_history')
@requires_auth
def api_signal_history():
    """API endpoint to get signal history with optional filtering and pagination"""
    try:
        # Get filter parameters from request
        pair = request.args.get('pair', None)
        signal_type = request.args.get('signal_type', None)
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)
        
        # 分页参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        limit = int(request.args.get('limit', 0))  # 0表示不限制，使用分页
        
        # 如果指定了limit并且大于0，则优先使用limit参数（向后兼容）
        if limit > 0:
            signals = ATRLevelSignal.get_signal_history(
                pair=pair,
                signal_type=signal_type,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
            total_count = len(signals)
            total_pages = 1
            
            logger.info(f"Retrieved {len(signals)} signals with filters: pair={pair}, signal_type={signal_type}, limit={limit}")
            
            return jsonify({
                "success": True, 
                "signals": signals,
                "pagination": {
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "current_page": 1,
                    "per_page": limit
                }
            })
        else:
            # 获取总记录数
            total_signals = ATRLevelSignal.get_signal_history(
                pair=pair,
                signal_type=signal_type,
                start_date=start_date,
                end_date=end_date,
                limit=0  # 不限制，获取总数
            )
            total_count = len(total_signals)
            
            # 计算总页数
            total_pages = (total_count + per_page - 1) // per_page
            
            # 确保页码在有效范围内
            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages
            
            # 计算偏移量
            offset = (page - 1) * per_page
            
            # 获取当前页的数据
            signals = ATRLevelSignal.get_signal_history(
                pair=pair,
                signal_type=signal_type,
                start_date=start_date,
                end_date=end_date,
                limit=per_page,
                offset=offset
            )
            
            logger.info(f"Retrieved {len(signals)} signals for page {page} (offset={offset}, per_page={per_page}) with filters: pair={pair}, signal_type={signal_type}")
            
            return jsonify({
                "success": True, 
                "signals": signals,
                "pagination": {
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "current_page": page,
                    "per_page": per_page
                }
            })
    except Exception as e:
        logger.error(f"Error getting signal history: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/current_price/<path:pair>')
@requires_auth
def get_current_price(pair):
    """API endpoint to get current price for a trading pair"""
    try:
        import ccxt
        import traceback
        
        # 获取交易所名称
        exchange_name = CONFIG.get('exchange', {}).get('name', 'binance')
        
        # 获取CCXT配置
        ccxt_config = {}
        if 'exchange' in CONFIG and 'ccxt_config' in CONFIG['exchange']:
            ccxt_config = CONFIG['exchange']['ccxt_config']
        
        # 初始化交易所
        logger.info(f"获取 {pair} 的当前价格，使用交易所 {exchange_name}")
        exchange = getattr(ccxt, exchange_name)(ccxt_config)
        
        # 获取当前价格
        try:
            ticker = exchange.fetch_ticker(pair)
            current_price = ticker['last'] if ticker and 'last' in ticker else None
            
            if not current_price:
                # 如果无法获取最新价格，尝试使用收盘价
                current_price = ticker['close'] if ticker and 'close' in ticker else None
            
            logger.info(f"获取到 {pair} 的当前价格: {current_price}")
            return jsonify({"success": True, "price": current_price})
        except Exception as e:
            logger.error(f"获取 {pair} 价格时出错: {e}")
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)})
    except Exception as e:
        logger.error(f"获取价格时发生错误: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/test_proxy')
@requires_auth
def test_proxy():
    """API endpoint to test proxy connection"""
    try:
        import requests
        import time
        
        # 获取CCXT配置
        ccxt_config = {}
        proxy_urls = {}
        
        # 优先检查标准CCXT配置
        if 'exchange' in CONFIG and 'ccxt_config' in CONFIG['exchange']:
            ccxt_config = CONFIG['exchange']['ccxt_config']
            
            # 从CCXT配置中提取代理URL
            if 'httpProxy' in ccxt_config:
                proxy_urls['http'] = ccxt_config['httpProxy']
            if 'httpsProxy' in ccxt_config:
                proxy_urls['https'] = ccxt_config['httpsProxy']
            
            logger.info(f"Using standard CCXT config for proxy test: {ccxt_config}")
        # 如果没有CCXT配置，尝试使用老格式的代理配置
        elif 'proxy' in CONFIG:
            proxy_urls = CONFIG['proxy']
            logger.info(f"Using legacy proxy configuration for test: {proxy_urls}")
        elif 'exchange' in CONFIG and 'proxy' in CONFIG['exchange']:
            proxy_urls = CONFIG['exchange']['proxy']
            logger.info(f"Using legacy proxy configuration from exchange section: {proxy_urls}")
            
        if not proxy_urls and not ccxt_config:
            return jsonify({
                "success": False, 
                "error": "No proxy configuration found in config file"
            })
        
        # 存储测试结果
        results = {
            "ccxt_config": ccxt_config,
            "proxy_urls": proxy_urls,
            "tests": []
        }
        
        # 测试HTTP代理
        if 'http' in proxy_urls:
            http_proxy = proxy_urls['http']
            start_time = time.time()
            try:
                response = requests.get('http://api.ipify.org', 
                                       proxies={"http": http_proxy}, 
                                       timeout=10)
                if response.status_code == 200:
                    ip = response.text
                    results["tests"].append({
                        "type": "HTTP",
                        "proxy": http_proxy,
                        "success": True,
                        "time": f"{time.time() - start_time:.2f}s",
                        "ip": ip
                    })
                else:
                    results["tests"].append({
                        "type": "HTTP",
                        "proxy": http_proxy,
                        "success": False,
                        "error": f"Status code: {response.status_code}",
                        "time": f"{time.time() - start_time:.2f}s"
                    })
            except Exception as e:
                results["tests"].append({
                    "type": "HTTP",
                    "proxy": http_proxy,
                    "success": False,
                    "error": str(e),
                    "time": f"{time.time() - start_time:.2f}s"
                })
                
        # 测试HTTPS代理
        if 'https' in proxy_urls:
            https_proxy = proxy_urls['https']
            start_time = time.time()
            try:
                response = requests.get('https://api.ipify.org', 
                                      proxies={"https": https_proxy}, 
                                      timeout=10,
                                      verify=False)  # 忽略SSL证书验证
                if response.status_code == 200:
                    ip = response.text
                    results["tests"].append({
                        "type": "HTTPS",
                        "proxy": https_proxy,
                        "success": True,
                        "time": f"{time.time() - start_time:.2f}s",
                        "ip": ip
                    })
                else:
                    results["tests"].append({
                        "type": "HTTPS",
                        "proxy": https_proxy,
                        "success": False,
                        "error": f"Status code: {response.status_code}",
                        "time": f"{time.time() - start_time:.2f}s"
                    })
            except Exception as e:
                results["tests"].append({
                    "type": "HTTPS",
                    "proxy": https_proxy,
                    "success": False,
                    "error": str(e),
                    "time": f"{time.time() - start_time:.2f}s"
                })
        
        # 如果有httpsProxy，也测试它
        if 'httpsProxy' in ccxt_config:
            https_proxy = ccxt_config['httpsProxy']
            start_time = time.time()
            try:
                response = requests.get('https://api.ipify.org', 
                                      proxies={"https": https_proxy}, 
                                      timeout=10,
                                      verify=False)  # 忽略SSL证书验证
                if response.status_code == 200:
                    ip = response.text
                    results["tests"].append({
                        "type": "HTTPS (CCXT)",
                        "proxy": https_proxy,
                        "success": True,
                        "time": f"{time.time() - start_time:.2f}s",
                        "ip": ip
                    })
                else:
                    results["tests"].append({
                        "type": "HTTPS (CCXT)",
                        "proxy": https_proxy,
                        "success": False,
                        "error": f"Status code: {response.status_code}",
                        "time": f"{time.time() - start_time:.2f}s"
                    })
            except Exception as e:
                results["tests"].append({
                    "type": "HTTPS (CCXT)",
                    "proxy": https_proxy,
                    "success": False,
                    "error": str(e),
                    "time": f"{time.time() - start_time:.2f}s"
                })
        
        # 测试binance API
        start_time = time.time()
        try:
            import ccxt
            # 创建binance交易所实例，直接传入ccxt_config
            binance_config = {
                'enableRateLimit': True,
                'timeout': 15000,  # 15秒超时
            }
            
            # 添加代理配置
            if ccxt_config:
                # 直接使用标准CCXT配置
                binance_config.update(ccxt_config)
            elif proxy_urls:
                # 如果有旧格式的代理，转换为CCXT格式
                if 'http' in proxy_urls:
                    binance_config['httpProxy'] = proxy_urls['http']
                if 'https' in proxy_urls:
                    binance_config['httpsProxy'] = proxy_urls['https']
                    binance_config['wsProxy'] = proxy_urls['https']
            
            logger.info(f"Testing Binance API with config: {binance_config}")
            binance = ccxt.binance(binance_config)
            
            # 获取交易所状态
            status = binance.fetch_status()
            results["tests"].append({
                "type": "Binance API",
                "success": True,
                "time": f"{time.time() - start_time:.2f}s",
                "status": status['status']
            })
        except Exception as e:
            results["tests"].append({
                "type": "Binance API",
                "success": False,
                "error": str(e),
                "time": f"{time.time() - start_time:.2f}s"
            })
            
        # 所有测试都成功？
        all_success = all(test['success'] for test in results['tests'])
        
        return jsonify({
            "success": True,
            "results": results,
            "all_tests_passed": all_success
        })
    except Exception as e:
        logger.error(f"Error testing proxy: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})

def create_templates_directory():
    """Create templates directory if it doesn't exist"""
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    # Create index.html template with dark theme
    index_html = """
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t('title') }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="bg-dark text-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-black mb-4">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="bi bi-graph-up-arrow text-success me-2"></i>
                ATRLevelSignal
            </a>
            <span class="badge bg-primary ms-2">{{ t('title') }}</span>
            
            <!-- Navigation links -->
            <div class="collapse navbar-collapse ms-3" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link active" href="/">
                            <i class="bi bi-layers me-1"></i>{{ t('manage_levels') }}
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/signal_history">
                            <i class="bi bi-clock-history me-1"></i>{{ t('signal_history') }}
                        </a>
                    </li>
                </ul>
            </div>
            
            <!-- Language switcher -->
            <div class="ms-auto">
                <div class="dropdown">
                    <button class="btn btn-sm btn-outline-light dropdown-toggle" type="button" id="languageDropdown" data-bs-toggle="dropdown" aria-expanded="false">
                        {% if lang == 'en' %}
                        <i class="bi bi-globe me-1"></i> English
                        {% else %}
                        <i class="bi bi-globe me-1"></i> 中文
                        {% endif %}
                    </button>
                    <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end" aria-labelledby="languageDropdown">
                        <li><a class="dropdown-item {% if lang == 'en' %}active{% endif %}" href="/set_language/en">English</a></li>
                        <li><a class="dropdown-item {% if lang == 'zh' %}active{% endif %}" href="/set_language/zh">中文</a></li>
                    </ul>
                </div>
            </div>
            
            <!-- Mobile toggler -->
            <button class="navbar-toggler ms-2" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
        </div>
    </nav>

    <div class="container">
        <div class="row">
            <!-- Form section -->
            <div class="col-lg-5">
                <div class="card bg-dark border-primary mb-4">
                    <div class="card-header bg-primary bg-gradient text-white">
                        <h5 class="mb-0">
                            <i class="bi bi-plus-circle me-2"></i>{{ t('add_new_level') }}
                        </h5>
                    </div>
                    <div class="card-body">
                        <form id="addLevelForm">
                            <div class="mb-3">
                                <label for="pairSearch" class="form-label">
                                    <i class="bi bi-currency-exchange me-1"></i>{{ t('pair') }}
                                </label>
                                <div class="input-group mb-2">
                                    <span class="input-group-text bg-dark text-light border-secondary">
                                        <i class="bi bi-search"></i>
                                    </span>
                                    <input type="text" class="form-control bg-dark text-light border-secondary" 
                                           id="pairSearch" placeholder="{{ t('search_pairs') }}" autocomplete="off">
                                </div>
                                <select class="form-select bg-dark text-light border-secondary" 
                                        id="pair" required size="8" style="overflow-y: auto;">
                                    <option value="">{{ t('select_pair') }}</option>
                                    {% for pair in pairs %}
                                    <option value="{{ pair }}">{{ pair }}</option>
                                    {% endfor %}
                                </select>
                                <div class="d-flex justify-content-between align-items-center mt-1">
                                    <div class="form-text text-muted small" id="pairCount">
                                        <i class="bi bi-info-circle me-1"></i>{{ t('total_pairs', pairs|length) }}
                                    </div>
                                    <div id="loadingPairs" class="text-muted small" {% if not loading_all_pairs %}style="display:none"{% endif %}>
                                        <div class="spinner-border spinner-border-sm text-primary me-1" role="status">
                                            <span class="visually-hidden">Loading...</span>
                                        </div>
                                        <span>{{ t('loading_pairs') }}</span>
                                    </div>
                                </div>
                                <div id="pairsAlert" class="mt-2 small" style="display:none;">
                                    <!-- Alert messages about pair loading will be shown here -->
                                </div>
                                <div class="d-flex justify-content-between mt-2">
                                    <button type="button" id="refreshPairsBtn" class="btn btn-sm btn-outline-primary">
                                        <i class="bi bi-arrow-clockwise me-1"></i>{{ t('refresh_pairs') }}
                                    </button>
                                    <button type="button" id="refreshBinanceUsdtSpotBtn" class="btn btn-sm btn-outline-info">
                                        <i class="bi bi-currency-exchange me-1"></i>{{ t('refresh_binance_usdt_spot') }}
                                    </button>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="level" class="form-label">
                                    <i class="bi bi-rulers me-1"></i>{{ t('price_level') }}
                                </label>
                                <input type="number" class="form-control bg-dark text-light border-secondary" 
                                       id="level" step="any" required>
                            </div>
                            <div class="mb-3">
                                <label for="direction" class="form-label">
                                    <i class="bi bi-arrow-left-right me-1"></i>{{ t('direction') }}
                                </label>
                                <select class="form-select bg-dark text-light border-secondary" id="direction" required>
                                    {% for direction in directions %}
                                    <option value="{{ direction }}">
                                        {% if direction == 'up' %}
                                        <i class="bi bi-arrow-up"></i> {{ t('up') }}
                                        {% elif direction == 'down' %}
                                        <i class="bi bi-arrow-down"></i> {{ t('down') }}
                                        {% elif direction == 'both' %}
                                        <i class="bi bi-arrow-down-up"></i> {{ t('both') }}
                                        {% elif direction == 'wick_up' %}
                                        <i class="bi bi-arrow-bar-up"></i> {{ t('wick_up') }}
                                        {% elif direction == 'wick_down' %}
                                        <i class="bi bi-arrow-bar-down"></i> {{ t('wick_down') }}
                                        {% elif direction == 'wick_both' %}
                                        <i class="bi bi-arrows-expand"></i> {{ t('wick_both') }}
                                        {% endif %}
                                    </option>
                                    {% endfor %}
                                </select>
                            </div>

                            <button type="submit" class="btn btn-success w-100">
                                <i class="bi bi-plus-lg me-2"></i>{{ t('add') }}
                            </button>
                        </form>
                    </div>
                </div>
                
                <!-- Test proxy connection card -->
                <div class="card bg-dark border-warning mb-4">
                    <div class="card-header bg-warning bg-gradient text-dark">
                        <h5 class="mb-0">
                            <i class="bi bi-wifi me-2"></i>{{ t('test_proxy') }}
                        </h5>
                    </div>
                    <div class="card-body">
                        <p class="text-muted small mb-3">{{ t('check_config_proxy') }}</p>
                        <button type="button" id="testProxyBtn" class="btn btn-warning w-100">
                            <i class="bi bi-wifi me-1"></i>{{ t('test_proxy') }}
                        </button>
                        <div id="proxyTestResult" class="mt-3 small" style="display:none;">
                            <!-- Proxy test results will be shown here -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Table section -->
            <div class="col-lg-7">
                <!-- Statistics card -->
                <div class="card bg-dark border-info mb-4">
                    <div class="card-header bg-info bg-gradient text-dark">
                        <h5 class="mb-0">
                            <i class="bi bi-info-circle me-2"></i>{{ t('statistics') }}
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="row text-center">
                            <div class="col-4">
                                <div class="stat-card">
                                    <div class="stat-value text-primary" id="totalLevels">{{ levels|length }}</div>
                                    <div class="stat-label">{{ t('total_levels') }}</div>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="stat-card">
                                    <div class="stat-value text-success" id="upLevels">
                                        {{ levels|selectattr('direction', 'equalto', 'up')|list|length }}
                                    </div>
                                    <div class="stat-label">{{ t('up_levels') }}</div>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="stat-card">
                                    <div class="stat-value text-danger" id="downLevels">
                                        {{ levels|selectattr('direction', 'equalto', 'down')|list|length }}
                                    </div>
                                    <div class="stat-label">{{ t('down_levels') }}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card bg-dark border-secondary mb-4">
                    <div class="card-header bg-secondary bg-gradient">
                        <div class="d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">
                                <i class="bi bi-table me-2"></i>{{ t('existing_levels') }}
                            </h5>
                            <div class="input-group" style="width: 250px;">
                                <span class="input-group-text bg-dark text-light border-secondary">
                                    <i class="bi bi-filter"></i>
                                </span>
                                <input type="text" class="form-control bg-dark text-light border-secondary" 
                                       id="filterPairInput" placeholder="{{ t('filter_pairs') }}" autocomplete="off">
                            </div>
                        </div>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-dark table-hover table-bordered mb-0">
                                <thead class="table-dark">
                                    <tr>
                                        <th>{{ t('id') }}</th>
                                        <th>{{ t('trading_pair') }}</th>
                                        <th>{{ t('price_level') }}</th>
                                        <th>{{ t('direction') }}</th>
                                        <th class="text-center">{{ t('actions') }}</th>
                                    </tr>
                                </thead>
                                <tbody id="levelsTableBody">
                                    {% for level in levels %}
                                    <tr data-pair="{{ level.pair }}">
                                        <td>{{ level.id }}</td>
                                        <td>
                                            <span class="badge bg-dark text-light border border-light pair-badge" data-pair="{{ level.pair }}">
                                                {{ level.pair }}
                                            </span>
                                        </td>
                                        <td class="text-info fw-bold">{{ level.level }}</td>
                                        <td>
                                            {% if level.direction == 'up' %}
                                            <span class="badge bg-success">
                                                <i class="bi bi-arrow-up me-1"></i>
                                                {% if lang == 'en' %}Up{% else %}上穿{% endif %}
                                            </span>
                                            {% elif level.direction == 'down' %}
                                            <span class="badge bg-danger">
                                                <i class="bi bi-arrow-down me-1"></i>
                                                {% if lang == 'en' %}Down{% else %}下穿{% endif %}
                                            </span>
                                            {% elif level.direction == 'both' %}
                                            <span class="badge bg-primary">
                                                <i class="bi bi-arrow-down-up me-1"></i>
                                                {% if lang == 'en' %}Both{% else %}双向{% endif %}
                                            </span>
                                            {% elif level.direction == 'wick_up' %}
                                            <span class="badge bg-warning">
                                                <i class="bi bi-arrow-bar-up me-1"></i>
                                                {% if lang == 'en' %}Wick Up{% else %}上影线流动性清扫{% endif %}
                                            </span>
                                            {% elif level.direction == 'wick_down' %}
                                            <span class="badge bg-info">
                                                <i class="bi bi-arrow-bar-down me-1"></i>
                                                {% if lang == 'en' %}Wick Down{% else %}下影线流动性清扫{% endif %}
                                            </span>
                                            {% elif level.direction == 'wick_both' %}
                                            <span class="badge bg-secondary">
                                                <i class="bi bi-arrows-expand me-1"></i>
                                                {% if lang == 'en' %}Bidirectional Liquidity Sweep{% else %}双向流动性清扫{% endif %}
                                            </span>
                                            {% endif %}
                                        </td>

                                        <td class="text-center">
                                            <div class="btn-group" role="group">
                                                <button class="btn btn-sm btn-outline-primary edit-btn me-2" data-id="{{ level.id }}" 
                                                        data-pair="{{ level.pair }}" data-level="{{ level.level }}" 
                                                        data-direction="{{ level.direction }}" data-confirm-close="{{ level.confirm_close|int }}">
                                                    <i class="bi bi-pencil"></i>
                                                </button>
                                                <button class="btn btn-sm btn-outline-danger delete-btn" data-id="{{ level.id }}">
                                                    <i class="bi bi-trash"></i>
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Check inactive pairs card -->
                <div class="card bg-dark border-warning">
                    <div class="card-header bg-warning bg-gradient text-dark">
                        <h5 class="mb-0">
                            <i class="bi bi-exclamation-triangle me-2"></i>{{ t('check_inactive_pairs') }}
                        </h5>
                    </div>
                    <div class="card-body">
                        <button id="checkInactivePairsBtn" class="btn btn-warning w-100 mb-3">
                            <i class="bi bi-check-circle me-2"></i>{{ t('check_inactive_pairs') }}
                        </button>
                        <div id="inactivePairsResult" class="mt-2 small" style="display:none;">
                            <!-- Results will be displayed here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <footer class="mt-4 text-center text-muted">
            <p>{{ t('footer') }} &copy; {{ now.year }}</p>
        </footer>
    </div>

    <!-- Notification toast -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <div id="notificationToast" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <strong class="me-auto" id="toastTitle">{{ t('notification') }}</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body" id="toastMessage"></div>
        </div>
    </div>
    
    <!-- Edit Level Modal -->
    <div class="modal fade" id="editLevelModal" tabindex="-1" aria-labelledby="editLevelModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content bg-dark text-light">
                <div class="modal-header bg-primary">
                    <h5 class="modal-title" id="editLevelModalLabel">{{ t('edit_level') }}</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <form id="editLevelForm">
                        <input type="hidden" id="editLevelId">
                        <div class="mb-3">
                            <label for="editPair" class="form-label">{{ t('trading_pair') }}</label>
                            <input type="text" class="form-control bg-dark text-light border-secondary" id="editPair" readonly>
                        </div>
                        <div class="mb-3">
                            <label for="editLevel" class="form-label">{{ t('price_level') }}</label>
                            <div class="input-group">
                                <input type="number" class="form-control bg-dark text-light border-secondary" id="editLevel" step="any" required>
                                <button type="button" class="btn btn-outline-primary" id="fetchCurrentPriceBtn">
                                    <i class="bi bi-arrow-repeat me-1"></i>{{ t('get_current_price') }}
                                </button>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="editDirection" class="form-label">{{ t('direction') }}</label>
                            <select class="form-select bg-dark text-light border-secondary" id="editDirection" required>
                                {% for direction in directions %}
                                <option value="{{ direction }}">
                                    {% if direction == 'up' %}
                                    <i class="bi bi-arrow-up"></i> {{ t('up') }}
                                    {% elif direction == 'down' %}
                                    <i class="bi bi-arrow-down"></i> {{ t('down') }}
                                    {% elif direction == 'both' %}
                                    <i class="bi bi-arrow-down-up"></i> {{ t('both') }}
                                    {% elif direction == 'wick_up' %}
                                    <i class="bi bi-arrow-bar-up"></i> {{ t('wick_up') }}
                                    {% elif direction == 'wick_down' %}
                                    <i class="bi bi-arrow-bar-down"></i> {{ t('wick_down') }}
                                    {% elif direction == 'wick_both' %}
                                    <i class="bi bi-arrows-expand"></i> {{ t('wick_both') }}
                                    {% endif %}
                                </option>
                                {% endfor %}
                            </select>
                        </div>

                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{{ t('cancel') }}</button>
                    <button type="button" class="btn btn-primary" id="saveEditBtn">{{ t('save') }}</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Language-specific messages
            const translations = {
                'en': {
                    'success': 'Success',
                    'error': 'Error',
                    'added_level': 'Added price level {0} for {1}',
                    'add_failed': 'Add failed: {0}',
                    'deleted_level': 'Deleted price level',
                    'delete_failed': 'Delete failed: {0}',
                    'confirm_delete': 'Are you sure you want to delete this level?',
                    'loading_price': 'Loading price...',
                    'price_fetch_failed': 'Failed to fetch price',
                    'current_price_loaded': 'Current price loaded',
                    'is required': 'is required',
                    'updated_level': 'Updated price level for {0}',
                    'update_failed': 'Update failed: {0}'
                },
                'zh': {
                    'success': '成功',
                    'error': '错误',
                    'added_level': '已添加 {1} 的价格点位 {0}',
                    'add_failed': '添加失败: {0}',
                    'deleted_level': '已删除价格点位',
                    'delete_failed': '删除失败: {0}',
                    'confirm_delete': '确定要删除此监控点位吗?',
                    'loading_price': '正在获取价格...',
                    'price_fetch_failed': '获取价格失败',
                    'current_price_loaded': '当前价格已加载',
                    'is required': '是必填项',
                    'updated_level': '已更新 {0} 的价格点位',
                    'update_failed': '更新失败: {0}'
                }
            };
            
            // Get current language
            const currentLang = '{{ lang }}';
            
            // Translation function
            function t(key, ...args) {
                let text = translations[currentLang][key] || key;
                for (let i = 0; i < args.length; i++) {
                    text = text.replace(`{${i}}`, args[i]);
                }
                return text;
            }
            
            // Toast notification function
            function showNotification(title, message, type = 'success') {
                const toast = document.getElementById('notificationToast');
                const toastTitle = document.getElementById('toastTitle');
                const toastMessage = document.getElementById('toastMessage');
                
                toastTitle.textContent = title;
                toastMessage.textContent = message;
                
                // Set toast class based on type
                toast.className = 'toast';
                if (type === 'success') {
                    toast.classList.add('bg-success', 'text-white');
                } else if (type === 'error') {
                    toast.classList.add('bg-danger', 'text-white');
                } else if (type === 'warning') {
                    toast.classList.add('bg-warning', 'text-dark');
                } else {
                    toast.classList.add('bg-dark', 'text-light');
                }
                
                const bsToast = new bootstrap.Toast(toast);
                bsToast.show();
            }
        
            // Add level form submission
            document.getElementById('addLevelForm').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const pair = document.getElementById('pair').value;
                const level = document.getElementById('level').value;
                const direction = document.getElementById('direction').value;
                
                fetch('/api/levels', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        pair: pair,
                        level: parseFloat(level),
                        direction: direction,
                        confirm_close: false
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showNotification(t('success'), t('added_level', level, pair), 'success');
                        setTimeout(() => window.location.reload(), 1000);
                    } else {
                        showNotification(t('error'), t('add_failed', data.error), 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showNotification(t('error'), t('add_failed', error), 'error');
                });
            });
            
            // 当选择交易对时，自动获取当前价格
            document.getElementById('pair').addEventListener('change', function() {
                const pair = this.value;
                const levelInput = document.getElementById('level');
                
                // 如果没有选择交易对，直接返回
                if (!pair) return;
                
                // 清空输入框并显示加载状态
                levelInput.value = '';
                levelInput.setAttribute('placeholder', t('loading_price'));
                
                // 创建加载指示器
                let loadingIndicator = document.getElementById('priceLoadingIndicator');
                if (!loadingIndicator) {
                    loadingIndicator = document.createElement('div');
                    loadingIndicator.id = 'priceLoadingIndicator';
                    loadingIndicator.className = 'spinner-border spinner-border-sm text-primary ms-2';
                    loadingIndicator.setAttribute('role', 'status');
                    loadingIndicator.innerHTML = '<span class="visually-hidden">Loading...</span>';
                    document.querySelector('label[for="level"]').appendChild(loadingIndicator);
                } else {
                    loadingIndicator.style.display = '';
                }
                
                // 获取价格
                fetch(`/api/current_price/${encodeURIComponent(pair)}`)
                    .then(response => response.json())
                    .then(data => {
                        // 隐藏加载指示器
                        if (loadingIndicator) {
                            loadingIndicator.style.display = 'none';
                        }
                        
                        if (data.success && data.price) {
                            // 设置价格到输入框
                            levelInput.value = data.price;
                            levelInput.setAttribute('placeholder', '');
                            showNotification(t('success'), t('current_price_loaded'), 'success');
                        } else {
                            // 显示错误
                            console.error('获取价格失败:', data.error);
                            levelInput.setAttribute('placeholder', t('price_fetch_failed'));
                            showNotification(t('error'), t('price_fetch_failed') + ': ' + (data.error || '未知错误'), 'error');
                        }
                    })
                    .catch(error => {
                        // 隐藏加载指示器
                        if (loadingIndicator) {
                            loadingIndicator.style.display = 'none';
                        }
                        
                        console.error('获取价格出错:', error);
                        levelInput.setAttribute('placeholder', t('price_fetch_failed'));
                        showNotification(t('error'), t('price_fetch_failed') + ': ' + error, 'error');
                    });
            });
            
            // Edit level buttons
            document.querySelectorAll('.edit-btn').forEach(button => {
                button.addEventListener('click', function() {
                    const levelId = this.getAttribute('data-id');
                    const pair = this.getAttribute('data-pair');
                    const level = this.getAttribute('data-level');
                    const direction = this.getAttribute('data-direction');
                    
                    // Set values in modal form
                    document.getElementById('editLevelId').value = levelId;
                    document.getElementById('editPair').value = pair;
                    document.getElementById('editLevel').value = level;
                    document.getElementById('editDirection').value = direction;
                    
                    // Show modal
                    const editModal = new bootstrap.Modal(document.getElementById('editLevelModal'));
                    editModal.show();
                });
            });
            
            // Fetch current price button in edit modal
            document.getElementById('fetchCurrentPriceBtn').addEventListener('click', function() {
                const pair = document.getElementById('editPair').value;
                const levelInput = document.getElementById('editLevel');
                
                // If no pair selected, show error and return
                if (!pair) {
                    showNotification(t('error'), t('trading_pair') + ' ' + t('is required'), 'error');
                    return;
                }
                
                // Clear input and show loading state
                levelInput.setAttribute('placeholder', t('loading_price'));
                
                // Create loading indicator
                let loadingIndicator = document.createElement('span');
                loadingIndicator.className = 'spinner-border spinner-border-sm text-primary ms-2';
                loadingIndicator.setAttribute('role', 'status');
                this.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i>${t('loading_price')}`;
                this.disabled = true;
                
                // Fetch current price
                fetch(`/api/current_price/${encodeURIComponent(pair)}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.price) {
                            // Set price to input field
                            levelInput.value = data.price;
                            levelInput.setAttribute('placeholder', '');
                            showNotification(t('success'), t('current_price_loaded'), 'success');
                        } else {
                            // Show error
                            console.error('Failed to fetch price:', data.error);
                            levelInput.setAttribute('placeholder', t('price_fetch_failed'));
                            showNotification(t('error'), t('price_fetch_failed') + ': ' + (data.error || ''), 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching price:', error);
                        levelInput.setAttribute('placeholder', t('price_fetch_failed'));
                        showNotification(t('error'), t('price_fetch_failed') + ': ' + error, 'error');
                    })
                    .finally(() => {
                        // Restore button text and enable it
                        this.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i>${t('get_current_price')}`;
                        this.disabled = false;
                    });
            });
            
            // Save edit button
            document.getElementById('saveEditBtn').addEventListener('click', function() {
                const levelId = document.getElementById('editLevelId').value;
                const pair = document.getElementById('editPair').value;
                const level = document.getElementById('editLevel').value;
                const direction = document.getElementById('editDirection').value;
                
                // Validate input
                if (!level) {
                    showNotification(t('error'), t('price_level') + ' ' + t('is required'), 'error');
                    return;
                }
                
                // Send update request
                fetch(`/api/levels/${levelId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        level: parseFloat(level),
                        direction: direction,
                        confirm_close: false
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showNotification(t('success'), t('updated_level', pair), 'success');
                        
                        // Close modal
                        const editModal = bootstrap.Modal.getInstance(document.getElementById('editLevelModal'));
                        editModal.hide();
                        
                        // Reload page to show updated data
                        setTimeout(() => window.location.reload(), 1000);
                    } else {
                        showNotification(t('error'), t('update_failed', data.error), 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showNotification(t('error'), t('update_failed', error), 'error');
                });
            });
            
            // Delete level buttons
            document.querySelectorAll('.delete-btn').forEach(button => {
                button.addEventListener('click', function() {
                    const levelId = this.getAttribute('data-id');
                    if (confirm(t('confirm_delete'))) {
                        fetch(`/api/levels/${levelId}`, {
                            method: 'DELETE',
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                showNotification(t('success'), t('deleted_level'), 'success');
                                setTimeout(() => window.location.reload(), 1000);
                            } else {
                                showNotification(t('error'), t('delete_failed', data.error), 'error');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            showNotification(t('error'), t('delete_failed', error), 'error');
                        });
                    }
                });
            });
            
            // Filter table by pair
            document.getElementById('filterPairInput').addEventListener('input', function() {
                const filterText = this.value.toLowerCase();
                const rows = document.querySelectorAll('#levelsTableBody tr');
                
                rows.forEach(row => {
                    const pair = row.getAttribute('data-pair').toLowerCase();
                    if (pair.includes(filterText)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            });
            
            // Filter dropdown options by search text
            document.getElementById('pairSearch').addEventListener('input', function() {
                const searchText = this.value.toLowerCase();
                const pairSelect = document.getElementById('pair');
                const options = pairSelect.querySelectorAll('option');
                
                let visibleCount = 0;
                
                options.forEach(option => {
                    // Skip the first placeholder option
                    if (option.value === '') return;
                    
                    const pairText = option.textContent.toLowerCase();
                    if (pairText.includes(searchText)) {
                        option.style.display = '';
                        visibleCount++;
                    } else {
                        option.style.display = 'none';
                    }
                });
                
                // Automatically select the only visible option if there's exactly one match
                if (visibleCount === 1 && searchText.length > 2) {
                    options.forEach(option => {
                        if (option.style.display !== 'none' && option.value !== '') {
                            pairSelect.value = option.value;
                            // 触发change事件，自动获取价格
                            const event = new Event('change');
                            pairSelect.dispatchEvent(event);
                        }
                    });
                }
            });
            
            // Load all pairs from exchange
            function loadAllPairs(usdt_only = false, spot_only = false) {
                const loadingElement = document.getElementById('loadingPairs');
                const pairCountElement = document.getElementById('pairCount');
                const pairSelect = document.getElementById('pair');
                const pairSearch = document.getElementById('pairSearch');
                const pairsAlert = document.getElementById('pairsAlert');
                
                // Show loading indicator
                loadingElement.style.display = '';
                
                // Hide any previous alerts
                pairsAlert.style.display = 'none';
                pairsAlert.innerHTML = '';
                
                // Build query parameters
                const params = new URLSearchParams();
                if (usdt_only) params.append('usdt_only', 'true');
                if (spot_only) params.append('spot_only', 'true');
                
                // Clear search input
                pairSearch.value = '';
                
                // Disable form elements during loading
                pairSelect.disabled = true;
                pairSearch.disabled = true;
                
                fetch(`/api/all_pairs?${params.toString()}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const pairs = data.pairs;
                            const currentValue = pairSelect.value;
                            
                            console.log(`Received ${pairs.length} pairs from server`);
                            
                            // Clear existing options (except the first one)
                            while (pairSelect.options.length > 1) {
                                pairSelect.remove(1);
                            }
                            
                            // Check for proxy error indicator
                            const proxyErrorIndex = pairs.indexOf("ERROR_PROXY_CONNECTION");
                            if (proxyErrorIndex !== -1) {
                                // Remove the error indicator from the array
                                pairs.splice(proxyErrorIndex, 1);
                                
                                // Show proxy error message
                                pairsAlert.innerHTML = `
                                    <div class="alert alert-danger">
                                        <i class="bi bi-wifi-off me-2"></i>
                                        ${t('proxy_error')}
                                        <hr>
                                        <small class="d-block mt-2">
                                            <i class="bi bi-info-circle me-1"></i>
                                            ${t('check_config_proxy')}
                                        </small>
                                    </div>
                                `;
                                pairsAlert.style.display = 'block';
                                
                                // Show error notification
                                showNotification(t('error'), t('proxy_error'), 'error');
                            }
                            
                            if (pairs.length === 0) {
                                // No pairs returned
                                pairsAlert.innerHTML = `
                                    <div class="alert alert-warning">
                                        <i class="bi bi-exclamation-triangle me-2"></i>
                                        ${t('no_pairs_found')}
                                    </div>
                                `;
                                pairsAlert.style.display = 'block';
                                
                                // Update pair count for empty results
                                pairCountElement.innerHTML = `<i class="bi bi-info-circle me-1"></i>${t('total_pairs', 0)}`;
                                
                                // Show warning notification
                                showNotification(t('warning'), t('no_pairs_found'), 'warning');
                            } else {
                                // Add all pairs
                                pairs.forEach(pair => {
                                    const option = document.createElement('option');
                                    option.value = pair;
                                    option.textContent = pair;
                                    pairSelect.appendChild(option);
                                });
                                
                                // Restore selected value if it exists
                                if (currentValue && pairs.includes(currentValue)) {
                                    pairSelect.value = currentValue;
                                } else {
                                    pairSelect.selectedIndex = 0; // Select the first option
                                }
                                
                                // Update pair count
                                pairCountElement.innerHTML = `<i class="bi bi-info-circle me-1"></i>${t('total_pairs', pairs.length)}`;
                                
                                // Show success message
                                showNotification(t('success'), t('pairs_loaded', pairs.length), 'success');
                            }
                        } else {
                            console.error('Error loading pairs:', data.error);
                            
                            // Show error in alert
                            pairsAlert.innerHTML = `
                                <div class="alert alert-danger">
                                    <i class="bi bi-x-circle me-2"></i>
                                    ${t('error')}: ${data.error}
                                </div>
                            `;
                            pairsAlert.style.display = 'block';
                            
                            showNotification(t('error'), data.error, 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        
                        // Show error in alert
                        pairsAlert.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="bi bi-x-circle me-2"></i>
                                ${t('error')}: ${error.toString()}
                            </div>
                        `;
                        pairsAlert.style.display = 'block';
                        
                        showNotification(t('error'), error.toString(), 'error');
                    })
                    .finally(() => {
                        // Hide loading indicator
                        loadingElement.style.display = 'none';
                        
                        // Re-enable form elements
                        pairSelect.disabled = false;
                        pairSearch.disabled = false;
                    });
            }
            
            // Check inactive pairs
            function checkInactivePairs() {
                const resultElement = document.getElementById('inactivePairsResult');
                
                // Show loading message
                resultElement.innerHTML = `<div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm text-warning me-2" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <span>${t('checking_pairs')}</span>
                </div>`;
                resultElement.style.display = '';
                
                fetch('/api/check_inactive_pairs')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const pairsStatus = data.pairs_status;
                            const inactivePairs = Object.entries(pairsStatus).filter(([_, active]) => !active).map(([pair]) => pair);
                            
                            // Update pair badges in the table
                            document.querySelectorAll('.pair-badge').forEach(badge => {
                                const pair = badge.getAttribute('data-pair');
                                if (pair in pairsStatus) {
                                    if (!pairsStatus[pair]) {
                                        // Inactive pair
                                        badge.classList.remove('bg-dark');
                                        badge.classList.add('bg-danger');
                                        badge.setAttribute('title', t('inactive_pair'));
                                        
                                        // Add warning icon
                                        if (!badge.querySelector('.bi-exclamation-triangle-fill')) {
                                            badge.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i>${badge.innerHTML}`;
                                        }
                                    } else {
                                        // Active pair
                                        badge.classList.remove('bg-danger');
                                        badge.classList.add('bg-dark');
                                        badge.removeAttribute('title');
                                    }
                                }
                            });
                            
                            if (inactivePairs.length > 0) {
                                // Display inactive pairs
                                let html = `<div class="alert alert-warning">
                                    <i class="bi bi-exclamation-triangle me-2"></i>
                                    <strong>${t('inactive_pairs_found', inactivePairs.length)}</strong>
                                </div>
                                <ul class="list-group list-group-flush bg-dark">`;
                                
                                Object.entries(pairsStatus).forEach(([pair, active]) => {
                                    const badgeClass = active ? 'bg-success' : 'bg-danger';
                                    const status = active ? t('active_pair') : t('inactive_pair');
                                    html += `<li class="list-group-item bg-dark text-light d-flex justify-content-between align-items-center">
                                        ${pair}
                                        <span class="badge ${badgeClass}">${status}</span>
                                    </li>`;
                                });
                                
                                html += '</ul>';
                                resultElement.innerHTML = html;
                            } else {
                                // All pairs are active
                                resultElement.innerHTML = `<div class="alert alert-success">
                                    <i class="bi bi-check-circle me-2"></i>
                                    <strong>${t('all_pairs_active')}</strong>
                                </div>`;
                            }
                        } else {
                            console.error('Error checking inactive pairs:', data.error);
                            resultElement.innerHTML = `<div class="alert alert-danger">
                                <i class="bi bi-x-circle me-2"></i>
                                <strong>${t('error')}: ${data.error}</strong>
                            </div>`;
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        resultElement.innerHTML = `<div class="alert alert-danger">
                            <i class="bi bi-x-circle me-2"></i>
                            <strong>${t('error')}: ${error}</strong>
                        </div>`;
                    });
            }
            
            // Event listeners for buttons
            document.getElementById('refreshPairsBtn').addEventListener('click', function() {
                loadAllPairs(false, false);
            });
            
            document.getElementById('refreshBinanceUsdtSpotBtn').addEventListener('click', function() {
                loadAllPairs(true, true);
            });
            
            document.getElementById('checkInactivePairsBtn').addEventListener('click', function() {
                checkInactivePairs();
            });
            
            // 测试代理连接
            document.getElementById('testProxyBtn').addEventListener('click', function() {
                testProxyConnection();
            });
            
            // 测试代理连接功能
            function testProxyConnection() {
                // 显示测试中的提示
                const proxyTestResult = document.getElementById('proxyTestResult');
                proxyTestResult.innerHTML = `
                    <div class="alert alert-info">
                        <div class="d-flex align-items-center">
                            <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <span>${t('testing_proxy')}</span>
                        </div>
                    </div>
                `;
                proxyTestResult.style.display = 'block';
                
                // 禁用测试按钮
                document.getElementById('testProxyBtn').disabled = true;
                
                // 发送请求测试代理
                fetch('/api/test_proxy')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const results = data.results;
                            const tests = results.tests;
                            const allTestsPassed = data.all_tests_passed;
                            
                            // 构建结果HTML
                            let resultHtml = `
                                <div class="card mb-3">
                                    <div class="card-header ${allTestsPassed ? 'bg-success' : 'bg-warning'} text-white">
                                        <h5 class="mb-0">
                                            <i class="bi ${allTestsPassed ? 'bi-check-circle' : 'bi-exclamation-triangle'} me-2"></i>
                                            ${t('proxy_test_results')}
                                        </h5>
                                    </div>
                                    <div class="card-body bg-dark">
                                        <div class="alert ${allTestsPassed ? 'alert-success' : tests.some(t => t.success) ? 'alert-warning' : 'alert-danger'}">
                                            ${allTestsPassed 
                                                ? t('proxy_test_success') 
                                                : tests.some(t => t.success) 
                                                    ? t('proxy_test_partial') 
                                                    : t('proxy_test_failed')
                                            }
                                        </div>
                                        
                                        <div class="mt-3">
                                            <h6 class="text-muted">Proxy Configuration:</h6>
                                            <div class="row">
                                                <div class="col-md-6">
                                                    <h6 class="text-muted mb-2">CCXT Config:</h6>
                                                    <pre class="bg-dark text-light p-2 border">${JSON.stringify(results.ccxt_config || {}, null, 2)}</pre>
                                                </div>
                                                <div class="col-md-6">
                                                    <h6 class="text-muted mb-2">Proxy URLs:</h6>
                                                    <pre class="bg-dark text-light p-2 border">${JSON.stringify(results.proxy_urls || {}, null, 2)}</pre>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div class="mt-3">
                                            <h6 class="text-muted">Test Results:</h6>
                                            <div class="list-group bg-dark">
            `;
                            
                            // 添加每个测试的结果
                            tests.forEach(test => {
                                const statusClass = test.success ? 'bg-success' : 'bg-danger';
                                const statusIcon = test.success ? 'bi-check-circle' : 'bi-x-circle';
                                
                                resultHtml += `
                                    <div class="list-group-item bg-dark text-light border-secondary">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <div>
                                                <h6 class="mb-1">${test.type}</h6>
                                                ${test.proxy ? `<small class="text-muted d-block">Proxy: ${test.proxy}</small>` : ''}
                                                ${test.time ? `<small class="text-muted d-block">Time: ${test.time}</small>` : ''}
                                                ${test.ip ? `<small class="text-success d-block">IP: ${test.ip}</small>` : ''}
                                                ${test.error ? `<small class="text-danger d-block">Error: ${test.error}</small>` : ''}
                                            </div>
                                            <span class="badge ${statusClass}">
                                                <i class="bi ${statusIcon}"></i>
                                            </span>
                                        </div>
                                    </div>
                                `;
                            });
                            
                            resultHtml += `
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `;
                            
                            // 显示结果
                            proxyTestResult.innerHTML = resultHtml;
                            
                            // 显示通知
                            if (allTestsPassed) {
                                showNotification(t('success'), t('proxy_test_success'), 'success');
                            } else if (tests.some(t => t.success)) {
                                showNotification(t('warning'), t('proxy_test_partial'), 'warning');
                            } else {
                                showNotification(t('error'), t('proxy_test_failed'), 'error');
                            }
                        } else {
                            // 显示错误
                            proxyTestResult.innerHTML = `
                                <div class="alert alert-danger">
                                    <i class="bi bi-x-circle me-2"></i>
                                    ${t('error')}: ${data.error}
                                </div>
                            `;
                            
                            showNotification(t('error'), data.error, 'error');
                        }
                    })
                    .catch(error => {
                        // 显示错误
                        proxyTestResult.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="bi bi-x-circle me-2"></i>
                                ${t('error')}: ${error.toString()}
                            </div>
                        `;
                        
                        showNotification(t('error'), error.toString(), 'error');
                    })
                    .finally(() => {
                        // 重新启用测试按钮
                        document.getElementById('testProxyBtn').disabled = false;
                    });
            }
            
            // Load all pairs when the page loads with a slight delay to ensure UI is ready
            setTimeout(() => {
                // First load with default parameters
                loadAllPairs(false, false);
            }, 500);
        });
    </script>
</body>
</html>
    """
    
    # Create error.html template with dark theme
    error_html = """
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t('error_title') }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="bg-dark text-light">
    <div class="container mt-5">
        <div class="card bg-dark border-danger">
            <div class="card-header bg-danger bg-gradient text-white">
                <h4 class="mb-0">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>{{ t('error') }}
                </h4>
            </div>
            <div class="card-body">
                <p class="lead">{{ error }}</p>
                <hr class="border-secondary">
                <div class="d-grid gap-2">
                    <a href="/" class="btn btn-primary">
                        <i class="bi bi-house-door me-2"></i>{{ t('return_home') }}
                    </a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
    """
    
    # Write templates to files
    with open(templates_dir / 'index.html', 'w') as f:
        f.write(index_html)
    
    with open(templates_dir / 'error.html', 'w') as f:
        f.write(error_html)

def create_static_directory():
    """Create static directory if it doesn't exist"""
    static_dir = Path(__file__).parent / 'static'
    static_dir.mkdir(exist_ok=True)
    
    # Create CSS file with dark theme styles
    css_file = static_dir / 'style.css'
    with open(css_file, 'w') as f:
        f.write("""
/* Custom styles for price levels web interface - Dark Theme */
body {
    background-color: #121212;
    color: #e0e0e0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.navbar {
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
}

.navbar-brand {
    font-weight: bold;
    font-size: 1.4rem;
}

.card {
    background-color: #1e1e1e;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    margin-bottom: 20px;
    transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.4);
}

.card-header {
    border-radius: 8px 8px 0 0 !important;
    font-weight: bold;
}

.form-control, .form-select {
    background-color: #2d2d2d;
    border-color: #444;
    color: #e0e0e0;
}

.form-control:focus, .form-select:focus {
    background-color: #2d2d2d;
    border-color: #007bff;
    color: #e0e0e0;
    box-shadow: 0 0 0 0.25rem rgba(0, 123, 255, 0.25);
}

.btn {
    border-radius: 6px;
    font-weight: 500;
    padding: 0.5rem 1rem;
    transition: all 0.2s;
}

.btn-success {
    background-color: #198754;
    border-color: #198754;
}

.btn-success:hover {
    background-color: #157347;
    border-color: #146c43;
    transform: translateY(-2px);
}

.btn-outline-danger {
    color: #dc3545;
    border-color: #dc3545;
}

.btn-outline-danger:hover {
    background-color: #dc3545;
    color: white;
}

.table {
    color: #e0e0e0;
    border-color: #444;
}

.table-dark {
    background-color: #1e1e1e;
}

.table-hover tbody tr:hover {
    background-color: rgba(255, 255, 255, 0.075);
}

.badge {
    font-weight: 500;
    padding: 0.5em 0.8em;
}

.stat-card {
    padding: 10px;
    border-radius: 8px;
    background-color: #2d2d2d;
    margin-bottom: 10px;
}

.stat-value {
    font-size: 1.8rem;
    font-weight: bold;
}

.stat-label {
    font-size: 0.9rem;
    color: #aaa;
}

footer {
    border-top: 1px solid #444;
    padding-top: 20px;
    margin-top: 30px;
}

/* Toast customization */
.toast {
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

/* Pair select customization */
select[size] option {
    padding: 8px 12px;
    border-bottom: 1px solid #333;
}

select[size] option:hover {
    background-color: #2a2a2a;
}

select[size] option:first-child {
    font-weight: bold;
    color: #aaa;
    background-color: #222;
    border-bottom: 2px solid #444;
}

/* Hide options with display:none from the select dropdown */
select option[style*="display: none"] {
    display: none !important;
}
        """)

def main() -> None:
    """Main function"""
    parser = argparse.ArgumentParser(description='Web service to manage price levels for ATRLevelSignal strategy')
    
    # Add config file argument
    parser.add_argument('--config', '-c', required=True, 
                       help='Path to Freqtrade config file. For proxy support, add "proxy" section in config file.')
    
    # Add language argument
    parser.add_argument('--lang', '-l', choices=['en', 'zh'], default='zh', 
                        help='Default language (en=English, zh=Chinese)')
    
    # Add help text about proxy configuration
    parser.epilog = """
Proxy Configuration:
  To use a proxy for exchange API requests, add a "proxy" section to your config file:
  
  "proxy": {
    "http": "http://your-proxy-server:port",
    "https": "https://your-proxy-server:port"
  }
  
  You can also set a custom timeout for exchange API requests:
  
  "exchange_request_timeout": 30  # timeout in seconds
  
  The proxy settings and timeout will be used when fetching trading pairs from the exchange.
"""
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create templates and static directories
    create_templates_directory()
    create_static_directory()
    
    # Initialize database connection
    if not setup_db(args.config):
        sys.exit(1)
    
    # Set default language
    app.config['DEFAULT_LANGUAGE'] = args.lang
    
    # Get web config
    web_config = CONFIG.get('web_config', {})
    host = web_config.get('host', '127.0.0.1')
    port = web_config.get('port', 8501)
    
    # Run Flask app
    logger.info(f"Starting web server at http://{host}:{port}")
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    main() 