import logging
import enum
import os
from typing import ClassVar, Optional, List, Dict, Any
from datetime import datetime
import traceback
import pandas as pd

from sqlalchemy import String, Float, Integer, DateTime, select, delete, create_engine
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError

from freqtrade.strategy import IStrategy
from freqtrade.persistence.base import ModelBase, SessionType
from freqtrade.persistence.models import init_db
from pandas import DataFrame, Series
import pandas_ta as ta

logger = logging.getLogger(__name__)

class LevelDirection(str, enum.Enum):
    """Direction for level crossing"""
    UP = "up"  # 向上突破（K线实体部分向上穿过价格水平）
    DOWN = "down"  # 向下突破（K线实体部分向下穿过价格水平）
    BOTH = "both"  # 双向突破（K线实体部分向上或向下穿过价格水平）
    WICK_UP = "wick_up"  # 向上流动性清扫（K线上影线部分穿过价格水平）
    WICK_DOWN = "wick_down"  # 向下流动性清扫（K线下影线部分穿过价格水平）
    WICK_BOTH = "wick_both"  # 双向流动性清扫（K线上下影线部分穿过价格水平）

class PriceLevel(ModelBase):
    """
    Price level database model for level crossing detection
    """
    __tablename__ = "price_levels"
    session: ClassVar[SessionType]

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair: Mapped[str] = mapped_column(String(25), nullable=False, index=True)
    level: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)  # 1=active, 0=inactive
    confirm_close: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)  # 1=require close confirmation, 0=trigger on cross

    @classmethod
    def get_levels(cls, pair: Optional[str] = None) -> List["PriceLevel"]:
        """
        Get all active price levels for a specific pair or all pairs
        """
        try:
            # Ensure we have a valid session
            if not hasattr(cls, 'session') or cls.session is None:
                logger.warning("Database session not initialized. Attempting to reconnect...")
                ATRLevelSignal.init_db_session()
                
            filters = [PriceLevel.active == 1]
            if pair:
                filters.append(PriceLevel.pair == pair)
            
            return PriceLevel.session.scalars(select(PriceLevel).filter(*filters)).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_levels: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in get_levels: {e}")
            return []
    
    @classmethod
    def add_level(cls, pair: str, level: float, direction: str = "both", confirm_close: bool = False) -> "PriceLevel":
        """
        Add a new price level to monitor
        
        Args:
            pair: Trading pair symbol
            level: Price level value
            direction: Direction to monitor (up/down/both)
            confirm_close: If True, require candle to close beyond the level
        """
        try:
            # Ensure we have a valid session
            if not hasattr(cls, 'session') or cls.session is None:
                logger.warning("Database session not initialized. Attempting to reconnect...")
                ATRLevelSignal.init_db_session()
                
            price_level = PriceLevel(
                pair=pair,
                level=level,
                direction=direction,
                created_at=datetime.now(),
                active=1,
                confirm_close=1 if confirm_close else 0
            )
            PriceLevel.session.add(price_level)
            PriceLevel.session.commit()
            return price_level
        except SQLAlchemyError as e:
            logger.error(f"Database error in add_level: {e}")
            PriceLevel.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error in add_level: {e}")
            PriceLevel.session.rollback()
            raise
    
    @classmethod
    def delete_level(cls, level_id: int) -> None:
        """
        Delete a price level by ID
        """
        try:
            # Ensure we have a valid session
            if not hasattr(cls, 'session') or cls.session is None:
                logger.warning("Database session not initialized. Attempting to reconnect...")
                ATRLevelSignal.init_db_session()
                
            PriceLevel.session.execute(delete(PriceLevel).where(PriceLevel.id == level_id))
            PriceLevel.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Database error in delete_level: {e}")
            PriceLevel.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error in delete_level: {e}")
            PriceLevel.session.rollback()
            raise
    
    @classmethod
    def deactivate_level(cls, level_id: int) -> None:
        """
        Deactivate a price level by ID
        """
        try:
            # Ensure we have a valid session
            if not hasattr(cls, 'session') or cls.session is None:
                logger.warning("Database session not initialized. Attempting to reconnect...")
                ATRLevelSignal.init_db_session()
                
            level = PriceLevel.session.get(PriceLevel, level_id)
            if level:
                level.active = 0
                PriceLevel.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Database error in deactivate_level: {e}")
            PriceLevel.session.rollback()
        except Exception as e:
            logger.error(f"Error in deactivate_level: {e}")
            PriceLevel.session.rollback()

