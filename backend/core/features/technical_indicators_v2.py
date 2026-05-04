
import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List, Tuple, Optional
import warnings
import logging
from datetime import datetime, timedelta
from scipy import stats
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from scipy.signal import argrelextrema
import os

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

class EnhancedTechnicalIndicatorsGeneric:
    """
    Technical Indicators Calculator focused on categorical/binary features
    to prevent overfitting in decision tree models
    """
    
    def __init__(self, primary_timeframe='5m'):
        self.primary_timeframe = primary_timeframe
        self.fibonacci_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.414, 1.618, 2.0, 2.618]
        self.support_resistance_periods = [20, 50, 100, 200]

    @staticmethod
    def _candles_per_hour_from_tf(tf: str) -> int:
        """Resolve candles-per-hour from the timeframe label, never from index diffs.

        Computing it from ``dt_series[1] - dt_series[0]`` blows up on weekly
        forex bars where the first gap straddles a weekend (Sun 22:00 → Mon
        02:00 = 4h, so a 15m frame falsely reports 1 candle every 4h, and
        ``int(60/240)==0`` later poisons every rolling-window call).
        """
        s = (tf or "").strip().lower()
        # minutes per candle
        minutes = {
            "1m": 1, "2m": 2, "5m": 5, "10m": 10, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "1d": 1440, "1w": 1440 * 7,
        }.get(s)
        if not minutes:
            return 4  # default: 15m frequency, harmless fallback
        # cap at 1 so the rolling windows are always at least 1 candle
        return max(1, 60 // minutes if minutes <= 60 else 1)
        
    @staticmethod
    def _ensure_float64(series: pd.Series) -> np.ndarray:
        """Ensure the series is float64 for TA-Lib compatibility"""
        return series.astype(np.float64).values
    
    @staticmethod
    def _safe_divide(numerator: pd.Series, denominator: pd.Series, fill_value: float = 0.0) -> pd.Series:
        """Safe division with handling of zero division"""
        return np.where(denominator != 0, numerator / denominator, fill_value)
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all categorical/binary technical indicators and features"""
        df = df.copy()
        
        # Ensure OHLCV columns exist and are float64
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = df[col].astype(np.float64)
        
        # Handle volume column
        if 'volume' not in df.columns:
            logger.warning("Volume column not found, creating default volume data")
            df['volume'] = 1000.0
        else:
            df['volume'] = df['volume'].astype(np.float64)
        
        print("Calculating categorical technical indicators...")
        
        # First calculate raw indicators for feature engineering
        df = self._calculate_raw_indicators(df)
        
        # Then create categorical features
        df = self._calculate_trend_features(df)
        df = self._calculate_momentum_features(df)
        df = self._calculate_volatility_features(df)
        df = self._calculate_volume_features(df)
        df = self._calculate_support_resistance_features(df)
        df = self._calculate_candlestick_features(df)
        df = self._calculate_bollinger_band_features(df)
        df = self._calculate_fibonacci_features(df)
        df = self._calculate_market_structure_features(df)
        df = self._calculate_divergence_features(df)
        df = self._calculate_session_features(df)
        df = self._calculate_multi_timeframe_features(df)
        df = self._calculate_enhanced_multi_timeframe_alignment(df)
        df = self._calculate_price_action_features(df)
        df = self._calculate_level_interaction_features(df)
        df = self._calculate_momentum_regime_features(df)
        df = self._calculate_volatility_regime_features(df)
        df = self._calculate_trend_strength_features(df)
        df = self._calculate_reversal_pattern_features(df)
        df = self._calculate_breakout_features(df)
        df = self._calculate_consolidation_features(df)
        df = self._calculate_impulse_correction_features(df)
        # Add these lines after existing calculations and before cleanup
        df = self._calculate_fair_value_gap_features(df)
        df = self._calculate_market_structure_breaks(df)
        df = self._calculate_order_flow_features(df)
        df = self._calculate_liquidity_features(df)
        df = self._calculate_enhanced_sideways_filters(df)
        df = self._calculate_advanced_smc_features(df)
        df = self._calculate_retracement_strategy_features(df)
        df = self._calculate_enhanced_session_features(df)
        df = self._calculate_session_start_activity_features(df)
        df = self._calculate_volume_price_divergence_features(df) 
        df = self._calculate_mean_reversion_statistical_features(df)
        df = self._calculate_kalman_trend_features(df)

        # Clean up - remove raw indicators to avoid overfitting
        df = self._cleanup_raw_indicators(df)
        
        # Fill NaN values
        feature_cols = [col for col in df.columns if col not in ['open', 'high', 'low', 'close', 'volume']]
        df[feature_cols] = df[feature_cols].fillna(method='ffill').fillna(0)
        
        print(f"Categorical technical indicators calculated. Total feature columns: {len(feature_cols)}")
        return df
    

    def _calculate_enhanced_session_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate enhanced session-based features with proper session sequence logic"""
        
        if hasattr(df.index, 'hour') or 'datetime' in df.columns:
            if 'datetime' in df.columns:
                dt_series = pd.to_datetime(df['datetime'])
            else:
                dt_series = df.index
            
            hour = dt_series.hour

            # Resolve from the engine's declared primary_timeframe — robust against
            # weekend gaps in forex bars. (See _candles_per_hour_from_tf docstring.)
            candles_per_hour = self._candles_per_hour_from_tf(self.primary_timeframe)
            
            # Session lengths in candles
            asia_session_candles = candles_per_hour * 9    # 9 hours
            london_session_candles = candles_per_hour * 8  # 8 hours  
            ny_session_candles = candles_per_hour * 8      # 8 hours
            daily_candles = candles_per_hour * 24          # 24 hours
            
            # Define session boundaries (UTC time for XAUUSD)
            asia_session_mask = ((hour >= 23) | (hour < 8))      # 23:00-08:00 UTC
            london_session_mask = ((hour >= 8) & (hour < 16))    # 08:00-16:00 UTC  
            ny_session_mask = ((hour >= 13) & (hour < 21))       # 13:00-21:00 UTC
            
            # === Calculate session highs/lows ===
            # Asia session highs/lows
            asia_highs = df['high'].where(asia_session_mask, np.nan)
            asia_lows = df['low'].where(asia_session_mask, np.nan)
            asia_session_high = asia_highs.rolling(window=asia_session_candles, min_periods=1).max().fillna(method='ffill')
            asia_session_low = asia_lows.rolling(window=asia_session_candles, min_periods=1).min().fillna(method='ffill')
            
            # London session highs/lows
            london_highs = df['high'].where(london_session_mask, np.nan)
            london_lows = df['low'].where(london_session_mask, np.nan)
            london_session_high = london_highs.rolling(window=london_session_candles, min_periods=1).max().fillna(method='ffill')
            london_session_low = london_lows.rolling(window=london_session_candles, min_periods=1).min().fillna(method='ffill')
            
            # NY session highs/lows  
            ny_highs = df['high'].where(ny_session_mask, np.nan)
            ny_lows = df['low'].where(ny_session_mask, np.nan)
            ny_session_high = ny_highs.rolling(window=ny_session_candles, min_periods=1).max().fillna(method='ffill')
            ny_session_low = ny_lows.rolling(window=ny_session_candles, min_periods=1).min().fillna(method='ffill')
            
            # === Previous session reference logic ===
            # When in London session -> look at previous Asia session
            # When in NY session -> look at previous London session  
            # When in Asia session -> look at previous NY session
            
            prev_session_high = np.where(
                london_session_mask, asia_session_high.shift(asia_session_candles),     # London looks at prev Asia
                np.where(
                    ny_session_mask, london_session_high.shift(london_session_candles), # NY looks at prev London
                    ny_session_high.shift(ny_session_candles)                           # Asia looks at prev NY
                )
            )
            
            prev_session_low = np.where(
                london_session_mask, asia_session_low.shift(asia_session_candles),      # London looks at prev Asia
                np.where(
                    ny_session_mask, london_session_low.shift(london_session_candles),  # NY looks at prev London  
                    ny_session_low.shift(ny_session_candles)                            # Asia looks at prev NY
                )
            )
            
            # === Previous day high/low ===
            daily_high = df['high'].rolling(window=daily_candles, min_periods=1).max()
            daily_low = df['low'].rolling(window=daily_candles, min_periods=1).min()
            prev_day_high = daily_high.shift(daily_candles)  # Previous day high
            prev_day_low = daily_low.shift(daily_candles)    # Previous day low
            
            # === Feature calculations ===
            # Previous session level breaches
            prev_session_high_breach = (df['close'] - prev_session_high) / df['close']
            prev_session_low_breach = (prev_session_low - df['close']) / df['close']
            
            # Previous day level breaches
            prev_day_high_breach = (df['close'] - prev_day_high) / df['close'] 
            prev_day_low_breach = (prev_day_low - df['close']) / df['close']
            
            # Binary features
            df['above_prev_session_high'] = (prev_session_high_breach > 0.002).astype(int)    # >0.2% above
            df['below_prev_session_low'] = (prev_session_low_breach > 0.002).astype(int)      # >0.2% below
            df['above_prev_day_high'] = (prev_day_high_breach > 0.002).astype(int)           # >0.2% above prev day high
            df['below_prev_day_low'] = (prev_day_low_breach > 0.002).astype(int)             # >0.2% below prev day low
            
        return df

    def _calculate_raw_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate raw indicators needed for feature engineering"""
        close_data = self._ensure_float64(df['close'])
        high_data = self._ensure_float64(df['high'])
        low_data = self._ensure_float64(df['low'])
        volume_data = self._ensure_float64(df['volume'])
        
        # Moving averages (needed for trend features)
        ma_periods = [5, 8, 13, 21, 34, 50, 89, 100, 200]
        for period in ma_periods:
            if len(df) >= period:
                df[f'_sma_{period}'] = talib.SMA(close_data, timeperiod=period)
                df[f'_ema_{period}'] = talib.EMA(close_data, timeperiod=period)
        
        # RSI
        rsi_periods = [2, 9, 14, 21, 30]
        for period in rsi_periods:
            if len(df) >= period:
                df[f'_rsi_{period}'] = talib.RSI(close_data, timeperiod=period)
        
        # MACD
        macd_line, signal_line, histogram = talib.MACD(close_data, fastperiod=12, slowperiod=26, signalperiod=9)
        df['_macd_line'] = macd_line
        df['_macd_signal'] = signal_line
        df['_macd_histogram'] = histogram
        
        # Stochastic
        stoch_k, stoch_d = talib.STOCH(high_data, low_data, close_data, fastk_period=14, slowk_period=3, slowd_period=3)
        df['_stoch_k'] = stoch_k
        df['_stoch_d'] = stoch_d
        
        # ADX
        df['_adx'] = talib.ADX(high_data, low_data, close_data, timeperiod=14)
        df['_plus_di'] = talib.PLUS_DI(high_data, low_data, close_data, timeperiod=14)
        df['_minus_di'] = talib.MINUS_DI(high_data, low_data, close_data, timeperiod=14)
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = talib.BBANDS(close_data, timeperiod=20, nbdevup=2, nbdevdn=2)
        df['_bb_upper'] = bb_upper
        df['_bb_middle'] = bb_middle
        df['_bb_lower'] = bb_lower
        
        # ATR
        df['_atr'] = talib.ATR(high_data, low_data, close_data, timeperiod=14)
        
        # Volume indicators
        df['_obv'] = talib.OBV(close_data, volume_data)
        df['_mfi'] = talib.MFI(high_data, low_data, close_data, volume_data, timeperiod=14)
        
        # Williams %R
        df['_williams_r'] = talib.WILLR(high_data, low_data, close_data, timeperiod=14)
        
        # CCI
        df['_cci'] = talib.CCI(high_data, low_data, close_data, timeperiod=14)
        
        # Additional calculations
        df['_true_range'] = np.maximum(df['high'] - df['low'], 
                                      np.maximum(abs(df['high'] - df['close'].shift(1)),
                                                abs(df['low'] - df['close'].shift(1))))
        
        # Price changes
        df['_price_change_1'] = df['close'].pct_change(1)
        df['_price_change_5'] = df['close'].pct_change(5)
        df['_price_change_20'] = df['close'].pct_change(20)
        
        # Volume changes
        df['_volume_change_1'] = df['volume'].pct_change(1)
        df['_volume_change_5'] = df['volume'].pct_change(5)

        # Market Microstructure Raw Calculations (add after existing calculations)
        # Fair Value Gap detection
        df['_body_high'] = df[['open', 'close']].max(axis=1)
        df['_body_low'] = df[['open', 'close']].min(axis=1)

        # Order flow imbalance
        df['_buying_pressure'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        df['_selling_pressure'] = (df['high'] - df['close']) / (df['high'] - df['low'])

        # Liquidity zones (simplified)
        df['_high_of_day'] = df['high'].rolling(288).max()  # 24H for 5min data
        df['_low_of_day'] = df['low'].rolling(288).min()

        # Price efficiency
        df['_price_efficiency'] = abs(df['close'] - df['open']) / (df['high'] - df['low'])

        # Market sessions high/low
        df['_session_high'] = df['high'].rolling(72).max()  # 6H session
        df['_session_low'] = df['low'].rolling(72).min()

        # Volume-based calculations for new features
        df['_volume_ma_20'] = df['volume'].rolling(20).mean()
        df['_volume_std_20'] = df['volume'].rolling(20).std()
        df['_price_std_50'] = df['close'].rolling(50).std()
        df['_price_ma_50'] = df['close'].rolling(50).mean()

        # Statistical measures
        df['_price_zscore_50'] = (df['close'] - df['_price_ma_50']) / df['_price_std_50']
        df['_ema_21_distance'] = abs(df['close'] - df['_ema_21']) / df['close']

        # Kalman filter simple implementation
        df['_kalman_trend'] = self._calculate_simple_kalman_filter(df['close'])
        
        return df
    
    def _calculate_session_start_activity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate session start activity features"""
        
        if hasattr(df.index, 'hour') or 'datetime' in df.columns:
            if 'datetime' in df.columns:
                dt_series = pd.to_datetime(df['datetime'])
            else:
                dt_series = df.index
            
            hour = dt_series.hour
            
            # London session start (8:00 UTC)
            london_first_2h = ((hour >= 8) & (hour < 10))
            # NY session start (13:00 UTC)  
            ny_first_2h = ((hour >= 13) & (hour < 15))
            
            # Volume analysis at session starts
            volume_6h_avg = df['volume'].rolling(72).mean()  # 6 hours for 5min data
            
            # London open volume surge
            london_volume_surge = (london_first_2h & (df['volume'] > volume_6h_avg * 1.5))
            df['london_open_volume_surge'] = london_volume_surge.astype(int)
            
            # NY open volume surge
            ny_volume_surge = (ny_first_2h & (df['volume'] > volume_6h_avg * 1.5))
            df['ny_open_volume_surge'] = ny_volume_surge.astype(int)
            
            # Session transition momentum
            asia_to_london = (hour == 8)
            london_to_ny = (hour == 13)
            
            momentum_1h = df['close'].pct_change(12)  # 1 hour momentum for 5min data
            momentum_shift = abs(momentum_1h - momentum_1h.shift(12)) > 0.005
            
            df['session_transition_momentum_shift'] = ((asia_to_london | london_to_ny) & momentum_shift).astype(int)
            
            # Gap behavior at London open
            if '_atr' in df.columns:
                london_gap = np.where((hour == 8), abs(df['open'] - df['close'].shift(1)), 0)
                london_gap_normalized = london_gap / df['_atr']
                df['london_open_significant_gap'] = (london_gap_normalized > 0.5).astype(int)
            
            # NY open volatility spike
            atr_4h_avg = df['_atr'].rolling(48).mean() if '_atr' in df.columns else pd.Series(0, index=df.index)
            ny_volatility_spike = (ny_first_2h & (df['_atr'] > atr_4h_avg * 1.5))
            df['ny_open_volatility_spike'] = ny_volatility_spike.astype(int)
            
            # Price efficiency at session starts
            session_starts = ((hour == 8) | (hour == 13))
            price_change = abs(df['close'].pct_change(12))  # 1 hour change
            volume_change = df['volume'].pct_change(12)
            price_efficiency = np.where(volume_change > 0, price_change / volume_change, 0)
            efficiency_threshold = np.nanpercentile(price_efficiency[price_efficiency > 0], 80) if np.any(price_efficiency > 0) else 0
            df['session_start_high_efficiency'] = (session_starts & (price_efficiency > efficiency_threshold)).astype(int)
            
        return df

    def _calculate_volume_price_divergence_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volume-price divergence features"""
        
        if '_volume_std_20' in df.columns:
            # Volume spike detection
            volume_spike_2std = (df['volume'] > df['_volume_ma_20'] + 2 * df['_volume_std_20'])
            volume_spike_3std = (df['volume'] > df['_volume_ma_20'] + 3 * df['_volume_std_20'])
            
            # Price movement categories
            price_change_1 = df['_price_change_1']
            price_std_20 = abs(price_change_1).rolling(20).std()
            
            small_price_move = (abs(price_change_1) < 0.5 * price_std_20)
            large_price_move = (abs(price_change_1) > 1.5 * price_std_20)
            
            # Volume-price divergence patterns
            df['volume_spike_small_movement'] = (volume_spike_2std & small_price_move).astype(int)
            df['volume_spike_large_movement'] = (volume_spike_2std & large_price_move).astype(int)
            
            # Volume trend vs price trend
            volume_trend = (df['volume'] > df['volume'].shift(1)).rolling(5).sum()
            price_trend = (df['close'] > df['close'].shift(1)).rolling(5).sum()
            
            df['decreasing_volume_trend_continuation'] = ((volume_trend <= 2) & (price_trend >= 4)).astype(int)
            
            # Volume-price efficiency ratio
            volume_change = df['volume'].pct_change(1)
            efficiency_ratio = np.where(volume_change > 0, abs(price_change_1) / volume_change, 0)
            efficiency_percentile = pd.Series(efficiency_ratio).rolling(50).rank(pct=True)
            
            df['high_volume_efficiency'] = (efficiency_percentile > 0.8).astype(int)
            df['low_volume_efficiency'] = (efficiency_percentile < 0.2).astype(int)
            
            # Climax volume patterns
            df['climax_volume_reversal'] = (volume_spike_3std.shift(1) & 
                                        (price_change_1 * price_change_1.shift(1) < 0)).astype(int)
            
            # Stealth accumulation (high volume, sideways price)
            sideways_price = (abs(df['close'].pct_change(10)) < 0.005)
            high_avg_volume = (df['volume'].rolling(10).mean() > df['_volume_ma_20'] * 1.2)
            df['stealth_accumulation'] = (sideways_price & high_avg_volume).astype(int)
            
            # Volume momentum vs price momentum divergence
            volume_momentum = df['volume'].pct_change(5)
            price_momentum = df['close'].pct_change(5)
            
            divergence = ((volume_momentum > 0) & (price_momentum < 0)) | ((volume_momentum < 0) & (price_momentum > 0))
            df['volume_momentum_divergence'] = divergence.astype(int)
            
            # Exhaustion patterns (high volume, small body)
            if 'small_body' in df.columns:
                df['exhaustion_volume_pattern'] = (volume_spike_2std & (df['small_body'] == 1)).astype(int)
        
        return df

    def _calculate_mean_reversion_statistical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate mean reversion statistical features"""
        
        if '_price_zscore_50' in df.columns:
            # Extreme price deviations
            df['price_3std_above_mean'] = (df['_price_zscore_50'] > 3).astype(int)
            df['price_3std_below_mean'] = (df['_price_zscore_50'] < -3).astype(int)
            df['price_2std_extreme'] = (abs(df['_price_zscore_50']) > 2).astype(int)
            
            # RSI extreme with historical context
            if '_rsi_14' in df.columns:
                rsi_percentile = df['_rsi_14'].rolling(200).rank(pct=True)
                df['rsi_extreme_historical_context'] = ((df['_rsi_14'] < 20) & (rsi_percentile < 0.1) |
                                                    (df['_rsi_14'] > 80) & (rsi_percentile > 0.9)).astype(int)
            
            # Bollinger band squeeze with expansion potential
            if '_bb_upper' in df.columns and '_bb_lower' in df.columns:
                bb_width = (df['_bb_upper'] - df['_bb_lower']) / df['_bb_middle']
                bb_width_percentile = bb_width.rolling(100).rank(pct=True)
                
                squeeze_duration = (bb_width_percentile < 0.2).rolling(10).sum()
                df['bb_squeeze_expansion_potential'] = (squeeze_duration >= 8).astype(int)
            
            # Volatility compression extreme
            if '_atr' in df.columns:
                atr_percentile = df['_atr'].rolling(100).rank(pct=True)
                compression_duration = (atr_percentile < 0.1).rolling(15).sum()
                df['volatility_compression_extreme'] = (compression_duration >= 12).astype(int)
            
            # Distance from EMA extremes
            if '_ema_21_distance' in df.columns:
                ema_distance_percentile = df['_ema_21_distance'].rolling(100).rank(pct=True)
                df['price_stretch_from_ema'] = (ema_distance_percentile > 0.95).astype(int)
            
            # Multiple mean reversion signals confluence
            reversion_signals = []
            if 'price_2std_extreme' in df.columns:
                reversion_signals.append(df['price_2std_extreme'])
            if 'rsi_extreme_historical_context' in df.columns:
                reversion_signals.append(df['rsi_extreme_historical_context'])
            if 'price_stretch_from_ema' in df.columns:
                reversion_signals.append(df['price_stretch_from_ema'])
                
            if reversion_signals:
                reversion_score = pd.concat(reversion_signals, axis=1).sum(axis=1)
                df['mean_reversion_probability_high'] = (reversion_score >= 2).astype(int)
            
            # Support/resistance magnetic effect
            if 'near_support_20' in df.columns and 'near_resistance_20' in df.columns:
                near_level = (df['near_support_20'] | df['near_resistance_20'])
                magnetic_effect = near_level.rolling(3).sum() >= 2
                df['support_resistance_magnetic_effect'] = magnetic_effect.astype(int)
        
        return df

    def _calculate_kalman_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Kalman filter and advanced higher timeframe features"""
        
        if '_kalman_trend' in df.columns:
            # Kalman trend direction
            kalman_direction = df['_kalman_trend'].diff()
            df['kalman_trend_bullish'] = (kalman_direction > 0).astype(int)
            df['kalman_trend_bearish'] = (kalman_direction < 0).astype(int)
            
            # Kalman trend strength
            kalman_strength = abs(kalman_direction)
            kalman_strength_percentile = kalman_strength.rolling(50).rank(pct=True)
            df['kalman_trend_strong'] = (kalman_strength_percentile > 0.8).astype(int)
            
            # Trend regime change signal
            trend_change = ((kalman_direction > 0) & (kalman_direction.shift(1) <= 0)) | \
                        ((kalman_direction < 0) & (kalman_direction.shift(1) >= 0))
            volume_confirmation = df['volume'] > df['_volume_ma_20'] if '_volume_ma_20' in df.columns else pd.Series(True, index=df.index)
            df['trend_regime_change_signal'] = (trend_change & volume_confirmation).astype(int)
            
        # Multi-timeframe trend alignment score
        htf_trend_cols = [col for col in df.columns if 'htf' in col and 'trend' in col and 'bullish' in col]
        if len(htf_trend_cols) >= 2:
            # Weight higher timeframes more heavily
            weights = [0.3, 0.5, 0.7, 1.0]  # Ascending weights for higher timeframes
            
            alignment_score = 0
            for i, col in enumerate(htf_trend_cols[:4]):
                weight = weights[min(i, len(weights)-1)]
                alignment_score += df[col] * weight
                
            max_score = sum(weights[:len(htf_trend_cols)])
            normalized_score = alignment_score / max_score
            
            df['multi_timeframe_trend_alignment_strong'] = (normalized_score > 0.75).astype(int)
            df['multi_timeframe_trend_alignment_weak'] = (normalized_score < 0.25).astype(int)
        
        # Momentum regime persistence
        if 'momentum_regime_bullish' in df.columns:
            bull_persistence = df['momentum_regime_bullish'].rolling(20).sum()
            bear_persistence = df['momentum_regime_bearish'].rolling(20).sum()
            
            df['momentum_regime_persistent_bull'] = (bull_persistence >= 15).astype(int)  # 75% of last 20 periods
            df['momentum_regime_persistent_bear'] = (bear_persistence >= 15).astype(int)
        
        # Cross-timeframe volatility regime
        if 'volatility_regime_high' in df.columns:
            volatility_consistency = df['volatility_regime_high'].rolling(10).sum()
            df['volatility_regime_consistent_high'] = (volatility_consistency >= 7).astype(int)
            df['volatility_regime_consistent_low'] = (df['volatility_regime_low'].rolling(10).sum() >= 7).astype(int)
        
        return df

    def _calculate_simple_kalman_filter(self, price_series: pd.Series, process_variance: float = 0.01, measurement_variance: float = 1.0) -> pd.Series:
        """Simple Kalman filter implementation for trend smoothing"""
        
        n = len(price_series)
        if n == 0:
            return price_series
        
        # Initialize
        x = np.zeros(n)  # State estimates
        P = np.zeros(n)  # Error covariances
        
        # Initial values
        x[0] = price_series.iloc[0]
        P[0] = 1.0
        
        for i in range(1, n):
            # Prediction
            x_pred = x[i-1]
            P_pred = P[i-1] + process_variance
            
            # Update
            K = P_pred / (P_pred + measurement_variance)  # Kalman gain
            x[i] = x_pred + K * (price_series.iloc[i] - x_pred)
            P[i] = (1 - K) * P_pred
        
        return pd.Series(x, index=price_series.index)


    def _calculate_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate trend-based categorical features"""
        
        # === EMA Trend Features ===
        ema_pairs = [(8, 21), (13, 34), (21, 55), (50, 200)]
        for fast, slow in ema_pairs:
            if f'_ema_{fast}' in df.columns and f'_ema_{slow}' in df.columns:
                # Trend direction
                df[f'ema_trend_{fast}_{slow}_bullish'] = (df[f'_ema_{fast}'] > df[f'_ema_{slow}']).astype(int)
                df[f'ema_trend_{fast}_{slow}_bearish'] = (df[f'_ema_{fast}'] < df[f'_ema_{slow}']).astype(int)
                
                # Crossover signals
                df[f'ema_bullish_cross_{fast}_{slow}'] = ((df[f'_ema_{fast}'] > df[f'_ema_{slow}']) & 
                                                         (df[f'_ema_{fast}'].shift(1) <= df[f'_ema_{slow}'].shift(1))).astype(int)
                df[f'ema_bearish_cross_{fast}_{slow}'] = ((df[f'_ema_{fast}'] < df[f'_ema_{slow}']) & 
                                                         (df[f'_ema_{fast}'].shift(1) >= df[f'_ema_{slow}'].shift(1))).astype(int)
                
                # Trend strength
                separation = abs(df[f'_ema_{fast}'] - df[f'_ema_{slow}']) / df['close']
                separation_threshold = separation.rolling(50).quantile(0.7)
                df[f'ema_strong_trend_{fast}_{slow}'] = (separation > separation_threshold).astype(int)
                df[f'ema_weak_trend_{fast}_{slow}'] = (separation < separation.rolling(50).quantile(0.3)).astype(int)
        
        # === Price vs MA Position ===
        ma_periods = [8, 21, 50, 200]
        for period in ma_periods:
            if f'_ema_{period}' in df.columns:
                df[f'price_above_ema_{period}'] = (df['close'] > df[f'_ema_{period}']).astype(int)
                df[f'price_below_ema_{period}'] = (df['close'] < df[f'_ema_{period}']).astype(int)
                
                # Distance categories
                distance = abs(df['close'] - df[f'_ema_{period}']) / df['close']
                df[f'price_far_from_ema_{period}'] = (distance > distance.rolling(50).quantile(0.8)).astype(int)
                df[f'price_near_ema_{period}'] = (distance < distance.rolling(50).quantile(0.2)).astype(int)
        
        # === ADX Trend Strength ===
        if '_adx' in df.columns:
            df['adx_strong_trend'] = (df['_adx'] > 25).astype(int)
            df['adx_weak_trend'] = ((df['_adx'] >= 20) & (df['_adx'] <= 25)).astype(int)
            df['adx_no_trend'] = (df['_adx'] < 20).astype(int)
            df['adx_very_strong_trend'] = (df['_adx'] > 40).astype(int)
            
            # ADX direction
            if '_plus_di' in df.columns and '_minus_di' in df.columns:
                df['adx_bullish_direction'] = (df['_plus_di'] > df['_minus_di']).astype(int)
                df['adx_bearish_direction'] = (df['_plus_di'] < df['_minus_di']).astype(int)
                
                # DI crossovers
                df['di_bullish_cross'] = ((df['_plus_di'] > df['_minus_di']) & 
                                         (df['_plus_di'].shift(1) <= df['_minus_di'].shift(1))).astype(int)
                df['di_bearish_cross'] = ((df['_plus_di'] < df['_minus_di']) & 
                                         (df['_plus_di'].shift(1) >= df['_minus_di'].shift(1))).astype(int)
        
        # === Multi-MA Alignment ===
        if all(f'_ema_{p}' in df.columns for p in [8, 21, 50]):
            # Bullish alignment (8 > 21 > 50)
            df['ma_bullish_alignment'] = ((df['_ema_8'] > df['_ema_21']) & 
                                         (df['_ema_21'] > df['_ema_50'])).astype(int)
            # Bearish alignment (8 < 21 < 50)
            df['ma_bearish_alignment'] = ((df['_ema_8'] < df['_ema_21']) & 
                                         (df['_ema_21'] < df['_ema_50'])).astype(int)
            # Mixed alignment (sideways)
            df['ma_mixed_alignment'] = (~((df['_ema_8'] > df['_ema_21']) & (df['_ema_21'] > df['_ema_50'])) & 
                                       ~((df['_ema_8'] < df['_ema_21']) & (df['_ema_21'] < df['_ema_50']))).astype(int)
        
        return df
    
    def _calculate_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate momentum-based categorical features"""
        
        # === RSI Features ===
        rsi_periods = [14, 21]
        for period in [14, 21]:
            if f'_rsi_{period}' in df.columns:
                rsi = df[f'_rsi_{period}']
                
                # Classic levels
                df[f'rsi_{period}_oversold'] = (rsi < 30).astype(int)
                df[f'rsi_{period}_overbought'] = (rsi > 70).astype(int)
                df[f'rsi_{period}_extreme_oversold'] = (rsi < 20).astype(int)
                df[f'rsi_{period}_extreme_overbought'] = (rsi > 80).astype(int)
                
                # More nuanced levels
                df[f'rsi_{period}_weak_bearish'] = ((rsi >= 30) & (rsi < 40)).astype(int)
                df[f'rsi_{period}_neutral'] = ((rsi >= 40) & (rsi <= 60)).astype(int)
                df[f'rsi_{period}_weak_bullish'] = ((rsi > 60) & (rsi <= 70)).astype(int)
                
                # RSI momentum
                rsi_change = rsi.diff()
                df[f'rsi_{period}_rising'] = (rsi_change > 0).astype(int)
                df[f'rsi_{period}_falling'] = (rsi_change < 0).astype(int)
                df[f'rsi_{period}_accelerating_up'] = (rsi_change > rsi_change.shift(1)).astype(int)
                df[f'rsi_{period}_accelerating_down'] = (rsi_change < rsi_change.shift(1)).astype(int)
                
                # RSI reversals from extremes
                df[f'rsi_{period}_reversal_from_oversold'] = ((rsi > 30) & (rsi.shift(1) <= 30)).astype(int)
                df[f'rsi_{period}_reversal_from_overbought'] = ((rsi < 70) & (rsi.shift(1) >= 70)).astype(int)
        
        # === MACD Features ===
        if '_macd_line' in df.columns and '_macd_signal' in df.columns:
            # MACD position
            df['macd_bullish'] = (df['_macd_line'] > df['_macd_signal']).astype(int)
            df['macd_bearish'] = (df['_macd_line'] < df['_macd_signal']).astype(int)
            
            # MACD crossovers
            df['macd_bullish_cross'] = ((df['_macd_line'] > df['_macd_signal']) & 
                                       (df['_macd_line'].shift(1) <= df['_macd_signal'].shift(1))).astype(int)
            df['macd_bearish_cross'] = ((df['_macd_line'] < df['_macd_signal']) & 
                                       (df['_macd_line'].shift(1) >= df['_macd_signal'].shift(1))).astype(int)
            
            # MACD histogram
            if '_macd_histogram' in df.columns:
                df['macd_histogram_positive'] = (df['_macd_histogram'] > 0).astype(int)
                df['macd_histogram_negative'] = (df['_macd_histogram'] < 0).astype(int)
                df['macd_histogram_increasing'] = (df['_macd_histogram'] > df['_macd_histogram'].shift(1)).astype(int)
                df['macd_histogram_decreasing'] = (df['_macd_histogram'] < df['_macd_histogram'].shift(1)).astype(int)
            
            # MACD zero line
            df['macd_above_zero'] = (df['_macd_line'] > 0).astype(int)
            df['macd_below_zero'] = (df['_macd_line'] < 0).astype(int)
        
        # === Stochastic Features ===
        if '_stoch_k' in df.columns and '_stoch_d' in df.columns:
            stoch_k = df['_stoch_k']
            stoch_d = df['_stoch_d']
            
            # Classic levels
            df['stoch_oversold'] = (stoch_k < 20).astype(int)
            df['stoch_overbought'] = (stoch_k > 80).astype(int)
            df['stoch_extreme_oversold'] = (stoch_k < 10).astype(int)
            df['stoch_extreme_overbought'] = (stoch_k > 90).astype(int)
            
            # Stochastic crossovers
            df['stoch_bullish_cross'] = ((stoch_k > stoch_d) & (stoch_k.shift(1) <= stoch_d.shift(1))).astype(int)
            df['stoch_bearish_cross'] = ((stoch_k < stoch_d) & (stoch_k.shift(1) >= stoch_d.shift(1))).astype(int)
            
            # Stochastic momentum
            df['stoch_rising'] = (stoch_k > stoch_k.shift(1)).astype(int)
            df['stoch_falling'] = (stoch_k < stoch_k.shift(1)).astype(int)
        
        # === Williams %R Features ===
        if '_williams_r' in df.columns:
            wr = df['_williams_r']
            df['williams_oversold'] = (wr < -80).astype(int)
            df['williams_overbought'] = (wr > -20).astype(int)
            df['williams_extreme_oversold'] = (wr < -90).astype(int)
            df['williams_extreme_overbought'] = (wr > -10).astype(int)
        
        # === CCI Features ===
        if '_cci' in df.columns:
            cci = df['_cci']
            df['cci_oversold'] = (cci < -100).astype(int)
            df['cci_overbought'] = (cci > 100).astype(int)
            df['cci_extreme_oversold'] = (cci < -200).astype(int)
            df['cci_extreme_overbought'] = (cci > 200).astype(int)
            df['cci_neutral'] = ((cci >= -100) & (cci <= 100)).astype(int)
        
        # === MFI Features ===
        if '_mfi' in df.columns:
            mfi = df['_mfi']
            df['mfi_oversold'] = (mfi < 20).astype(int)
            df['mfi_overbought'] = (mfi > 80).astype(int)
            df['mfi_extreme_oversold'] = (mfi < 10).astype(int)
            df['mfi_extreme_overbought'] = (mfi > 90).astype(int)
        
        # === Momentum Convergence/Divergence ===
        # Multiple indicators confirming direction
        momentum_bullish_indicators = []
        momentum_bearish_indicators = []
        
        if 'rsi_14_rising' in df.columns:
            momentum_bullish_indicators.append(df['rsi_14_rising'])
            momentum_bearish_indicators.append(df['rsi_14_falling'])
        
        if 'macd_bullish' in df.columns:
            momentum_bullish_indicators.append(df['macd_bullish'])
            momentum_bearish_indicators.append(df['macd_bearish'])
        
        if 'stoch_rising' in df.columns:
            momentum_bullish_indicators.append(df['stoch_rising'])
            momentum_bearish_indicators.append(df['stoch_falling'])
        
        if momentum_bullish_indicators:
            momentum_bullish_score = pd.concat(momentum_bullish_indicators, axis=1).sum(axis=1)
            momentum_bearish_score = pd.concat(momentum_bearish_indicators, axis=1).sum(axis=1)
            
            df['momentum_strong_bullish'] = (momentum_bullish_score >= len(momentum_bullish_indicators) - 1).astype(int)
            df['momentum_strong_bearish'] = (momentum_bearish_score >= len(momentum_bearish_indicators) - 1).astype(int)
            df['momentum_mixed'] = ((momentum_bullish_score > 0) & (momentum_bearish_score > 0)).astype(int)
        
        return df
    
    def _calculate_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volatility-based categorical features"""
        
        # === ATR Features ===
        if '_atr' in df.columns:
            atr = df['_atr']
            atr_normalized = atr / df['close']
            
            # Volatility regimes
            atr_percentile = atr_normalized.rolling(100).rank(pct=True)
            df['volatility_low'] = (atr_percentile < 0.25).astype(int)
            df['volatility_normal'] = ((atr_percentile >= 0.25) & (atr_percentile <= 0.75)).astype(int)
            df['volatility_high'] = (atr_percentile > 0.75).astype(int)
            df['volatility_extreme'] = (atr_percentile > 0.9).astype(int)
            
            # Volatility trend
            atr_change = atr.diff()
            df['volatility_expanding'] = (atr_change > 0).astype(int)
            df['volatility_contracting'] = (atr_change < 0).astype(int)
        
        # === Range Features ===
        if '_true_range' in df.columns:
            tr = df['_true_range']
            tr_normalized = tr / df['close']
            
            # True range categories
            tr_percentile = tr_normalized.rolling(50).rank(pct=True)
            df['range_small'] = (tr_percentile < 0.33).astype(int)
            df['range_normal'] = ((tr_percentile >= 0.33) & (tr_percentile <= 0.66)).astype(int)
            df['range_large'] = (tr_percentile > 0.66).astype(int)
            df['range_extreme'] = (tr_percentile > 0.9).astype(int)
        
        # === Price Movement Features ===
        # Based on price changes
        if '_price_change_1' in df.columns:
            pc1 = df['_price_change_1']
            pc1_abs = abs(pc1)
            
            # Movement magnitude
            pc1_percentile = pc1_abs.rolling(50).rank(pct=True)
            df['movement_small'] = (pc1_percentile < 0.33).astype(int)
            df['movement_normal'] = ((pc1_percentile >= 0.33) & (pc1_percentile <= 0.66)).astype(int)
            df['movement_large'] = (pc1_percentile > 0.66).astype(int)
            
            # Movement direction consistency
            df['consistent_upward_movement'] = (pc1.rolling(5).apply(lambda x: (x > 0).sum()) >= 4).astype(int)
            df['consistent_downward_movement'] = (pc1.rolling(5).apply(lambda x: (x < 0).sum()) >= 4).astype(int)
        
        return df
    
    def _calculate_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volume-based categorical features"""
        
        # === Volume Surge Detection ===
        volume_ma = df['volume'].rolling(20).mean()
        volume_std = df['volume'].rolling(20).std()
        
        df['volume_normal'] = (df['volume'] <= volume_ma + volume_std).astype(int)
        df['volume_above_average'] = ((df['volume'] > volume_ma) & (df['volume'] <= volume_ma + 2 * volume_std)).astype(int)
        df['volume_surge'] = (df['volume'] > volume_ma + 2 * volume_std).astype(int)
        df['volume_extreme_surge'] = (df['volume'] > volume_ma + 3 * volume_std).astype(int)
        df['volume_low'] = (df['volume'] < volume_ma - volume_std).astype(int)
        
        # === Volume Trend ===
        if '_volume_change_1' in df.columns:
            vol_change = df['_volume_change_1']
            df['volume_increasing'] = (vol_change > 0).astype(int)
            df['volume_decreasing'] = (vol_change < 0).astype(int)
            df['volume_stable'] = (abs(vol_change) < 0.1).astype(int)
        
        # === Volume Price Confirmation ===
        if '_price_change_1' in df.columns:
            price_up = (df['_price_change_1'] > 0).astype(int)
            volume_up = (df['volume'] > volume_ma).astype(int)
            
            df['volume_price_confirmed_up'] = (price_up & volume_up).astype(int)
            df['volume_price_confirmed_down'] = ((1 - price_up) & volume_up).astype(int)
            df['volume_price_unconfirmed'] = (price_up != volume_up).astype(int)
        
        # === OBV Features ===
        if '_obv' in df.columns:
            obv = df['_obv']
            obv_ma = obv.rolling(20).mean()
            
            df['obv_rising'] = (obv > obv_ma).astype(int)
            df['obv_falling'] = (obv < obv_ma).astype(int)
            df['obv_momentum_up'] = (obv.diff() > 0).astype(int)
            df['obv_momentum_down'] = (obv.diff() < 0).astype(int)
        
        return df
    
    def _calculate_support_resistance_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate support/resistance categorical features"""
        
        # === Dynamic Support/Resistance ===
        for period in [20, 50]:
            resistance = df['high'].rolling(period).max()
            support = df['low'].rolling(period).min()
            
            # Distance to levels
            dist_to_resistance = (resistance - df['close']) / df['close']
            dist_to_support = (df['close'] - support) / df['close']
            
            # Proximity categories
            df[f'near_resistance_{period}'] = (dist_to_resistance < 0.01).astype(int)  # Within 1%
            df[f'at_resistance_{period}'] = (dist_to_resistance < 0.005).astype(int)   # Within 0.5%
            df[f'near_support_{period}'] = (dist_to_support < 0.01).astype(int)
            df[f'at_support_{period}'] = (dist_to_support < 0.005).astype(int)
            
            # Position in range
            range_position = (df['close'] - support) / (resistance - support)
            df[f'in_lower_range_{period}'] = (range_position < 0.33).astype(int)
            df[f'in_middle_range_{period}'] = ((range_position >= 0.33) & (range_position <= 0.66)).astype(int)
            df[f'in_upper_range_{period}'] = (range_position > 0.66).astype(int)
            
            # Breakouts
            df[f'breakout_above_resistance_{period}'] = ((df['close'] > resistance) & 
                                                        (df['close'].shift(1) <= resistance.shift(1))).astype(int)
            df[f'breakdown_below_support_{period}'] = ((df['close'] < support) & 
                                                      (df['close'].shift(1) >= support.shift(1))).astype(int)
        
        return df
    
    def _calculate_candlestick_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate candlestick pattern categorical features"""
        
        # === Basic Candle Characteristics ===
        body_size = abs(df['close'] - df['open'])
        upper_shadow = df['high'] - df[['open', 'close']].max(axis=1)
        lower_shadow = df[['open', 'close']].min(axis=1) - df['low']
        total_range = df['high'] - df['low']
        
        # Body size categories
        body_ratio = body_size / total_range
        df['small_body'] = (body_ratio < 0.3).astype(int)
        df['medium_body'] = ((body_ratio >= 0.3) & (body_ratio <= 0.7)).astype(int)
        df['large_body'] = (body_ratio > 0.7).astype(int)
        
        # Shadow categories
        upper_shadow_ratio = upper_shadow / total_range
        lower_shadow_ratio = lower_shadow / total_range
        
        df['long_upper_shadow'] = (upper_shadow_ratio > 0.4).astype(int)
        df['long_lower_shadow'] = (lower_shadow_ratio > 0.4).astype(int)
        df['no_upper_shadow'] = (upper_shadow_ratio < 0.1).astype(int)
        df['no_lower_shadow'] = (lower_shadow_ratio < 0.1).astype(int)
        
        # Candle direction
        df['bullish_candle'] = (df['close'] > df['open']).astype(int)
        df['bearish_candle'] = (df['close'] < df['open']).astype(int)
        df['doji_candle'] = (abs(df['close'] - df['open']) / total_range < 0.1).astype(int)
        
        # === Specific Patterns ===
        # Hammer/Hanging Man
        df['hammer_pattern'] = ((body_ratio < 0.3) & (lower_shadow_ratio > 0.6) & (upper_shadow_ratio < 0.2)).astype(int)
        df['inverted_hammer_pattern'] = ((body_ratio < 0.3) & (upper_shadow_ratio > 0.6) & (lower_shadow_ratio < 0.2)).astype(int)
        
        # Shooting Star
        df['shooting_star_pattern'] = ((df['bearish_candle'] == 1) & (upper_shadow_ratio > 0.6) & (lower_shadow_ratio < 0.2)).astype(int)
        
        # Marubozu
        df['bullish_marubozu'] = ((df['bullish_candle'] == 1) & (upper_shadow_ratio < 0.05) & (lower_shadow_ratio < 0.05)).astype(int)
        df['bearish_marubozu'] = ((df['bearish_candle'] == 1) & (upper_shadow_ratio < 0.05) & (lower_shadow_ratio < 0.05)).astype(int)
        
        # Spinning Top
        df['spinning_top'] = ((body_ratio < 0.3) & (upper_shadow_ratio > 0.3) & (lower_shadow_ratio > 0.3)).astype(int)
        
        # === Multi-Candle Patterns ===
        # Engulfing patterns
        df['bullish_engulfing'] = ((df['bullish_candle'] == 1) & 
                                  (df['bearish_candle'].shift(1) == 1) &
                                  (df['open'] < df['close'].shift(1)) &
                                  (df['close'] > df['open'].shift(1))).astype(int)
        
        df['bearish_engulfing'] = ((df['bearish_candle'] == 1) & 
                                  (df['bullish_candle'].shift(1) == 1) &
                                  (df['open'] > df['close'].shift(1)) &
                                  (df['close'] < df['open'].shift(1))).astype(int)
        
        # Inside/Outside bars
        df['inside_bar'] = ((df['high'] <= df['high'].shift(1)) & (df['low'] >= df['low'].shift(1))).astype(int)
        df['outside_bar'] = ((df['high'] >= df['high'].shift(1)) & (df['low'] <= df['low'].shift(1))).astype(int)
        
        # === Candle Momentum ===
        # Consecutive candles
        df['consecutive_bullish_2'] = ((df['bullish_candle'] == 1) & (df['bullish_candle'].shift(1) == 1)).astype(int)
        df['consecutive_bearish_2'] = ((df['bearish_candle'] == 1) & (df['bearish_candle'].shift(1) == 1)).astype(int)
        df['consecutive_bullish_3'] = (df['bullish_candle'].rolling(3).sum() == 3).astype(int)
        df['consecutive_bearish_3'] = (df['bearish_candle'].rolling(3).sum() == 3).astype(int)


                # === Enhanced Candle Size Analysis ===
        # Total candle range (high to low)
        candle_range = df['high'] - df['low']
        candle_range_normalized = candle_range / df['close']

        # Historical candle size analysis
        candle_range_percentile = candle_range_normalized.rolling(100).rank(pct=True)

        df['large_candle_range'] = (candle_range_percentile > 0.8).astype(int)  # Top 20% largest candles
        df['extreme_candle_range'] = (candle_range_percentile > 0.95).astype(int)  # Top 5% largest candles

        # Body vs total range efficiency
        body_to_range_ratio = body_size / candle_range
        df['efficient_candle'] = (body_to_range_ratio > 0.7).astype(int)  # Body takes >70% of range
        df['inefficient_candle'] = (body_to_range_ratio < 0.3).astype(int)  # Body takes <30% of range

        # Wick dominance features
        total_wick_size = upper_shadow + lower_shadow
        wick_to_range_ratio = total_wick_size / candle_range
        df['wick_dominated_candle'] = (wick_to_range_ratio > 0.6).astype(int)  # Wicks >60% of range
        
        return df
    
    def _calculate_bollinger_band_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Bollinger Band categorical features"""
        
        if '_bb_upper' in df.columns and '_bb_lower' in df.columns and '_bb_middle' in df.columns:
            bb_upper = df['_bb_upper']
            bb_lower = df['_bb_lower']
            bb_middle = df['_bb_middle']
            
            # === Position Features ===
            df['above_bb_upper'] = (df['close'] > bb_upper).astype(int)
            df['below_bb_lower'] = (df['close'] < bb_lower).astype(int)
            df['between_bb_bands'] = ((df['close'] >= bb_lower) & (df['close'] <= bb_upper)).astype(int)
            df['above_bb_middle'] = (df['close'] > bb_middle).astype(int)
            df['below_bb_middle'] = (df['close'] < bb_middle).astype(int)
            
            # === Band Width Features ===
            bb_width = (bb_upper - bb_lower) / bb_middle
            bb_width_percentile = bb_width.rolling(50).rank(pct=True)
            
            df['bb_squeeze'] = (bb_width_percentile < 0.2).astype(int)
            df['bb_expansion'] = (bb_width_percentile > 0.8).astype(int)
            df['bb_normal_width'] = ((bb_width_percentile >= 0.2) & (bb_width_percentile <= 0.8)).astype(int)
            
            # === Touch and Bounce Features ===
            tolerance = 0.001  # 0.1% tolerance
            df['touching_bb_upper'] = (abs(df['high'] - bb_upper) / bb_upper < tolerance).astype(int)
            df['touching_bb_lower'] = (abs(df['low'] - bb_lower) / bb_lower < tolerance).astype(int)
            
            # BB reversals
            df['bb_reversal_from_upper'] = ((df['close'] < bb_upper) & (df['close'].shift(1) >= bb_upper)).astype(int)
            df['bb_reversal_from_lower'] = ((df['close'] > bb_lower) & (df['close'].shift(1) <= bb_lower)).astype(int)
            
            # === %B Features ===
            bb_percent = (df['close'] - bb_lower) / (bb_upper - bb_lower)
            df['bb_percent_oversold'] = (bb_percent < 0.2).astype(int)
            df['bb_percent_overbought'] = (bb_percent > 0.8).astype(int)
            df['bb_percent_neutral'] = ((bb_percent >= 0.4) & (bb_percent <= 0.6)).astype(int)
        
        return df
    
    def _calculate_fibonacci_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Fibonacci-based categorical features"""
        
        # === Fibonacci Retracements ===
        for period in [20, 50]:
            swing_high = df['high'].rolling(period).max()
            swing_low = df['low'].rolling(period).min()
            swing_range = swing_high - swing_low
            
            # Key Fibonacci levels
            fib_236 = swing_high - (swing_range * 0.236)
            fib_382 = swing_high - (swing_range * 0.382)
            fib_500 = swing_high - (swing_range * 0.5)
            fib_618 = swing_high - (swing_range * 0.618)
            fib_786 = swing_high - (swing_range * 0.786)
            
            tolerance = 0.005  # 0.5% tolerance
            
            # Near Fibonacci levels
            df[f'near_fib_236_{period}'] = (abs(df['close'] - fib_236) / df['close'] < tolerance).astype(int)
            df[f'near_fib_382_{period}'] = (abs(df['close'] - fib_382) / df['close'] < tolerance).astype(int)
            df[f'near_fib_500_{period}'] = (abs(df['close'] - fib_500) / df['close'] < tolerance).astype(int)
            df[f'near_fib_618_{period}'] = (abs(df['close'] - fib_618) / df['close'] < tolerance).astype(int)
            df[f'near_fib_786_{period}'] = (abs(df['close'] - fib_786) / df['close'] < tolerance).astype(int)
            
            # Fibonacci zones
            df[f'in_fib_golden_zone_{period}'] = ((df['close'] >= fib_618) & (df['close'] <= fib_786)).astype(int)
            df[f'above_fib_618_{period}'] = (df['close'] > fib_618).astype(int)
            df[f'below_fib_382_{period}'] = (df['close'] < fib_382).astype(int)
        
        return df
    
    def _calculate_market_structure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate market structure categorical features"""
        
        # === Higher Highs and Lower Lows ===
        for period in [10, 20]:
            # Higher highs/lows
            df[f'making_higher_high_{period}'] = (df['high'] > df['high'].rolling(period).max().shift(1)).astype(int)
            df[f'making_lower_low_{period}'] = (df['low'] < df['low'].rolling(period).min().shift(1)).astype(int)
            df[f'making_higher_low_{period}'] = ((df['low'] > df['low'].rolling(period).min().shift(1)) & 
                                               (df['low'].shift(1) == df['low'].rolling(period).min().shift(1))).astype(int)
            df[f'making_lower_high_{period}'] = ((df['high'] < df['high'].rolling(period).max().shift(1)) & 
                                               (df['high'].shift(1) == df['high'].rolling(period).max().shift(1))).astype(int)
        
        # === Structure Breaks ===
        for period in [20, 50]:
            prev_high = df['high'].rolling(period).max().shift(1)
            prev_low = df['low'].rolling(period).min().shift(1)
            
            df[f'structure_break_bullish_{period}'] = ((df['close'] > prev_high) & 
                                                     (df['close'].shift(1) <= prev_high.shift(1))).astype(int)
            df[f'structure_break_bearish_{period}'] = ((df['close'] < prev_low) & 
                                                     (df['close'].shift(1) >= prev_low.shift(1))).astype(int)
        
        # # === Swing Points ===
        # # Simplified swing identification
        # df['local_high'] = ((df['high'] > df['high'].shift(1)) & 
        #                    (df['high'] > df['high'].shift(-1))).astype(int)
        # df['local_low'] = ((df['low'] < df['low'].shift(1)) & 
        #                   (df['low'] < df['low'].shift(-1))).astype(int)

        # === Swing Points (No Look-Ahead Bias) ===
        # Method 1: Use only completed historical candles
        df['local_high'] = ((df['high'] > df['high'].shift(1)) & 
                        (df['high'] > df['high'].shift(2)) &
                        (df['high'].shift(1) > df['high'].shift(2))).astype(int)

        df['local_low'] = ((df['low'] < df['low'].shift(1)) & 
                        (df['low'] < df['low'].shift(2)) &
                        (df['low'].shift(1) < df['low'].shift(2))).astype(int)

        # Method 2: Delayed confirmation (more practical)
        # Confirm swing points only after they're validated by subsequent candles
        df['local_high_confirmed'] = ((df['high'].shift(1) > df['high'].shift(2)) & 
                                    (df['high'].shift(1) > df['high']) &
                                    (df['high'].shift(1) > df['high'].shift(3))).astype(int)

        df['local_low_confirmed'] = ((df['low'].shift(1) < df['low'].shift(2)) & 
                                (df['low'].shift(1) < df['low']) &
                                (df['low'].shift(1) < df['low'].shift(3))).astype(int)
        
        return df
    
    def _calculate_divergence_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate divergence categorical features"""
        
        # === RSI Divergence ===
        if '_rsi_14' in df.columns:
            rsi = df['_rsi_14']
            
            # Simplified divergence detection
            for period in [10, 20]:
                # Bullish divergence: price making lower lows, RSI making higher lows
                price_lower_low = (df['close'] < df['close'].shift(period))
                rsi_higher_low = (rsi > rsi.shift(period))
                df[f'rsi_bullish_divergence_{period}'] = (price_lower_low & rsi_higher_low).astype(int)
                
                # Bearish divergence: price making higher highs, RSI making lower highs
                price_higher_high = (df['close'] > df['close'].shift(period))
                rsi_lower_high = (rsi < rsi.shift(period))
                df[f'rsi_bearish_divergence_{period}'] = (price_higher_high & rsi_lower_high).astype(int)
        
        # === MACD Divergence ===
        if '_macd_line' in df.columns:
            macd = df['_macd_line']
            
            for period in [10, 20]:
                # Bullish divergence
                price_lower_low = (df['close'] < df['close'].shift(period))
                macd_higher_low = (macd > macd.shift(period))
                df[f'macd_bullish_divergence_{period}'] = (price_lower_low & macd_higher_low).astype(int)
                
                # Bearish divergence
                price_higher_high = (df['close'] > df['close'].shift(period))
                macd_lower_high = (macd < macd.shift(period))
                df[f'macd_bearish_divergence_{period}'] = (price_higher_high & macd_lower_high).astype(int)
        
        return df
    
    def _calculate_session_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate session-based categorical features"""
        
        # Create time-based features if index is datetime
        if hasattr(df.index, 'hour') or 'datetime' in df.columns:
            if 'datetime' in df.columns:
                dt_series = pd.to_datetime(df['datetime'])
            else:
                dt_series = df.index
            
            # Extract time components
            hour = dt_series.hour
            day_of_week = dt_series.dayofweek
            
            # Trading sessions (assuming UTC time)
            df['asian_session'] = ((hour >= 23) | (hour < 8)).astype(int)
            df['london_session'] = ((hour >= 8) & (hour < 16)).astype(int)
            df['us_session'] = ((hour >= 13) & (hour < 21)).astype(int)
            df['overlap_session'] = ((hour >= 13) & (hour < 16)).astype(int)
            
            # Day of week
            df['monday'] = (day_of_week == 0).astype(int)
            df['tuesday'] = (day_of_week == 1).astype(int)
            df['wednesday'] = (day_of_week == 2).astype(int)
            df['thursday'] = (day_of_week == 3).astype(int)
            df['friday'] = (day_of_week == 4).astype(int)
            
            # Session characteristics
            df['high_liquidity_time'] = (df['overlap_session'] | df['london_session']).astype(int)
            df['low_liquidity_time'] = df['asian_session'].astype(int)
        
        return df
    
    def _calculate_multi_timeframe_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate multi-timeframe categorical features"""
        
        # === Higher Timeframe Trend ===
        # Simulate higher timeframe by using longer periods
        htf_periods = [60, 120, 240]  # Simulate 5H, 10H, 20H timeframes for 5min data
        
        for period in htf_periods:
            if len(df) >= period:
                # Higher timeframe EMA trend
                htf_ema_fast = df['close'].rolling(int(period/4)).mean()
                htf_ema_slow = df['close'].rolling(period).mean()
                
                df[f'htf_trend_bullish_{period}'] = (htf_ema_fast > htf_ema_slow).astype(int)
                df[f'htf_trend_bearish_{period}'] = (htf_ema_fast < htf_ema_slow).astype(int)
                
                # Higher timeframe momentum
                htf_momentum = df['close'].pct_change(period)
                df[f'htf_momentum_positive_{period}'] = (htf_momentum > 0).astype(int)
                df[f'htf_momentum_negative_{period}'] = (htf_momentum < 0).astype(int)
                df[f'htf_momentum_strong_{period}'] = (abs(htf_momentum) > htf_momentum.rolling(period).std()).astype(int)
        
        return df

    def _calculate_enhanced_multi_timeframe_alignment(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate enhanced multi-timeframe alignment features using resampling"""
        
        # Resample to higher timeframes (1H and 4H)
        df_1h = self._resample_to_higher_timeframe(df, '1H')
        df_4h = self._resample_to_higher_timeframe(df, '4H')
        df_1d = self._resample_to_higher_timeframe(df, '1D')
        
        # === 1 Hour Timeframe Alignment ===
        if len(df_1h) > 50:
            # Calculate EMAs for 1H
            ema_21_1h = df_1h['close'].ewm(span=21).mean()
            ema_50_1h = df_1h['close'].ewm(span=50).mean()
            
            # Trend direction on 1H
            trend_1h_bullish = (ema_21_1h > ema_50_1h)
            trend_1h_bearish = (ema_21_1h < ema_50_1h)
            
            # Price position relative to 1H EMAs
            price_above_1h_ema = (df_1h['close'] > ema_21_1h)
            price_below_1h_ema = (df_1h['close'] < ema_21_1h)
            
            # Forward fill to 15min timeframe
            df['htf_1h_trend_bullish'] = self._forward_fill_htf_to_ltf(trend_1h_bullish, df.index, df_1h.index)
            df['htf_1h_trend_bearish'] = self._forward_fill_htf_to_ltf(trend_1h_bearish, df.index, df_1h.index)
            df['htf_1h_price_above_ema'] = self._forward_fill_htf_to_ltf(price_above_1h_ema, df.index, df_1h.index)
            df['htf_1h_price_below_ema'] = self._forward_fill_htf_to_ltf(price_below_1h_ema, df.index, df_1h.index)
            
            # 1H momentum
            rsi_1h = self._calculate_rsi_simple(df_1h['close'], 14)
            momentum_1h_bullish = (rsi_1h > 50)
            momentum_1h_bearish = (rsi_1h < 50)
            
            df['htf_1h_momentum_bullish'] = self._forward_fill_htf_to_ltf(momentum_1h_bullish, df.index, df_1h.index)
            df['htf_1h_momentum_bearish'] = self._forward_fill_htf_to_ltf(momentum_1h_bearish, df.index, df_1h.index)
        
        # === 4 Hour Timeframe Alignment ===
        if len(df_4h) > 20:
            # Calculate EMAs for 4H
            ema_21_4h = df_4h['close'].ewm(span=21).mean()
            ema_50_4h = df_4h['close'].ewm(span=50).mean()
            
            # Trend direction on 4H
            trend_4h_bullish = (ema_21_4h > ema_50_4h)
            trend_4h_bearish = (ema_21_4h < ema_50_4h)
            
            # Price position relative to 4H EMAs
            price_above_4h_ema = (df_4h['close'] > ema_21_4h)
            price_below_4h_ema = (df_4h['close'] < ema_21_4h)
            
            # Forward fill to 15min timeframe
            df['htf_4h_trend_bullish'] = self._forward_fill_htf_to_ltf(trend_4h_bullish, df.index, df_4h.index)
            df['htf_4h_trend_bearish'] = self._forward_fill_htf_to_ltf(trend_4h_bearish, df.index, df_4h.index)
            df['htf_4h_price_above_ema'] = self._forward_fill_htf_to_ltf(price_above_4h_ema, df.index, df_4h.index)
            df['htf_4h_price_below_ema'] = self._forward_fill_htf_to_ltf(price_below_4h_ema, df.index, df_4h.index)
            
            # 4H momentum
            rsi_4h = self._calculate_rsi_simple(df_4h['close'], 14)
            momentum_4h_bullish = (rsi_4h > 50)
            momentum_4h_bearish = (rsi_4h < 50)
            
            df['htf_4h_momentum_bullish'] = self._forward_fill_htf_to_ltf(momentum_4h_bullish, df.index, df_4h.index)
            df['htf_4h_momentum_bearish'] = self._forward_fill_htf_to_ltf(momentum_4h_bearish, df.index, df_4h.index)
        
        # === 1 Day Timeframe (just 2 features) ===
        if len(df_1d) > 10:
            # Daily trend (simple price vs 20 EMA)
            ema_20_1d = df_1d['close'].ewm(span=20).mean()
            trend_1d_bullish = (df_1d['close'] > ema_20_1d)
            
            df['htf_1d_trend_bullish'] = self._forward_fill_htf_to_ltf(trend_1d_bullish, df.index, df_1d.index)
            df['htf_1d_trend_bearish'] = self._forward_fill_htf_to_ltf(~trend_1d_bullish, df.index, df_1d.index)
        
        # === Multi-Timeframe Alignment ===
        # All timeframes aligned bullish
        bullish_cols = [col for col in df.columns if 'htf' in col and 'bullish' in col and 'trend' in col]
        if len(bullish_cols) >= 2:
            df['mtf_all_bullish'] = df[bullish_cols].all(axis=1).astype(int)
            df['mtf_all_bearish'] = df[[col.replace('bullish', 'bearish') for col in bullish_cols]].all(axis=1).astype(int)
            df['mtf_mixed_signals'] = (~df['mtf_all_bullish'] & ~df['mtf_all_bearish']).astype(int)
        
        # HTF trend vs LTF momentum alignment
        if 'htf_4h_trend_bullish' in df.columns and 'momentum_regime_bullish' in df.columns:
            df['htf_trend_ltf_momentum_aligned_bull'] = (df['htf_4h_trend_bullish'] & df['momentum_regime_bullish']).astype(int)
            df['htf_trend_ltf_momentum_aligned_bear'] = (df['htf_4h_trend_bearish'] & df['momentum_regime_bearish']).astype(int)
            df['htf_trend_ltf_momentum_diverged'] = ((df['htf_4h_trend_bullish'] & df['momentum_regime_bearish']) | 
                                                (df['htf_4h_trend_bearish'] & df['momentum_regime_bullish'])).astype(int)


        # Add after existing MTF calculations:

        # === Trend Strength Alignment ===
        # Calculate trend strength on multiple timeframes
        if len(df_1h) > 20 and len(df_4h) > 10:
            # 1H trend strength
            price_change_1h = df_1h['close'].pct_change(5)  # 5 period change on 1H = 5H change
            trend_strength_1h = abs(price_change_1h).rolling(10).rank(pct=True)
            strong_trend_1h = (trend_strength_1h > 0.7)
            
            # 4H trend strength  
            price_change_4h = df_4h['close'].pct_change(3)  # 3 period change on 4H = 12H change
            trend_strength_4h = abs(price_change_4h).rolling(5).rank(pct=True)
            strong_trend_4h = (trend_strength_4h > 0.7)
            
            # Forward fill to current timeframe
            df['htf_1h_strong_trend'] = self._forward_fill_htf_to_ltf(strong_trend_1h, df.index, df_1h.index)
            df['htf_4h_strong_trend'] = self._forward_fill_htf_to_ltf(strong_trend_4h, df.index, df_4h.index)
            
            # === Momentum Alignment ===
            # When both higher timeframes show momentum in same direction
            bull_momentum_1h = (df_1h['close'] > df_1h['close'].ewm(span=21).mean())
            bear_momentum_1h = (df_1h['close'] < df_1h['close'].ewm(span=21).mean())
            
            bull_momentum_4h = (df_4h['close'] > df_4h['close'].ewm(span=21).mean())  
            bear_momentum_4h = (df_4h['close'] < df_4h['close'].ewm(span=21).mean())
            
            bull_1h_filled = self._forward_fill_htf_to_ltf(bull_momentum_1h, df.index, df_1h.index)
            bull_4h_filled = self._forward_fill_htf_to_ltf(bull_momentum_4h, df.index, df_4h.index)
            bear_1h_filled = self._forward_fill_htf_to_ltf(bear_momentum_1h, df.index, df_1h.index)
            bear_4h_filled = self._forward_fill_htf_to_ltf(bear_momentum_4h, df.index, df_4h.index)
            
            df['mtf_momentum_aligned_bull'] = (bull_1h_filled & bull_4h_filled).astype(int)
            df['mtf_momentum_aligned_bear'] = (bear_1h_filled & bear_4h_filled).astype(int)
        
        return df
    

    def _calculate_retracement_strategy_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate features specific to retracement-based strategy"""
        
        # === Post-Large-Candle Behavior ===
        # Large opposite candle detection
        large_bull_candle = ((df['close'] > df['open']) & (df['large_candle_range'] == 1))
        large_bear_candle = ((df['close'] < df['open']) & (df['large_candle_range'] == 1))
        
        # Retracement after large candles (key for your strategy)
        post_large_bull = large_bull_candle.shift(1).rolling(3).sum() > 0
        post_large_bear = large_bear_candle.shift(1).rolling(3).sum() > 0
        
        current_retracement_after_bull = (df['close'] < df['close'].shift(1)) & post_large_bull
        current_retracement_after_bear = (df['close'] > df['close'].shift(1)) & post_large_bear
        
        df['healthy_retracement_after_bull_candle'] = (current_retracement_after_bull & 
                                                    (abs(df['close'].pct_change(1)) < 0.01)).astype(int)  # <1% retracement
        df['healthy_retracement_after_bear_candle'] = (current_retracement_after_bear & 
                                                    (abs(df['close'].pct_change(1)) < 0.01)).astype(int)
        
        # === Momentum Persistence ===
        # Check if momentum continues after large candles
        bull_momentum_continues = large_bull_candle.shift(1) & (df['close'] > df['close'].shift(1))
        bear_momentum_continues = large_bear_candle.shift(1) & (df['close'] < df['close'].shift(1))
        
        df['momentum_continuation_bull'] = bull_momentum_continues.astype(int)
        df['momentum_continuation_bear'] = bear_momentum_continues.astype(int)
        
        return df

    def _calculate_price_action_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate price action categorical features"""
        
        # === Gap Features ===
        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)
        
        df['gap_up'] = (df['low'] > prev_high).astype(int)
        df['gap_down'] = (df['high'] < prev_low).astype(int)
        df['no_gap'] = ((df['low'] <= prev_high) & (df['high'] >= prev_low)).astype(int)
        
        # Gap size categories
        gap_size = np.where(df['gap_up'] == 1, df['low'] - prev_high,
                           np.where(df['gap_down'] == 1, prev_low - df['high'], 0))
        gap_size_normalized = abs(gap_size) / df['close']
        
        df['small_gap'] = ((df['gap_up'] | df['gap_down']) & (gap_size_normalized < 0.005)).astype(int)
        df['medium_gap'] = ((df['gap_up'] | df['gap_down']) & 
                           (gap_size_normalized >= 0.005) & (gap_size_normalized < 0.01)).astype(int)
        df['large_gap'] = ((df['gap_up'] | df['gap_down']) & (gap_size_normalized >= 0.01)).astype(int)
        
        # === Price Momentum Features ===
        for period in [3, 5, 10]:
            price_change = df['close'].pct_change(period)
            price_change_abs = abs(price_change)
            
            # Momentum strength
            momentum_threshold = price_change_abs.rolling(50).quantile(0.75)
            df[f'strong_momentum_{period}'] = (price_change_abs > momentum_threshold).astype(int)
            df[f'weak_momentum_{period}'] = (price_change_abs < price_change_abs.rolling(50).quantile(0.25)).astype(int)
            
            # Momentum direction
            df[f'positive_momentum_{period}'] = (price_change > 0).astype(int)
            df[f'negative_momentum_{period}'] = (price_change < 0).astype(int)
        
        # === Wick Analysis ===
        body_size = abs(df['close'] - df['open'])
        upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
        lower_wick = df[['open', 'close']].min(axis=1) - df['low']
        
        # Wick rejection features
        df['upper_wick_rejection'] = ((upper_wick > 2 * body_size) & (df['close'] < df['open'])).astype(int)
        df['lower_wick_rejection'] = ((lower_wick > 2 * body_size) & (df['close'] > df['open'])).astype(int)
        
        return df
    

    def _calculate_advanced_smc_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate advanced Smart Money Concepts features"""
        
        # === Displacement Detection ===
        # Strong directional moves (displacement)
        price_change_3 = df['close'].pct_change(3)
        price_change_5 = df['close'].pct_change(5)
        
        # Volume surge with displacement
        volume_ma = df['volume'].rolling(20).mean()
        volume_surge = df['volume'] > volume_ma * 1.5
        
        displacement_threshold = abs(price_change_3).rolling(50).quantile(0.85)
        df['bullish_displacement'] = ((price_change_3 > displacement_threshold) & volume_surge).astype(int)
        df['bearish_displacement'] = ((price_change_3 < -displacement_threshold) & volume_surge).astype(int)
        
        # === Retracement Pattern Analysis ===
        # After displacement, look for retracements (no lookahead)
        # Fix: Convert to boolean first, then use logical OR
        bull_disp_shifted = (df['bullish_displacement'].shift(1) == 1)
        bear_disp_shifted = (df['bearish_displacement'].shift(1) == 1)
        displacement_occurred = (bull_disp_shifted | bear_disp_shifted)
        
        # Shallow retracement after bullish displacement
        post_bull_displacement = (df['bullish_displacement'].shift(1).rolling(5).sum() > 0)
        current_retracement_bull = (df['close'] < df['close'].shift(1)) & post_bull_displacement
        df['shallow_bull_retracement'] = (current_retracement_bull & (abs(df['close'].pct_change(3)) < 0.005)).astype(int)
        
        # Shallow retracement after bearish displacement  
        post_bear_displacement = (df['bearish_displacement'].shift(1).rolling(5).sum() > 0)
        current_retracement_bear = (df['close'] > df['close'].shift(1)) & post_bear_displacement
        df['shallow_bear_retracement'] = (current_retracement_bear & (abs(df['close'].pct_change(3)) < 0.005)).astype(int)
        
        # === Consecutive Candle Analysis ===
        # Strong consecutive moves indicating institutional flow
        bullish_candles = (df['close'] > df['open']).astype(int)
        bearish_candles = (df['close'] < df['open']).astype(int)
        
        df['strong_bull_sequence'] = (bullish_candles.rolling(4).sum() >= 3).astype(int)  # 3 out of 4 bullish
        df['strong_bear_sequence'] = (bearish_candles.rolling(4).sum() >= 3).astype(int)  # 3 out of 4 bearish
        
        return df


    def _calculate_level_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate level interaction categorical features"""
        
        # === Round Number Levels ===
        # For XAUUSD, common round numbers
        round_levels = [1800, 1850, 1900, 1950, 2000, 2050, 2100, 2150,
        2200, 2250, 2300, 2350, 2400, 2450, 2500, 2550, 2600, 2650, 2700, 2750,
        2800, 2850, 2900, 2950, 3000, 3050, 3100, 3150, 
        3200, 3250, 3300, 3350, 3400, 3450, 3500, 3550, 3600, 3650, 3700,
        3750, 3800, 3850, 3900, 3950, 4000, 4050, 4100, 4150, 4200, 4250, 4300,
        4350, 4400, 4450, 4500, 4550, 4600, 4650, 4700, 4750, 4800, 4850, 4900, 4950, 5000]
        
        # Find closest round number
        closest_round = df['close'].apply(lambda x: min(round_levels, key=lambda level: abs(x - level)))
        distance_to_round = abs(df['close'] - closest_round) / df['close']
        
        df['near_round_number'] = (distance_to_round < 0.005).astype(int)  # Within 0.5%
        df['at_round_number'] = (distance_to_round < 0.001).astype(int)    # Within 0.1%
        
        # === Psychological Levels ===
        # Half levels (e.g., 1950.5, 2000.5)
        half_distance = abs(df['close'] % 50 - 25) / df['close']
        df['near_psychological_half'] = (half_distance < 0.002).astype(int)
        
        # Quarter levels
        quarter_distance = abs(df['close'] % 25 - 12.5) / df['close']
        df['near_psychological_quarter'] = (quarter_distance < 0.001).astype(int)
        
        return df
    
    def _resample_to_higher_timeframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample 15min data to higher timeframe"""
        try:
            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'datetime' in df.columns:
                    df_temp = df.copy()
                    df_temp.index = pd.to_datetime(df_temp['datetime'])
                else:
                    return pd.DataFrame()  # Return empty if no datetime info
            else:
                df_temp = df.copy()
            
            # Resample OHLCV data
            resampled = df_temp.resample(timeframe).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            return resampled
        except Exception as e:
            logger.warning(f"Error resampling to {timeframe}: {e}")
            return pd.DataFrame()

    def _forward_fill_htf_to_ltf(self, htf_series: pd.Series, ltf_index: pd.DatetimeIndex, htf_index: pd.DatetimeIndex) -> pd.Series:
        """Forward fill higher timeframe series to lower timeframe index"""
        try:
            # Create a series with HTF values at HTF timestamps
            htf_series_with_index = pd.Series(htf_series.values, index=htf_index)
            
            # Reindex to LTF and forward fill
            result = htf_series_with_index.reindex(ltf_index, method='ffill').fillna(0).astype(int)
            
            return result
        except Exception as e:
            logger.warning(f"Error forward filling HTF to LTF: {e}")
            return pd.Series(0, index=ltf_index, dtype=int)

    def _calculate_rsi_simple(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Simple RSI calculation"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception as e:
            logger.warning(f"Error calculating RSI: {e}")
            return pd.Series(50, index=prices.index)  # Return neutral RSI

    def _calculate_momentum_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate momentum regime categorical features"""
        
        # === Composite Momentum Score ===
        momentum_indicators = []
        
        if 'rsi_14_rising' in df.columns:
            momentum_indicators.append(df['rsi_14_rising'])
        if 'macd_bullish' in df.columns:
            momentum_indicators.append(df['macd_bullish'])
        if 'stoch_rising' in df.columns:
            momentum_indicators.append(df['stoch_rising'])
        
        if momentum_indicators:
            momentum_score = pd.concat(momentum_indicators, axis=1).sum(axis=1)
            total_indicators = len(momentum_indicators)
            
            df['momentum_regime_bullish'] = (momentum_score >= total_indicators * 0.75).astype(int)
            df['momentum_regime_bearish'] = (momentum_score <= total_indicators * 0.25).astype(int)
            df['momentum_regime_neutral'] = ((momentum_score > total_indicators * 0.25) & 
                                           (momentum_score < total_indicators * 0.75)).astype(int)
        
        # === Momentum Acceleration ===
        if '_rsi_14' in df.columns:
            rsi_acceleration = df['_rsi_14'].diff().diff()
            df['momentum_accelerating_up'] = (rsi_acceleration > 0).astype(int)
            df['momentum_accelerating_down'] = (rsi_acceleration < 0).astype(int)
        
        return df
    
    def _calculate_volatility_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volatility regime categorical features"""
        
        if '_atr' in df.columns:
            atr_normalized = df['_atr'] / df['close']
            
            # Volatility percentiles
            atr_percentile = atr_normalized.rolling(100).rank(pct=True)
            
            df['volatility_regime_low'] = (atr_percentile < 0.33).astype(int)
            df['volatility_regime_medium'] = ((atr_percentile >= 0.33) & (atr_percentile <= 0.66)).astype(int)
            df['volatility_regime_high'] = (atr_percentile > 0.66).astype(int)
            df['volatility_regime_extreme'] = (atr_percentile > 0.9).astype(int)
            
            # Volatility trend
            atr_ma = atr_normalized.rolling(20).mean()
            df['volatility_expanding'] = (atr_normalized > atr_ma).astype(int)
            df['volatility_contracting'] = (atr_normalized < atr_ma).astype(int)
        
        return df
    
    def _calculate_trend_strength_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate trend strength categorical features"""
        
        # === ADX-based Trend Strength ===
        if '_adx' in df.columns:
            adx = df['_adx']
            df['trend_strength_weak'] = (adx < 25).astype(int)
            df['trend_strength_moderate'] = ((adx >= 25) & (adx < 50)).astype(int)
            df['trend_strength_strong'] = (adx >= 50).astype(int)
        
        # === MA Slope-based Trend Strength ===
        if '_ema_21' in df.columns:
            ema_slope = df['_ema_21'].diff()
            ema_slope_normalized = ema_slope / df['close']
            
            # Trend slope categories
            slope_threshold = ema_slope_normalized.rolling(50).std()
            df['trend_slope_flat'] = (abs(ema_slope_normalized) < slope_threshold * 0.5).astype(int)
            df['trend_slope_moderate'] = ((abs(ema_slope_normalized) >= slope_threshold * 0.5) & 
                                         (abs(ema_slope_normalized) < slope_threshold * 1.5)).astype(int)
            df['trend_slope_steep'] = (abs(ema_slope_normalized) >= slope_threshold * 1.5).astype(int)
        
        return df
    
    def _calculate_reversal_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate reversal pattern categorical features"""
        
        # === Momentum Reversals ===
        if '_rsi_14' in df.columns:
            rsi = df['_rsi_14']
            
            # RSI reversal patterns
            df['rsi_reversal_bullish'] = ((rsi > 30) & (rsi.shift(1) <= 30) & (rsi.shift(2) <= 30)).astype(int)
            df['rsi_reversal_bearish'] = ((rsi < 70) & (rsi.shift(1) >= 70) & (rsi.shift(2) >= 70)).astype(int)
        
        # === Price Reversal Patterns ===
        # V-bottom/top patterns
        price_change_2 = df['close'].pct_change(2)
        price_change_1 = df['close'].pct_change(1)
        
        # V-bottom: significant drop followed by significant rise
        df['v_bottom_pattern'] = ((price_change_2 < -0.01) & (price_change_1 > 0.01)).astype(int)
        # V-top: significant rise followed by significant drop
        df['v_top_pattern'] = ((price_change_2 > 0.01) & (price_change_1 < -0.01)).astype(int)
        
        # === Failed Breakout Patterns ===
        for period in [20, 50]:
            if f'at_resistance_{period}' in df.columns and f'at_support_{period}' in df.columns:
                # Failed breakout above resistance
                df[f'failed_breakout_above_{period}'] = ((df['high'] > df['high'].rolling(period).max().shift(1)) & 
                                                        (df['close'] < df['high'].rolling(period).max().shift(1))).astype(int)
                # Failed breakdown below support
                df[f'failed_breakdown_below_{period}'] = ((df['low'] < df['low'].rolling(period).min().shift(1)) & 
                                                         (df['close'] > df['low'].rolling(period).min().shift(1))).astype(int)
        
        return df
    
    def _calculate_breakout_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate breakout categorical features"""
        
        # === Range Breakouts ===
        for period in [20, 50]:
            high_level = df['high'].rolling(period).max()
            low_level = df['low'].rolling(period).min()
            range_size = high_level - low_level
            
            # Breakout strength
            breakout_above = df['close'] - high_level.shift(1)
            breakdown_below = low_level.shift(1) - df['close']
            
            # Strong breakouts (beyond previous range by significant margin)
            df[f'strong_breakout_above_{period}'] = (breakout_above > range_size.shift(1) * 0.1).astype(int)
            df[f'strong_breakdown_below_{period}'] = (breakdown_below > range_size.shift(1) * 0.1).astype(int)
            
            # Weak breakouts
            df[f'weak_breakout_above_{period}'] = ((breakout_above > 0) & 
                                                  (breakout_above <= range_size.shift(1) * 0.05)).astype(int)
            df[f'weak_breakdown_below_{period}'] = ((breakdown_below > 0) & 
                                                   (breakdown_below <= range_size.shift(1) * 0.05)).astype(int)
        
        # === Volume-Confirmed Breakouts ===
        if 'volume_surge' in df.columns:
            if 'strong_breakout_above_20' in df.columns:
                df['volume_confirmed_breakout_above'] = (df['strong_breakout_above_20'] & df['volume_surge']).astype(int)
                df['volume_confirmed_breakdown_below'] = (df['strong_breakdown_below_20'] & df['volume_surge']).astype(int)
        
        return df
    
    def _calculate_consolidation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate consolidation/sideways market categorical features"""
        
        # === Range-bound Market ===
        for period in [20, 50]:
            high_level = df['high'].rolling(period).max()
            low_level = df['low'].rolling(period).min()
            range_size = high_level - low_level
            range_normalized = range_size / df['close']
            
            # Narrow range (consolidation)
            range_percentile = range_normalized.rolling(100).rank(pct=True)
            df[f'narrow_range_{period}'] = (range_percentile < 0.25).astype(int)
            df[f'wide_range_{period}'] = (range_percentile > 0.75).astype(int)
            df[f'normal_range_{period}'] = ((range_percentile >= 0.25) & (range_percentile <= 0.75)).astype(int)
            
            # Sideways movement (price staying within range)
            middle_of_range = (high_level + low_level) / 2
            distance_from_middle = abs(df['close'] - middle_of_range) / range_size
            df[f'in_consolidation_{period}'] = (distance_from_middle < 0.25).astype(int)
        
        # === Choppiness Index ===
        if '_atr' in df.columns:
            # Simplified choppiness calculation
            atr_sum = df['_atr'].rolling(14).sum()
            high_low_range = df['high'].rolling(14).max() - df['low'].rolling(14).min()
            choppiness = 100 * np.log10(atr_sum / high_low_range) / np.log10(14)
            
            df['market_choppy'] = (choppiness > 61.8).astype(int)
            df['market_trending'] = (choppiness < 38.2).astype(int)
            df['market_transitional'] = ((choppiness >= 38.2) & (choppiness <= 61.8)).astype(int)
        
        # === Low Volatility Periods ===
        if '_atr' in df.columns:
            atr_normalized = df['_atr'] / df['close']
            atr_ma = atr_normalized.rolling(50).mean()
            df['low_volatility_period'] = (atr_normalized < atr_ma * 0.5).astype(int)
            df['high_volatility_period'] = (atr_normalized > atr_ma * 1.5).astype(int)
        
        return df
    
    def _calculate_impulse_correction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate impulse and correction wave categorical features"""
        
        # === Wave Analysis ===
        price_change_5 = df['close'].pct_change(5)
        price_change_20 = df['close'].pct_change(20)
        
        # Impulse waves (strong directional moves)
        impulse_threshold = abs(price_change_5).rolling(100).quantile(0.8)
        df['impulse_wave_up'] = (price_change_5 > impulse_threshold).astype(int)
        df['impulse_wave_down'] = (price_change_5 < -impulse_threshold).astype(int)
        
        # Correction waves (counter-trend moves after impulse)
        df['correction_wave_up'] = ((price_change_5 > 0) & 
                                   (price_change_20 < 0) & 
                                   (abs(price_change_5) < impulse_threshold)).astype(int)
        df['correction_wave_down'] = ((price_change_5 < 0) & 
                                     (price_change_20 > 0) & 
                                     (abs(price_change_5) < impulse_threshold)).astype(int)
        
        # === Elliott Wave-inspired Features ===
        # Three-wave corrections
        consecutive_up = (df['close'] > df['close'].shift(1)).rolling(3).sum()
        consecutive_down = (df['close'] < df['close'].shift(1)).rolling(3).sum()
        
        df['three_wave_up'] = (consecutive_up == 3).astype(int)
        df['three_wave_down'] = (consecutive_down == 3).astype(int)
        
        # Five-wave impulses
        df['five_wave_up'] = (consecutive_up.rolling(2).sum() >= 4).astype(int)
        df['five_wave_down'] = (consecutive_down.rolling(2).sum() >= 4).astype(int)
        
        return df
    

    def _calculate_fair_value_gap_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Fair Value Gap categorical features"""
        
        # === Bullish Fair Value Gaps ===
        # Gap where current low > previous candle's high (with one candle between)
        bullish_fvg = (df['low'] > df['high'].shift(2)) & (df['low'].shift(1) > df['high'].shift(2))
        bearish_fvg = (df['high'] < df['low'].shift(2)) & (df['high'].shift(1) < df['low'].shift(2))
        
        df['bullish_fvg_present'] = bullish_fvg.astype(int)
        df['bearish_fvg_present'] = bearish_fvg.astype(int)
        
        # FVG size categories
        fvg_size_bull = np.where(bullish_fvg, df['low'] - df['high'].shift(2), 0)
        fvg_size_bear = np.where(bearish_fvg, df['low'].shift(2) - df['high'], 0)
        
        fvg_size_normalized_bull = fvg_size_bull / df['close']
        fvg_size_normalized_bear = fvg_size_bear / df['close']
        
        df['large_bullish_fvg'] = (fvg_size_normalized_bull > 0.005).astype(int)  # >0.5%
        df['large_bearish_fvg'] = (fvg_size_normalized_bear > 0.005).astype(int)
        
        # FVG fill detection (price returning to gap)
        # This gets complex, so simplified version
        df['in_bullish_fvg_zone'] = ((df['low'] <= df['high'].shift(2)) & 
                                    (df['high'] >= df['low'].shift(2)) & 
                                    bullish_fvg.shift(1)).astype(int)
        
        return df

    def _calculate_market_structure_breaks(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate BOS (Break of Structure) and CHoCH (Change of Character) features"""
        
        # === Break of Structure (BOS) ===
        for period in [20, 50]:
            # Previous swing high/low
            swing_high = df['high'].rolling(period).max()
            swing_low = df['low'].rolling(period).min()
            
            # BOS Bullish: Breaking above previous swing high
            df[f'bos_bullish_{period}'] = ((df['close'] > swing_high.shift(1)) & 
                                        (df['close'].shift(1) <= swing_high.shift(2))).astype(int)
            
            # BOS Bearish: Breaking below previous swing low  
            df[f'bos_bearish_{period}'] = ((df['close'] < swing_low.shift(1)) & 
                                        (df['close'].shift(1) >= swing_low.shift(2))).astype(int)
            
            # Strong BOS (with significant margin)
            bos_margin = (swing_high - swing_low).shift(1) * 0.1
            df[f'strong_bos_bullish_{period}'] = ((df['close'] > swing_high.shift(1) + bos_margin) & 
                                                (df['close'].shift(1) <= swing_high.shift(2))).astype(int)
            df[f'strong_bos_bearish_{period}'] = ((df['close'] < swing_low.shift(1) - bos_margin) & 
                                                (df['close'].shift(1) >= swing_low.shift(2))).astype(int)
        
        # === Change of Character (CHoCH) ===
        # Trend direction change indicators
        price_momentum_5 = df['close'].pct_change(5)
        price_momentum_20 = df['close'].pct_change(20)
        
        # CHoCH: When short-term momentum opposes longer-term momentum significantly
        df['choch_bullish'] = ((price_momentum_5 > 0.01) & 
                            (price_momentum_20 < -0.01) & 
                            (price_momentum_5.shift(1) <= 0)).astype(int)
        
        df['choch_bearish'] = ((price_momentum_5 < -0.01) & 
                            (price_momentum_20 > 0.01) & 
                            (price_momentum_5.shift(1) >= 0)).astype(int)
        
        return df

    def _calculate_order_flow_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate order flow and market microstructure features"""
        
        if '_buying_pressure' in df.columns and '_selling_pressure' in df.columns:
            # === Pressure Dominance ===
            df['buying_pressure_dominant'] = (df['_buying_pressure'] > 0.7).astype(int)
            df['selling_pressure_dominant'] = (df['_selling_pressure'] > 0.7).astype(int)
            df['balanced_pressure'] = ((df['_buying_pressure'] > 0.3) & 
                                    (df['_buying_pressure'] < 0.7)).astype(int)
            
            # === Pressure Trend ===
            buying_pressure_ma = df['_buying_pressure'].rolling(10).mean()
            selling_pressure_ma = df['_selling_pressure'].rolling(10).mean()
            
            df['increasing_buying_pressure'] = (df['_buying_pressure'] > buying_pressure_ma).astype(int)
            df['increasing_selling_pressure'] = (df['_selling_pressure'] > selling_pressure_ma).astype(int)
            
            # === Absorption Patterns ===
            # High volume with small price movement (absorption)
            if 'volume_surge' in df.columns and '_price_change_1' in df.columns:
                small_movement = abs(df['_price_change_1']) < abs(df['_price_change_1']).rolling(20).quantile(0.3)
                df['bullish_absorption'] = (df['volume_surge'] & small_movement & df['buying_pressure_dominant']).astype(int)
                df['bearish_absorption'] = (df['volume_surge'] & small_movement & df['selling_pressure_dominant']).astype(int)
        
        return df

    def _calculate_liquidity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate liquidity-based categorical features"""
        
        # === Daily/Session Highs and Lows ===
        if '_high_of_day' in df.columns:
            # Distance to daily levels
            dist_to_daily_high = (df['_high_of_day'] - df['close']) / df['close']
            dist_to_daily_low = (df['close'] - df['_low_of_day']) / df['close']
            
            df['near_daily_high'] = (dist_to_daily_high < 0.01).astype(int)
            df['near_daily_low'] = (dist_to_daily_low < 0.01).astype(int)
            df['at_daily_high'] = (dist_to_daily_high < 0.002).astype(int)
            df['at_daily_low'] = (dist_to_daily_low < 0.002).astype(int)
            
            # Liquidity sweep patterns
            df['daily_high_sweep'] = ((df['high'] > df['_high_of_day'].shift(1)) & 
                                    (df['close'] < df['_high_of_day'].shift(1))).astype(int)
            df['daily_low_sweep'] = ((df['low'] < df['_low_of_day'].shift(1)) & 
                                    (df['close'] > df['_low_of_day'].shift(1))).astype(int)
        
        # === Previous Session Levels ===
        if '_session_high' in df.columns:
            df['above_session_high'] = (df['close'] > df['_session_high']).astype(int)
            df['below_session_low'] = (df['close'] < df['_session_low']).astype(int)
            
            # Session range position
            session_range = df['_session_high'] - df['_session_low']
            session_position = (df['close'] - df['_session_low']) / session_range
            
            df['in_session_lower_third'] = (session_position < 0.33).astype(int)
            df['in_session_upper_third'] = (session_position > 0.67).astype(int)
            df['in_session_middle_third'] = ((session_position >= 0.33) & (session_position <= 0.67)).astype(int)
        
        return df

    def _calculate_enhanced_sideways_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enhanced sideways market detection filters"""
        
        # === Multi-timeframe Sideways Detection ===
        for period in [20, 50, 100]:
            # Range analysis
            high_level = df['high'].rolling(period).max()
            low_level = df['low'].rolling(period).min()
            range_size = high_level - low_level
            
            # Price clustering in middle of range
            middle = (high_level + low_level) / 2
            distance_from_middle = abs(df['close'] - middle)
            
            df[f'price_clustered_middle_{period}'] = (distance_from_middle < range_size * 0.2).astype(int)
            df[f'range_bound_tight_{period}'] = (range_size / df['close'] < 0.02).astype(int)  # <2% range
            
            # Sideways price action patterns
            price_oscillation = abs(df['close'] - df['close'].shift(period//4))
            df[f'oscillating_pattern_{period}'] = (price_oscillation < range_size * 0.3).astype(int)
        
        # === Momentum Divergence in Sideways ===
        if '_rsi_14' in df.columns and '_macd_line' in df.columns:
            # When price is sideways but momentum is building
            price_sideways = df['price_clustered_middle_20'] == 1
            rsi_building = abs(df['_rsi_14'] - 50) > 15  # RSI moving away from neutral
            macd_building = abs(df['_macd_line']) > df['_macd_line'].rolling(20).mean()
            
            df['sideways_with_momentum_buildup'] = (price_sideways & (rsi_building | macd_building)).astype(int)
        
        # === False Breakout Prone Areas ===
        for period in [20, 50]:
            # Areas where multiple false breakouts occurred
            if f'failed_breakout_above_{period}' in df.columns:
                false_breakout_count = (df[f'failed_breakout_above_{period}'].rolling(period).sum() + 
                                    df[f'failed_breakdown_below_{period}'].rolling(period).sum())
                df[f'false_breakout_zone_{period}'] = (false_breakout_count >= 2).astype(int)
        
        # === Volume Profile Insights ===
        # Simplified volume profile concepts
        volume_ma = df['volume'].rolling(50).mean()
        
        # Low volume sideways (weak moves)
        df['low_volume_sideways'] = ((df['volume'] < volume_ma * 0.7) & 
                                    (df['range_bound_tight_20'] == 1)).astype(int)
        
        # High volume at range boundaries (potential breakout preparation)
        if 'near_resistance_20' in df.columns:
            df['volume_at_resistance'] = (df['near_resistance_20'] & (df['volume'] > volume_ma * 1.5)).astype(int)
            df['volume_at_support'] = (df['near_support_20'] & (df['volume'] > volume_ma * 1.5)).astype(int)
        
        return df

    def _cleanup_raw_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove raw indicators to prevent overfitting"""
        
        # Remove all columns starting with underscore (raw indicators)
        cols_to_drop = [col for col in df.columns if col.startswith('_')]
        df = df.drop(columns=cols_to_drop)
        
        return df


