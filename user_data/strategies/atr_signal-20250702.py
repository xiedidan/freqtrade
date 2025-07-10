import logging
from freqtrade.strategy import IStrategy
from pandas import DataFrame, Series
import pandas_ta as ta

logger = logging.getLogger(__name__)

class ATRSignal(IStrategy):
    # Add new class variables for ATR configuration
    timeframe = '15m'  # Set timeframe to 15 minutes
    atr_length = 14  # ATR calculation period
    atr_threshold = 1.5  # Threshold for sudden increase (1.5x previous ATR)
    stoploss = -0.10  # Required stoploss (10%) added to fix validation error

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
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Add ATR sudden increase condition
        atr_increase = (
            dataframe['atr'] > dataframe['atr'].shift(1) * self.atr_threshold
        )
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
        return dataframe

    def send_telegram_notification(self, pair: str, candle: Series):
        """Send buy signal notification via Telegram with detailed metrics"""
        try:
            # Calculate ATR change rate safely
            if candle['atr_prev'] != 0:
                atr_change = (candle['atr'] / candle['atr_prev'] - 1) * 100
            else:
                atr_change = 0
                
            # Format message with required metrics
            message = (
                f"🚨 ATR surge signal on {pair} ({self.timeframe})\n"
                f"▫ ATR变动率: {atr_change:.2f}%\n"
                f"▫ 实际ATR: {candle['atr']:.6f}\n"
                f"▫ 前一价格: {candle['close_prev']:.6f}\n"
                f"▫ 当前价格: {candle['close']:.6f}"
            )
            self.dp.send_msg(message)
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")