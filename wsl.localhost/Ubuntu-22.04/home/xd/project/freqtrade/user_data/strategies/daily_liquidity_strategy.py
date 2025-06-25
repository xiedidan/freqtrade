# 日线流动性战法1-日线翻转战法
# 规则：
# 清扫前日高点之后，在低时间周期中，根据单K线翻转模型入场做空。
# 清扫当日低点之后，在低时间周期中，根据单K线翻转模型入场做多。

from pandas import DataFrame

def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    # Get 1D timeframe data using Freqtrade's dataframe analyzer
    informative = self.dp.get_analyzer_dataframe(metadata['pair'], '1D')
    
    # Merge daily data into 15m timeframe using forward fill
    dataframe = dataframe.merge(
        informative[['high', 'low', 'volume']],
        right_index=True,
        left_index=True,
        how='left',
        suffixes=('', '_1D')
    ).ffill()

    # Update sweep conditions using daily reference
    dataframe['sweep_low'] = (
        (dataframe['low'] < dataframe['low_1D'].shift(1)) &  # Compare with previous day's low
        (dataframe['close'] > dataframe['low_1D'].shift(1))  # Close above swept daily level
    )
    
    dataframe['sweep_high'] = (
        (dataframe['high'] > dataframe['high_1D'].shift(1)) &  # Compare with previous day's high
        (dataframe['close'] < dataframe['high_1D'].shift(1))  # Close below swept daily level
    )

    # Update volume condition to use daily reference
    dataframe['volume_ma_1D'] = dataframe['volume_1D'].rolling(20).mean()

    # Add order block detection logic
    # Detect bullish order blocks according to SMC definition (modified for uptrend base)
    dataframe['bullish_order_block'] = (
        (dataframe['low'] == dataframe['low'].rolling(3, center=True).min()) &  # Local low
        # Fix future data reference by checking previous candles instead of future
        (dataframe['high'] < dataframe['low'].shift(2))  # FVG above (use past 2 candles instead of future)
    )

    # Detect bearish order blocks (large bearish candle after sweep)
    dataframe['bearish_order_block'] = (
        (dataframe['high'] == dataframe['high'].rolling(3, center=True).max()) &  # Local high
        # Fix future data reference by checking previous candles instead of future
        (dataframe['low'] > dataframe['high'].shift(2))  # FVG below (use past 2 candles instead of future)
    )
    
    # Track most recent order block levels
    dataframe['order_block_low'] = dataframe['low'].where(dataframe['bullish_order_block']).ffill()
    dataframe['order_block_high'] = dataframe['high'].where(dataframe['bearish_order_block']).ffill()

    dataframe['long_signal'] = (
        dataframe['sweep_low'] &
        (dataframe['rsi'] < 30) &
        (dataframe['volume'] > dataframe['volume_ma_1D'])
    )
    
    # Add short signal logic
    dataframe['short_signal'] = (
        dataframe['sweep_high'] &
        (dataframe['rsi'] > 70) &
        (dataframe['volume'] > dataframe['volume_ma_1D'])
    )
    return dataframe

def populate_entry_trend(self, dataframe, **kwargs):
    dataframe.loc[
        (
            dataframe['short_signal'] &
            (dataframe['high'] > dataframe['order_block_high']) &  # Price tests order block
            (dataframe['volume'] > 0)
        ),
        'enter_short'] = 1

    dataframe.loc[
        (
            dataframe['long_signal'] &
            (dataframe['low'] < dataframe['order_block_low']) &  # Price tests order block
            (dataframe['volume'] > 0)
        ),
        'enter_long'] = 1
    
    return dataframe