# Usage example with categorical features
def process_xauusd_data_categorical(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process XAUUSD data and calculate categorical technical indicators
    
    Parameters:
    df: DataFrame with columns ['datetime', 'open', 'high', 'low', 'close', 'volume']
    
    Returns:
    DataFrame with categorical technical indicators suitable for decision trees
    """
    # Initialize the calculator
    calculator = EnhancedTechnicalIndicatorsGeneric(primary_timeframe='5m')
    
    # Set datetime as index if it's a column
    if 'datetime' in df.columns:
        df = df.set_index('datetime')
        df.index = pd.to_datetime(df.index)
    
    # Ensure we have required columns
    required_columns = ['open', 'high', 'low', 'close']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in DataFrame")
    
    # Add volume if not present
    if 'volume' not in df.columns:
        df['volume'] = 1000.0  # Default volume
    
    print(f"Processing XAUUSD data with {len(df)} rows...")
    
    # Calculate all categorical technical indicators
    df_with_indicators = calculator.calculate_all_indicators(df)
    
    # Get only feature columns (exclude OHLCV)
    feature_cols = [col for col in df_with_indicators.columns 
                   if col not in ['open', 'high', 'low', 'close', 'volume']]
    
    print(f"Completed! Added {len(feature_cols)} categorical technical indicators.")
    print(f"Total feature columns: {len(feature_cols)}")
    
    # Display sample of categorical features
    print("\nSample categorical features:")
    sample_features = feature_cols[:20]  # Show first 20 features
    print(sample_features)
    
    # Show distribution of some key features
    print("\nFeature value distributions (should be mostly 0s and 1s):")
    for feature in sample_features[:5]:
        unique_vals = df_with_indicators[feature].unique()
        print(f"{feature}: {unique_vals}")
    
    return df_with_indicators


# Additional utility functions for strategy development
def get_feature_categories(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Categorize features by type for easier analysis
    
    Returns:
    Dictionary with feature categories
    """
    feature_cols = [col for col in df.columns if col not in ['open', 'high', 'low', 'close', 'volume']]
    
    categories = {
        'trend_features': [col for col in feature_cols if 'trend' in col or 'ema' in col or 'ma_' in col],
        'momentum_features': [col for col in feature_cols if any(x in col for x in ['rsi', 'macd', 'stoch', 'momentum'])],
        'volatility_features': [col for col in feature_cols if any(x in col for x in ['volatility', 'atr', 'range', 'bb'])],
        'volume_features': [col for col in feature_cols if 'volume' in col or 'obv' in col or 'mfi' in col],
        'support_resistance_features': [col for col in feature_cols if any(x in col for x in ['support', 'resistance', 'breakout', 'breakdown'])],
        'candlestick_features': [col for col in feature_cols if any(x in col for x in ['candle', 'body', 'shadow', 'hammer', 'doji', 'engulfing'])],
        'fibonacci_features': [col for col in feature_cols if 'fib' in col],
        'session_features': [col for col in feature_cols if any(x in col for x in ['session', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday'])],
        'market_structure_features': [col for col in feature_cols if any(x in col for x in ['structure', 'higher', 'lower', 'swing'])],
        'reversal_features': [col for col in feature_cols if 'reversal' in col or 'divergence' in col],
        'consolidation_features': [col for col in feature_cols if any(x in col for x in ['consolidation', 'choppy', 'narrow', 'sideways'])],
        'wave_features': [col for col in feature_cols if any(x in col for x in ['wave', 'impulse', 'correction'])],
        'level_features': [col for col in feature_cols if any(x in col for x in ['round', 'psychological', 'level'])],
        # Add these new categories to the existing categories dictionary
        'fair_value_gap_features': [col for col in feature_cols if 'fvg' in col],
        'market_structure_features': [col for col in feature_cols if any(x in col for x in ['bos', 'choch'])],
        'order_flow_features': [col for col in feature_cols if any(x in col for x in ['pressure', 'absorption', 'flow'])],
        'liquidity_features': [col for col in feature_cols if any(x in col for x in ['daily', 'session', 'liquidity', 'sweep'])],
        'enhanced_sideways_features': [col for col in feature_cols if any(x in col for x in ['clustered', 'oscillating', 'false_breakout_zone'])],
        'multi_timeframe_alignment': [col for col in feature_cols if any(x in col for x in ['htf', 'mtf', '_1h_', '_4h_', '_1d_'])]
    }
    
    return categories


def analyze_feature_importance_by_category(df: pd.DataFrame, target_column: str) -> pd.DataFrame:
    """
    Analyze feature importance by category
    
    Parameters:
    df: DataFrame with features and target
    target_column: Name of the target column
    
    Returns:
    DataFrame with feature importance analysis
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    
    categories = get_feature_categories(df)
    feature_cols = [col for col in df.columns if col not in ['open', 'high', 'low', 'close', 'volume', target_column]]
    
    # Prepare data
    X = df[feature_cols].fillna(0)
    y = df[target_column]
    
    # Train random forest
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    
    # Get feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': rf.feature_importances_
    }).sort_values('importance', ascending=False)
    
    # Add category information
    feature_importance['category'] = 'other'
    for category, features in categories.items():
        mask = feature_importance['feature'].isin(features)
        feature_importance.loc[mask, 'category'] = category
    
    # Category summary
    category_summary = feature_importance.groupby('category')['importance'].agg(['sum', 'mean', 'count']).sort_values('sum', ascending=False)
    
    print("Feature Importance by Category:")
    print(category_summary)
    
    return feature_importance


# Example usage
if __name__ == "__main__":
    # Example with sample data
    # sample_data = pd.DataFrame({
    #     'datetime': pd.date_range('2024-01-01', periods=1000, freq='5T'),
    #     'open': np.random.randn(1000).cumsum() + 2000,
    #     'high': np.random.randn(1000).cumsum() + 2005,
    #     'low': np.random.randn(1000).cumsum() + 1995,
    #     'close': np.random.randn(1000).cumsum() + 2000,
    #     'volume': np.random.randint(100, 1000, 1000)
    # })
    
    sample_data = pd.read_csv("../data/XAUUSD_15min_18th_Jan_2026.csv")
    # Process the data with categorical features
    result = process_xauusd_data_categorical(sample_data)
    
    # Show feature categories
    categories = get_feature_categories(result)
    print(f"\nFeature Categories:")
    for category, features in categories.items():
        print(f"{category}: {len(features)} features")
    
    # Save results
    result.to_csv("../data/technical_indicator_cache/XAUUSD_15min_technical_indicators_binary_with_timeframe_alignment_2nd_Feb_2026.csv")
    
    print(f"\nTotal categorical features: {len([col for col in result.columns if col not in ['open', 'high', 'low', 'close', 'volume']])}")
    print("Features saved to CSV file.")