class SignalHistory(ModelBase):
    """
    Signal history database model for tracking level crossing signals
    """
    __tablename__ = "signal_history"
    session: ClassVar[SessionType]

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair: Mapped[str] = mapped_column(String(25), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 'level_cross_up', 'level_cross_down', 'level_wick_up', 'level_wick_down', 'atr_surge'
    level_id: Mapped[int] = mapped_column(Integer, nullable=True)  # Reference to price level, null for ATR signals
    level_price: Mapped[float] = mapped_column(Float, nullable=True)  # Price level, null for ATR signals
    prev_price: Mapped[float] = mapped_column(Float, nullable=False)  # Previous candle close price
    current_price: Mapped[float] = mapped_column(Float, nullable=False)  # Current candle close price
    atr_value: Mapped[float] = mapped_column(Float, nullable=True)  # ATR value, null for level cross signals
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    @classmethod
    def add_signal(cls, pair: str, signal_type: str, prev_price: float, current_price: float, 
                   level_id: Optional[int] = None, level_price: Optional[float] = None, 
                   atr_value: Optional[float] = None) -> "SignalHistory":
        """
        Add a new signal to history
        
        Args:
            pair: Trading pair symbol
            signal_type: Type of signal ('level_cross_up', 'level_cross_down', 'atr_surge')
            prev_price: Previous candle close price
            current_price: Current candle close price
            level_id: ID of price level (for level crossing signals)
            level_price: Price level value (for level crossing signals)
            atr_value: ATR value (for ATR signals)
        """
        try:
            # Ensure we have a valid session
            if not hasattr(cls, 'session') or cls.session is None:
                logger.warning("Database session not initialized. Attempting to reconnect...")
                ATRLevelSignal.init_db_session()
                
            signal = SignalHistory(
                pair=pair,
                signal_type=signal_type,
                level_id=level_id,
                level_price=level_price,
                prev_price=prev_price,
                current_price=current_price,
                atr_value=atr_value,
                created_at=datetime.now()
            )
            SignalHistory.session.add(signal)
            SignalHistory.session.commit()
            return signal
        except SQLAlchemyError as e:
            logger.error(f"Database error in add_signal: {e}")
            SignalHistory.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error in add_signal: {e}")
            SignalHistory.session.rollback()
            raise
    
    @classmethod
    def get_signals(cls, pair: Optional[str] = None, signal_type: Optional[str] = None, 
                    start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, 
                    limit: int = 100, offset: int = 0) -> List["SignalHistory"]:
        """
        Get signal history with optional filtering
        
        Args:
            pair: Optional trading pair to filter by
            signal_type: Optional signal type to filter by
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            limit: Maximum number of results to return (0 means no limit)
            offset: Number of records to skip (for pagination)
            
        Returns:
            List of SignalHistory objects
        """
        try:
            # Ensure we have a valid session
            if not hasattr(cls, 'session') or cls.session is None:
                logger.warning("Database session not initialized. Attempting to reconnect...")
                ATRLevelSignal.init_db_session()
                
            filters = []
            if pair:
                filters.append(SignalHistory.pair == pair)
            if signal_type:
                filters.append(SignalHistory.signal_type == signal_type)
            if start_date:
                filters.append(SignalHistory.created_at >= start_date)
            if end_date:
                filters.append(SignalHistory.created_at <= end_date)
            
            query = select(SignalHistory).filter(*filters).order_by(SignalHistory.created_at.desc())
            
            # 添加偏移量（用于分页）
            if offset > 0:
                query = query.offset(offset)
            
            # 添加限制（如果limit > 0）
            if limit > 0:
                query = query.limit(limit)
                
            return SignalHistory.session.scalars(query).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_signals: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in get_signals: {e}")
            return []

class ATRLevelSignal(IStrategy):
    # Strategy configuration
    timeframe = '15m'  # Set timeframe to 15 minutes
    atr_length = 14  # ATR calculation period
    atr_threshold = 1.5  # Threshold for sudden increase (1.5x previous ATR)
    stoploss = -0.10  # Required stoploss (10%) added to fix validation error
    
    # Level crossing configuration
    check_level_crossing = True  # Enable level crossing detection
    
    # Database configuration
    db_initialized = False
    db_url = None
    
    @staticmethod
    def init_db_session():
        """Initialize database session for PriceLevel model"""
        try:
            # Try to get database URL from config or use default
            config_file = os.path.join('user_data', 'config.json')
            if os.path.exists(config_file):
                import json
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    ATRLevelSignal.db_url = config.get('db_url')
            
            # If no config found, use default SQLite path
            if not ATRLevelSignal.db_url:
                db_path = os.path.join('user_data', 'tradesv3.sqlite')
                ATRLevelSignal.db_url = f'sqlite:///{db_path}'
                logger.info(f"Using default database path: {db_path}")
            
            # Initialize database
            engine = create_engine(ATRLevelSignal.db_url)
            # Create tables if they don't exist
            ModelBase.metadata.create_all(engine)
            # Create scoped session factory
            session_factory = sessionmaker(bind=engine)
            session = scoped_session(session_factory)
            
            # Assign session to model classes
            PriceLevel.session = session
            SignalHistory.session = session
            
            logger.info(f"Database initialized with URL: {ATRLevelSignal.db_url}")
            logger.info(f"Database session created and assigned to models")
            
            ATRLevelSignal.db_initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            logger.error(traceback.format_exc())
            ATRLevelSignal.db_initialized = False
    
    def __init__(self, config: dict) -> None:
        """Initialize strategy with database connection"""
        super().__init__(config)
        
        # Initialize database session if not already initialized
        if not ATRLevelSignal.db_initialized:
            ATRLevelSignal.init_db_session()
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate ATR indicator
        dataframe['atr'] = ta.atr(
            high=dataframe['high'],
            low=dataframe['low'],
            close=dataframe['close'],
            length=self.atr_length
        )
        # Add previous close price calculation
        dataframe['close_prev'] = dataframe['close'].shift(1)
        # Add previous ATR calculation
        dataframe['atr_prev'] = dataframe['atr'].shift(1)
        
        # Add level crossing detection
        if self.check_level_crossing and self.dp and hasattr(self.dp, 'runmode'):
            # Only check for level crossing in live/dry run mode
            if self.dp.runmode.value in ('live', 'dry_run'):
                pair = metadata['pair']
                # Get active price levels for this pair
                try:
                    # Ensure database is initialized
                    if not ATRLevelSignal.db_initialized:
                        ATRLevelSignal.init_db_session()
                    
                    levels = PriceLevel.get_levels(pair)
                    logger.debug(f"Found {len(levels)} active price levels for {pair}")
                    
                    # Initialize level crossing columns
                    dataframe['level_cross_up'] = 0
                    dataframe['level_cross_down'] = 0
                    dataframe['level_wick_up'] = 0  # 新增：上影线流动性清扫信号
                    dataframe['level_wick_down'] = 0  # 新增：下影线流动性清扫信号
                    dataframe['level_id'] = 0  # Store the level ID for reference
                    dataframe['level_price'] = 0.0  # Store the level price for reference
                    
                    # Check each level for crossing
                    for level in levels:
                        level_price = level.level
                        level_direction = level.direction
                        require_close_confirm = bool(level.confirm_close)
                        
                        # 添加调试日志
                        last_candle_index = len(dataframe) - 1
                        if last_candle_index >= 0:
                            last_candle = dataframe.iloc[last_candle_index]
                            prev_candle = dataframe.iloc[last_candle_index-1] if last_candle_index > 0 else None
                            
                            logger.info(f"===== 调试信息 - {pair} - 价格水平: {level_price} =====")
                            logger.info(f"方向: {level_direction}, 需要收盘确认: {require_close_confirm}")
                            
                            if prev_candle is not None:
                                logger.info(f"上一根K线 - 开盘: {prev_candle['open']}, 收盘: {prev_candle['close']}, 最高: {prev_candle['high']}, 最低: {prev_candle['low']}")
                            
                            logger.info(f"当前K线 - 开盘: {last_candle['open']}, 收盘: {last_candle['close']}, 最高: {last_candle['high']}, 最低: {last_candle['low']}")
                        
                        # 检测实体向上突破（价格从下方穿过水平）
                        if level_direction in [LevelDirection.UP, LevelDirection.BOTH]:
                            if require_close_confirm:
                                # 只有当K线收盘价高于水平时才触发
                                cross_up = (dataframe['close_prev'] < level_price) & (dataframe['close'] > level_price)
                                
                                # 添加调试日志
                                if last_candle_index >= 0 and prev_candle is not None:
                                    condition1 = prev_candle['close'] < level_price
                                    condition2 = last_candle['close'] > level_price
                                    final_condition = condition1 and condition2
                                    logger.info(f"向上突破(收盘确认) - 条件1(上一收盘<水平): {condition1}, 条件2(当前收盘>水平): {condition2}, 最终结果: {final_condition}")
                                    
                                    # 检查cross_up的值
                                    has_cross_up = cross_up.any() if isinstance(cross_up, pd.Series) else bool(cross_up)
                                    logger.info(f"cross_up.any()的值: {has_cross_up}")
                                    
                                    # 强制检查最后一根K线的条件
                                    last_candle_condition = final_condition
                                    
                                    # 只有当最后一根K线满足条件时才设置信号
                                    if last_candle_condition:
                                        logger.info(f"UP CROSS detected for {pair} at level {level_price} (ID: {level.id})")
                                        # 只对满足条件的K线设置信号
                                        cross_up_indices = cross_up if isinstance(cross_up, pd.Series) else pd.Series([cross_up], index=[last_candle_index])
                                        dataframe.loc[cross_up_indices, 'level_cross_up'] = 1
                                        dataframe.loc[cross_up_indices, 'level_id'] = level.id
                                        dataframe.loc[cross_up_indices, 'level_price'] = level_price
                            else:
                                # 当K线实体任何部分穿过水平时触发（开盘价或收盘价）
                                cross_up = (dataframe['close_prev'] < level_price) & (
                                    (dataframe['open'] > level_price) | (dataframe['close'] > level_price)
                                )
                                
                                # 添加调试日志
                                if last_candle_index >= 0 and prev_candle is not None:
                                    condition1 = prev_candle['close'] < level_price
                                    condition2 = last_candle['open'] > level_price
                                    condition3 = last_candle['close'] > level_price
                                    final_condition = condition1 and (condition2 or condition3)
                                    logger.info(f"向上突破(非收盘确认) - 条件1(上一收盘<水平): {condition1}, 条件2(当前开盘>水平): {condition2}, 条件3(当前收盘>水平): {condition3}, 最终结果: {final_condition}")
                                    
                                    # 检查cross_up的值
                                    has_cross_up = cross_up.any() if isinstance(cross_up, pd.Series) else bool(cross_up)
                                    logger.info(f"cross_up.any()的值: {has_cross_up}")
                                    
                                    # 强制检查最后一根K线的条件
                                    last_candle_condition = condition1 and (condition2 or condition3)
                                    
                                    # 只有当最后一根K线满足条件时才设置信号
                                    if last_candle_condition:
                                        logger.info(f"UP CROSS detected for {pair} at level {level_price} (ID: {level.id})")
                                        # 只对满足条件的K线设置信号
                                        cross_up_indices = cross_up if isinstance(cross_up, pd.Series) else pd.Series([cross_up], index=[last_candle_index])
                                        dataframe.loc[cross_up_indices, 'level_cross_up'] = 1
                                        dataframe.loc[cross_up_indices, 'level_id'] = level.id
                                        dataframe.loc[cross_up_indices, 'level_price'] = level_price
                        
                        # 检测实体向下突破（价格从上方穿过水平）
                        if level_direction in [LevelDirection.DOWN, LevelDirection.BOTH]:
                            if require_close_confirm:
                                # 只有当K线收盘价低于水平时才触发
                                cross_down = (dataframe['close_prev'] > level_price) & (dataframe['close'] < level_price)
                                
                                # 添加调试日志
                                if last_candle_index >= 0 and prev_candle is not None:
                                    condition1 = prev_candle['close'] > level_price
                                    condition2 = last_candle['close'] < level_price
                                    final_condition = condition1 and condition2
                                    logger.info(f"向下突破(收盘确认) - 条件1(上一收盘>水平): {condition1}, 条件2(当前收盘<水平): {condition2}, 最终结果: {final_condition}")
                                    
                                    # 检查cross_down的值
                                    has_cross_down = cross_down.any() if isinstance(cross_down, pd.Series) else bool(cross_down)
                                    logger.info(f"cross_down.any()的值: {has_cross_down}")
                                    
                                    # 强制检查最后一根K线的条件
                                    last_candle_condition = final_condition
                                    
                                    # 只有当最后一根K线满足条件时才设置信号
                                    if last_candle_condition:
                                        logger.info(f"DOWN CROSS detected for {pair} at level {level_price} (ID: {level.id})")
                                        # 只对满足条件的K线设置信号
                                        cross_down_indices = cross_down if isinstance(cross_down, pd.Series) else pd.Series([cross_down], index=[last_candle_index])
                                        dataframe.loc[cross_down_indices, 'level_cross_down'] = 1
                                        dataframe.loc[cross_down_indices, 'level_id'] = level.id
                                        dataframe.loc[cross_down_indices, 'level_price'] = level_price
                            else:
                                # 当K线实体任何部分穿过水平时触发（开盘价或收盘价）
                                cross_down = (dataframe['close_prev'] > level_price) & (
                                    (dataframe['open'] < level_price) | (dataframe['close'] < level_price)
                                )
                                
                                # 添加调试日志
                                if last_candle_index >= 0 and prev_candle is not None:
                                    condition1 = prev_candle['close'] > level_price
                                    condition2 = last_candle['open'] < level_price
                                    condition3 = last_candle['close'] < level_price
                                    final_condition = condition1 and (condition2 or condition3)
                                    logger.info(f"向下突破(非收盘确认) - 条件1(上一收盘>水平): {condition1}, 条件2(当前开盘<水平): {condition2}, 条件3(当前收盘<水平): {condition3}, 最终结果: {final_condition}")
                                    
                                    # 检查cross_down的值
                                    has_cross_down = cross_down.any() if isinstance(cross_down, pd.Series) else bool(cross_down)
                                    logger.info(f"cross_down.any()的值: {has_cross_down}")
                                    
                                    # 强制检查最后一根K线的条件
                                    last_candle_condition = condition1 and (condition2 or condition3)
                                    
                                    # 只有当最后一根K线满足条件时才设置信号
                                    if last_candle_condition:
                                        logger.info(f"DOWN CROSS detected for {pair} at level {level_price} (ID: {level.id})")
                                        # 只对满足条件的K线设置信号
                                        cross_down_indices = cross_down if isinstance(cross_down, pd.Series) else pd.Series([cross_down], index=[last_candle_index])
                                        dataframe.loc[cross_down_indices, 'level_cross_down'] = 1
                                        dataframe.loc[cross_down_indices, 'level_id'] = level.id
                                        dataframe.loc[cross_down_indices, 'level_price'] = level_price
                            
                        # 检测上影线流动性清扫（上影线穿过水平但实体没有）
                        if level_direction in [LevelDirection.WICK_UP, LevelDirection.WICK_BOTH]:
                            # 修正：上影线穿过水平但实体保持在水平下方
                            # 确保上一根K线的高点低于水平，当前K线的高点高于水平，而且当前K线的开盘和收盘都低于水平
                            wick_up = (dataframe['high'].shift(1) < level_price) & (dataframe['high'] > level_price) & \
                                     (dataframe['close'] < level_price) & (dataframe['open'] < level_price)
                            
                            # 添加调试日志
                            if last_candle_index >= 0 and prev_candle is not None:
                                condition1 = prev_candle['high'] < level_price
                                condition2 = last_candle['high'] > level_price
                                condition3 = last_candle['close'] < level_price
                                condition4 = last_candle['open'] < level_price
                                final_condition = condition1 and condition2 and condition3 and condition4
                                logger.info(f"上影线流动性清扫 - 条件1(上一高点<水平): {condition1}, 条件2(当前高点>水平): {condition2}, 条件3(当前收盘<水平): {condition3}, 条件4(当前开盘<水平): {condition4}, 最终结果: {final_condition}")
                                
                                # 检查wick_up的值
                                has_wick_up = wick_up.any() if isinstance(wick_up, pd.Series) else bool(wick_up)
                                logger.info(f"wick_up.any()的值: {has_wick_up}")
                                
                                # 强制检查最后一根K线的条件
                                last_candle_condition = final_condition
                                
                                # 只有当最后一根K线满足条件时才设置信号
                                if last_candle_condition:
                                    logger.info(f"WICK UP detected for {pair} at level {level_price} (ID: {level.id})")
                                    # 只对满足条件的K线设置信号
                                    wick_up_indices = wick_up if isinstance(wick_up, pd.Series) else pd.Series([wick_up], index=[last_candle_index])
                                    dataframe.loc[wick_up_indices, 'level_wick_up'] = 1
                                    dataframe.loc[wick_up_indices, 'level_id'] = level.id
                                    dataframe.loc[wick_up_indices, 'level_price'] = level_price
                        
                        # 检测下影线流动性清扫（下影线穿过水平但实体没有）
                        if level_direction in [LevelDirection.WICK_DOWN, LevelDirection.WICK_BOTH]:
                            # 修正：下影线穿过水平但实体保持在水平上方
                            # 确保上一根K线的低点高于水平，当前K线的低点低于水平，而且当前K线的开盘和收盘都高于水平
                            wick_down = (dataframe['low'].shift(1) > level_price) & (dataframe['low'] < level_price) & \
                                       (dataframe['close'] > level_price) & (dataframe['open'] > level_price)
                            
                            # 添加调试日志
                            if last_candle_index >= 0 and prev_candle is not None:
                                condition1 = prev_candle['low'] > level_price
                                condition2 = last_candle['low'] < level_price
                                condition3 = last_candle['close'] > level_price
                                condition4 = last_candle['open'] > level_price
                                final_condition = condition1 and condition2 and condition3 and condition4
                                logger.info(f"下影线流动性清扫 - 条件1(上一低点>水平): {condition1}, 条件2(当前低点<水平): {condition2}, 条件3(当前收盘>水平): {condition3}, 条件4(当前开盘>水平): {condition4}, 最终结果: {final_condition}")
                                
                                # 检查wick_down的值
                                has_wick_down = wick_down.any() if isinstance(wick_down, pd.Series) else bool(wick_down)
                                logger.info(f"wick_down.any()的值: {has_wick_down}")
                                
                                # 强制检查最后一根K线的条件
                                last_candle_condition = final_condition
                                
                                # 只有当最后一根K线满足条件时才设置信号
                                if last_candle_condition:
                                    logger.info(f"WICK DOWN detected for {pair} at level {level_price} (ID: {level.id})")
                                    # 只对满足条件的K线设置信号
                                    wick_down_indices = wick_down if isinstance(wick_down, pd.Series) else pd.Series([wick_down], index=[last_candle_index])
                                    dataframe.loc[wick_down_indices, 'level_wick_down'] = 1
                                    dataframe.loc[wick_down_indices, 'level_id'] = level.id
                                    dataframe.loc[wick_down_indices, 'level_price'] = level_price
                            
                except SQLAlchemyError as e:
                    logger.error(f"Database error checking price levels: {e}")
                    # Initialize columns even if there was an error
                    dataframe['level_cross_up'] = 0
                    dataframe['level_cross_down'] = 0
                    dataframe['level_wick_up'] = 0
                    dataframe['level_wick_down'] = 0
                    dataframe['level_id'] = 0
                    dataframe['level_price'] = 0.0
                except Exception as e:
                    logger.error(f"Error checking price levels: {e}")
                    logger.error(traceback.format_exc())
                    # Initialize columns even if there was an error
                    dataframe['level_cross_up'] = 0
                    dataframe['level_cross_down'] = 0
                    dataframe['level_wick_up'] = 0
                    dataframe['level_wick_down'] = 0
                    dataframe['level_id'] = 0
                    dataframe['level_price'] = 0.0
            else:
                # For backtesting/hyperopt, just add the columns with zeros
                dataframe['level_cross_up'] = 0
                dataframe['level_cross_down'] = 0
                dataframe['level_wick_up'] = 0
                dataframe['level_wick_down'] = 0
                dataframe['level_id'] = 0
                dataframe['level_price'] = 0.0
                
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Add ATR sudden increase condition
        atr_increase = (
            dataframe['atr'] > dataframe['atr'].shift(1) * self.atr_threshold
        )
        
        # Add level crossing condition (if enabled)
        if self.check_level_crossing:
            level_cross_up = dataframe['level_cross_up'] == 1
            level_wick_up = dataframe['level_wick_up'] == 1  # 新增：上影线流动性清扫
            level_wick_down = dataframe['level_wick_down'] == 1  # 新增：下影线流动性清扫
            
            # Buy on either ATR increase, level crossing up, 或流动性清扫
            dataframe.loc[atr_increase | level_cross_up | level_wick_up | level_wick_down, 'buy'] = 1
        else:
            # Original ATR signal only
            dataframe.loc[atr_increase, 'buy'] = 1
        
        # Send Telegram notification when buy signal occurs
        if self.dp.runmode.value in ('live', 'dry_run'):
            last_candle = dataframe.iloc[-1]
            if last_candle['buy'] == 1:
                # Pass current candle data to notification method
                self.send_telegram_notification(metadata['pair'], last_candle)
                
        return dataframe

    # Add exit trend method to satisfy interface requirement
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signal placeholder implementation.
        Sets 'exit_long' to 0 for all rows (no active exit signals).
        """
        dataframe['exit_long'] = 0
        
        # Add level crossing down as exit signal if enabled
        if self.check_level_crossing:
            level_cross_down = dataframe['level_cross_down'] == 1
            dataframe.loc[level_cross_down, 'exit_long'] = 1
            
        return dataframe

    def send_telegram_notification(self, pair: str, candle: Series):
        """Send notification via Telegram with detailed metrics"""
        try:
            # Calculate ATR change rate safely
            if candle['atr_prev'] != 0:
                atr_change = (candle['atr'] / candle['atr_prev'] - 1) * 100
            else:
                atr_change = 0
            
            # Determine signal type
            signal_type = ""
            signal_details = ""
            signal_db_type = ""  # Type to store in database
            level_id = None
            level_price = None
            atr_value = None
            
            if self.check_level_crossing:
                if candle.get('level_cross_up', 0) == 1:
                    level_id = int(candle.get('level_id', 0))
                    level_price = float(candle.get('level_price', 0.0))
                    signal_type = "🔼 Level Cross UP"
                    signal_details = f"▫ 价格穿越上升点位: {level_price:.6f} (ID: {level_id})"
                    signal_db_type = "level_cross_up"
                elif candle.get('level_cross_down', 0) == 1:
                    level_id = int(candle.get('level_id', 0))
                    level_price = float(candle.get('level_price', 0.0))
                    signal_type = "🔽 Level Cross DOWN"
                    signal_details = f"▫ 价格穿越下降点位: {level_price:.6f} (ID: {level_id})"
                    signal_db_type = "level_cross_down"
                elif candle.get('level_wick_up', 0) == 1:
                    level_id = int(candle.get('level_id', 0))
                    level_price = float(candle.get('level_price', 0.0))
                    signal_type = "🔝 Wick UP Liquidity Sweep"
                    signal_details = f"▫ 上影线扫动流动性: {level_price:.6f} (ID: {level_id})"
                    signal_db_type = "level_wick_up"
                elif candle.get('level_wick_down', 0) == 1:
                    level_id = int(candle.get('level_id', 0))
                    level_price = float(candle.get('level_price', 0.0))
                    signal_type = "🔻 Wick DOWN Liquidity Sweep"
                    signal_details = f"▫ 下影线扫动流动性: {level_price:.6f} (ID: {level_id})"
                    signal_db_type = "level_wick_down"
                elif candle['atr'] > candle['atr_prev'] * self.atr_threshold:
                    signal_type = "🚨 ATR Surge"
                    signal_details = f"▫ ATR变动率: {atr_change:.2f}%"
                    signal_db_type = "atr_surge"
                    atr_value = float(candle['atr'])
            else:
                signal_type = "🚨 ATR Surge"
                signal_details = f"▫ ATR变动率: {atr_change:.2f}%"
                signal_db_type = "atr_surge"
                atr_value = float(candle['atr'])
                
            # Format message with required metrics
            message = (
                f"{signal_type} on {pair} ({self.timeframe})\n"
                f"{signal_details}\n"
                f"▫ 实际ATR: {candle['atr']:.6f}\n"
                f"▫ 前一价格: {candle['close_prev']:.6f}\n"
                f"▫ 当前价格: {candle['close']:.6f}"
            )
            self.dp.send_msg(message)
            
            # Store signal in history
            if signal_db_type:
                try:
                    # Ensure database is initialized
                    if not ATRLevelSignal.db_initialized:
                        ATRLevelSignal.init_db_session()
                    
                    # Record the signal
                    SignalHistory.add_signal(
                        pair=pair,
                        signal_type=signal_db_type,
                        prev_price=float(candle['close_prev']),
                        current_price=float(candle['close']),
                        level_id=level_id if level_id and level_id > 0 else None,
                        level_price=level_price if level_price else None,
                        atr_value=atr_value if atr_value else float(candle['atr'])
                    )
                    logger.info(f"Signal recorded in history: {signal_type} for {pair}")
                except Exception as e:
                    logger.error(f"Failed to record signal in history: {e}")
                    logger.error(traceback.format_exc())
                
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            logger.error(traceback.format_exc())
            
    @staticmethod
    def add_price_level(pair: str, level: float, direction: str = "both", confirm_close: bool = False) -> Dict[str, Any]:
        """
        Add a price level to monitor for crossing
        
        :param pair: Trading pair (e.g. BTC/USDT)
        :param level: Price level to monitor
        :param direction: Direction to monitor ('up', 'down', or 'both')
        :param confirm_close: If True, require candle to close beyond the level
        :return: Dictionary with level information
        """
        try:
            # Ensure database is initialized
            if not ATRLevelSignal.db_initialized:
                ATRLevelSignal.init_db_session()
                
            price_level = PriceLevel.add_level(pair, level, direction, confirm_close)
            return {
                "id": price_level.id,
                "pair": price_level.pair,
                "level": price_level.level,
                "direction": price_level.direction,
                "created_at": price_level.created_at.isoformat(),
                "active": bool(price_level.active),
                "confirm_close": bool(price_level.confirm_close)
            }
        except Exception as e:
            logger.error(f"Failed to add price level: {e}")
            logger.error(traceback.format_exc())
            return {"error": str(e)}
    
    @staticmethod
    def get_price_levels(pair: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all active price levels
        
        :param pair: Optional trading pair to filter by
        :return: List of dictionaries with level information
        """
        try:
            # Ensure database is initialized
            if not ATRLevelSignal.db_initialized:
                ATRLevelSignal.init_db_session()
                
            levels = PriceLevel.get_levels(pair)
            result = []
            for level in levels:
                result.append({
                    "id": level.id,
                    "pair": level.pair,
                    "level": level.level,
                    "direction": level.direction,
                    "created_at": level.created_at.isoformat(),
                    "active": bool(level.active),
                    "confirm_close": bool(level.confirm_close)
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get price levels: {e}")
            logger.error(traceback.format_exc())
            return []
    
    @staticmethod
    def delete_price_level(level_id: int) -> Dict[str, Any]:
        """
        Delete a price level
        
        :param level_id: ID of the price level to delete
        :return: Success/failure dictionary
        """
        try:
            # Ensure database is initialized
            if not ATRLevelSignal.db_initialized:
                ATRLevelSignal.init_db_session()
                
            PriceLevel.delete_level(level_id)
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to delete price level: {e}")
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
            
    @staticmethod
    def update_price_level(level_id: int, level: Optional[float] = None, 
                          direction: Optional[str] = None, confirm_close: Optional[bool] = None) -> Dict[str, Any]:
        """
        Update an existing price level
        
        :param level_id: ID of the price level to update
        :param level: New price level value (optional)
        :param direction: New direction (optional)
        :param confirm_close: New confirm_close value (optional)
        :return: Success/failure dictionary with updated level information
        """
        try:
            # Ensure database is initialized
            if not ATRLevelSignal.db_initialized:
                ATRLevelSignal.init_db_session()
                
            price_level = PriceLevel.session.get(PriceLevel, level_id)
            if not price_level:
                return {"success": False, "error": f"Price level with ID {level_id} not found"}
            
            # Update fields if provided
            if level is not None:
                price_level.level = level
            if direction is not None:
                price_level.direction = direction
            if confirm_close is not None:
                price_level.confirm_close = 1 if confirm_close else 0
            
            PriceLevel.session.commit()
            
            return {
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
            }
        except Exception as e:
            logger.error(f"Failed to update price level: {e}")
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_signal_history(pair: Optional[str] = None, signal_type: Optional[str] = None,
                           start_date: Optional[str] = None, end_date: Optional[str] = None,
                           limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get signal history with optional filtering
        
        :param pair: Optional trading pair to filter by
        :param signal_type: Optional signal type to filter by ('level_cross_up', 'level_cross_down', 'atr_surge')
        :param start_date: Optional start date for filtering (ISO format string)
        :param end_date: Optional end date for filtering (ISO format string)
        :param limit: Maximum number of results to return (0 means no limit)
        :param offset: Number of records to skip (for pagination)
        :return: List of dictionaries with signal information
        """
        try:
            # Ensure database is initialized
            if not ATRLevelSignal.db_initialized:
                ATRLevelSignal.init_db_session()
                
            # Convert date strings to datetime objects if provided
            start_dt = None
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date)
                except ValueError:
                    logger.warning(f"Invalid start_date format: {start_date}, expected ISO format")
                    
            end_dt = None
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date)
                except ValueError:
                    logger.warning(f"Invalid end_date format: {end_date}, expected ISO format")
            
            # Get signals from database
            signals = SignalHistory.get_signals(
                pair=pair,
                signal_type=signal_type,
                start_date=start_dt,
                end_date=end_dt,
                limit=limit,
                offset=offset
            )
            
            # Convert to dictionaries
            result = []
            for signal in signals:
                signal_dict = {
                    "id": signal.id,
                    "pair": signal.pair,
                    "signal_type": signal.signal_type,
                    "level_id": signal.level_id,
                    "level_price": signal.level_price,
                    "prev_price": signal.prev_price,
                    "current_price": signal.current_price,
                    "atr_value": signal.atr_value,
                    "created_at": signal.created_at.isoformat()
                }
                result.append(signal_dict)
            
            return result
        except Exception as e:
            logger.error(f"Failed to get signal history: {e}")
            logger.error(traceback.format_exc())
            return []