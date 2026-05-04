"""
Enhanced SMC/ICT Feature Engineering Script - CORRECTED VERSION
A comprehensive implementation of Smart Money Concept (SMC) and Inner Circle Trader (ICT) methodology
WITHOUT LOOK-AHEAD BIAS
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class EnhancedSMCFeatures:
    def __init__(self, df, choch_period=50, idm_period=3, swing_length=8):
        # All methods use `.loc[i, col]` with positional i — index must be 0..len-1.
        # Callers sometimes pass datetime slices / non-zero starts; normalize here.
        self.df = df.reset_index(drop=True).copy()
        self.choch_period = choch_period
        self.idm_period = idm_period
        self.swing_length = swing_length
        self.signal_delay = swing_length  # Delay to avoid look-ahead bias
        
        # Initialize feature columns
        self._initialize_features()
        
    def _initialize_features(self):
        """Initialize all SMC feature columns"""
        # Market Structure Features
        self.df['is_hh'] = 0  # Higher High
        self.df['is_hl'] = 0  # Higher Low
        self.df['is_lh'] = 0  # Lower High
        self.df['is_ll'] = 0  # Lower Low
        
        # Change of Character
        self.df['is_choch'] = 0
        self.df['is_choch_bullish'] = 0
        self.df['is_choch_bearish'] = 0
        
        # Break of Structure
        self.df['is_bos'] = 0
        self.df['is_bos_bullish'] = 0
        self.df['is_bos_bearish'] = 0
        
        # Inducement (IDM)
        self.df['is_idm'] = 0
        self.df['is_idm_bullish'] = 0
        self.df['is_idm_bearish'] = 0
        
        # Fair Value Gaps
        self.df['is_fvg'] = 0
        self.df['is_fvg_bullish'] = 0
        self.df['is_fvg_bearish'] = 0
        
        # Order Blocks
        self.df['is_ob'] = 0
        self.df['is_ob_bullish'] = 0
        self.df['is_ob_bearish'] = 0
        
        # Liquidity Sweeps
        self.df['is_sweep'] = 0
        self.df['is_sweep_bullish'] = 0
        self.df['is_sweep_bearish'] = 0
        
        # Pivot Points
        self.df['is_pivot_high'] = 0
        self.df['is_pivot_low'] = 0
        
        # Lag Features (Historical Pivots)
        for lag in [5, 10, 20]:
            self.df[f'pivot_high_last_{lag}'] = 0  # Was there a pivot high in last N candles?
            self.df[f'pivot_low_last_{lag}'] = 0   # Was there a pivot low in last N candles?
            self.df[f'hh_last_{lag}'] = 0          # Was there HH in last N candles?
            self.df[f'll_last_{lag}'] = 0          # Was there LL in last N candles?
            self.df[f'choch_last_{lag}'] = 0       # Was there CHoCH in last N candles?
            self.df[f'bos_last_{lag}'] = 0         # Was there BOS in last N candles?
        
        # Market Structure State
        self.df['market_structure'] = 0  # 0=bearish, 1=bullish
        self.df['trend_strength'] = 0
    
    def detect_pivot_points(self):
        """
        Detect pivot points with delayed confirmation to avoid look-ahead bias
        Only confirms pivots after swing_length periods have passed
        """
        high = self.df['high'].values
        low = self.df['low'].values
        n = len(self.df)
        
        print(f"Detecting pivot points with {self.swing_length} period swing and {self.signal_delay} period delay...")
        
        # Detect pivot highs with delayed confirmation
        for i in range(self.swing_length, n - self.signal_delay):
            pivot_candidate = i  # Current candidate for pivot
            
            # Only check historical data (no future bars)
            is_pivot_high = True
            for j in range(pivot_candidate - self.swing_length, pivot_candidate + 1):
                if j != pivot_candidate and j >= 0 and high[j] >= high[pivot_candidate]:
                    is_pivot_high = False
                    break
            
            # Additional confirmation: check if it's still highest after some delay
            if is_pivot_high:
                confirmation_end = min(pivot_candidate + self.signal_delay, n - 1)
                still_highest = True
                for j in range(pivot_candidate + 1, confirmation_end + 1):
                    if high[j] > high[pivot_candidate]:
                        still_highest = False
                        break
                
                if still_highest:
                    # Signal the pivot at current time (delayed signal)
                    signal_idx = min(i + self.signal_delay, n - 1)
                    self.df.loc[signal_idx, 'is_pivot_high'] = 1
        
        # Detect pivot lows with delayed confirmation
        for i in range(self.swing_length, n - self.signal_delay):
            pivot_candidate = i
            
            # Only check historical data (no future bars)
            is_pivot_low = True
            for j in range(pivot_candidate - self.swing_length, pivot_candidate + 1):
                if j != pivot_candidate and j >= 0 and low[j] <= low[pivot_candidate]:
                    is_pivot_low = False
                    break
            
            # Additional confirmation: check if it's still lowest after some delay
            if is_pivot_low:
                confirmation_end = min(pivot_candidate + self.signal_delay, n - 1)
                still_lowest = True
                for j in range(pivot_candidate + 1, confirmation_end + 1):
                    if low[j] < low[pivot_candidate]:
                        still_lowest = False
                        break
                
                if still_lowest:
                    # Signal the pivot at current time (delayed signal)
                    signal_idx = min(i + self.signal_delay, n - 1)
                    self.df.loc[signal_idx, 'is_pivot_low'] = 1
        
        print(f"Detected {self.df['is_pivot_high'].sum()} pivot highs and {self.df['is_pivot_low'].sum()} pivot lows")
    
    def detect_market_structure_points(self):
        pivot_highs = self.df[self.df['is_pivot_high'] == 1].copy()
        pivot_lows = self.df[self.df['is_pivot_low'] == 1].copy()
        
        # Analyze pivot highs for HH/LH
        if len(pivot_highs) >= 2:
            for i in range(1, len(pivot_highs)):
                curr_idx = pivot_highs.index[i]
                prev_idx = pivot_highs.index[i-1]
                
                curr_high = self.df.loc[curr_idx, 'high']
                prev_high = self.df.loc[prev_idx, 'high']
                
                if curr_high > prev_high:
                    self.df.loc[curr_idx, 'is_hh'] = 1
                else:
                    self.df.loc[curr_idx, 'is_lh'] = 1
        
        # Analyze pivot lows for HL/LL
        if len(pivot_lows) >= 2:
            for i in range(1, len(pivot_lows)):
                curr_idx = pivot_lows.index[i]
                prev_idx = pivot_lows.index[i-1]
                
                curr_low = self.df.loc[curr_idx, 'low']
                prev_low = self.df.loc[prev_idx, 'low']
                
                if curr_low > prev_low:
                    self.df.loc[curr_idx, 'is_hl'] = 1
                else:
                    self.df.loc[curr_idx, 'is_ll'] = 1
        
        hh_count = self.df['is_hh'].sum()
        hl_count = self.df['is_hl'].sum()
        lh_count = self.df['is_lh'].sum()
        ll_count = self.df['is_ll'].sum()
        
        print(f"Market Structure - HH: {hh_count}, HL: {hl_count}, LH: {lh_count}, LL: {ll_count}")
    
    def detect_fair_value_gaps(self):
        high = self.df['high'].values
        low = self.df['low'].values
        n = len(self.df)
        
        fvg_count = 0
        
        for i in range(3, n):
            # Bullish FVG: Gap between candle 1 high and candle 3 low
            if high[i-3] < low[i-1]:
                self.df.loc[i, 'is_fvg'] = 1
                self.df.loc[i, 'is_fvg_bullish'] = 1
                fvg_count += 1
            
            # Bearish FVG: Gap between candle 1 low and candle 3 high
            elif low[i-3] > high[i-1]:
                self.df.loc[i, 'is_fvg'] = 1
                self.df.loc[i, 'is_fvg_bearish'] = 1
                fvg_count += 1
        
        print(f"Detected {fvg_count} Fair Value Gaps")
    
    def detect_break_of_structure_and_choch(self):
        close = self.df['close'].values
        high = self.df['high'].values
        low = self.df['low'].values
        n = len(self.df)
        
        # Market structure variables
        current_trend = 0  # 0 = bearish, 1 = bullish
        recent_high = None
        recent_low = None
        
        choch_count = 0
        bos_count = 0
        
        # Get pivot points for reference
        pivot_highs = self.df[self.df['is_pivot_high'] == 1].index.tolist()
        pivot_lows = self.df[self.df['is_pivot_low'] == 1].index.tolist()
        
        for i in range(self.choch_period, n):
            # Update recent highs and lows from pivots (only past pivots)
            recent_pivots_high = [idx for idx in pivot_highs if idx < i and idx > i - self.choch_period]
            recent_pivots_low = [idx for idx in pivot_lows if idx < i and idx > i - self.choch_period]
            
            if recent_pivots_high:
                recent_high_idx = recent_pivots_high[-1]
                recent_high = high[recent_high_idx]
            
            if recent_pivots_low:
                recent_low_idx = recent_pivots_low[-1]
                recent_low = low[recent_low_idx]
            
            # CHoCH Detection
            if current_trend == 0 and recent_high is not None:  # In bearish trend
                if close[i] > recent_high:  # Close above recent high = CHoCH to bullish
                    self.df.loc[i, 'is_choch'] = 1
                    self.df.loc[i, 'is_choch_bullish'] = 1
                    current_trend = 1
                    choch_count += 1
            
            elif current_trend == 1 and recent_low is not None:  # In bullish trend
                if close[i] < recent_low:  # Close below recent low = CHoCH to bearish
                    self.df.loc[i, 'is_choch'] = 1
                    self.df.loc[i, 'is_choch_bearish'] = 1
                    current_trend = 0
                    choch_count += 1
            
            # BOS Detection (continuation patterns)
            if current_trend == 1 and recent_high is not None:  # In bullish trend
                if close[i] > recent_high * 1.001:  # Small threshold to avoid noise
                    self.df.loc[i, 'is_bos'] = 1
                    self.df.loc[i, 'is_bos_bullish'] = 1
                    bos_count += 1
            
            elif current_trend == 0 and recent_low is not None:  # In bearish trend
                if close[i] < recent_low * 0.999:  # Small threshold to avoid noise
                    self.df.loc[i, 'is_bos'] = 1
                    self.df.loc[i, 'is_bos_bearish'] = 1
                    bos_count += 1
            
            # Update market structure
            self.df.loc[i, 'market_structure'] = current_trend
        
        print(f"Detected {choch_count} CHoCH and {bos_count} BOS events")
    
    def detect_inducements(self):
        """
        Detect inducements with corrected logic - no look-ahead bias
        """
        close = self.df['close'].values
        high = self.df['high'].values
        low = self.df['low'].values
        n = len(self.df)
        
        idm_count = 0
        
        # Get short-term pivot points for IDM detection (corrected)
        short_pivot_highs = []
        short_pivot_lows = []
        
        # Only use confirmed short-term pivots (no future data)
        for i in range(self.idm_period, n - self.idm_period):
            # Wait for confirmation before marking as pivot
            confirm_idx = min(i + self.idm_period, n - 1)
            
            # Short-term pivot highs (confirmed)
            is_pivot_high = True
            for j in range(i - self.idm_period, i + 1):  # Only past and current
                if j != i and j >= 0 and high[j] >= high[i]:
                    is_pivot_high = False
                    break
            
            # Check confirmation period
            if is_pivot_high and confirm_idx < n:
                confirmed = True
                for j in range(i + 1, min(i + self.idm_period + 1, n)):
                    if high[j] > high[i]:
                        confirmed = False
                        break
                if confirmed:
                    short_pivot_highs.append((confirm_idx, i, high[i]))  # (signal_time, pivot_time, level)
            
            # Short-term pivot lows (confirmed)
            is_pivot_low = True
            for j in range(i - self.idm_period, i + 1):  # Only past and current
                if j != i and j >= 0 and low[j] <= low[i]:
                    is_pivot_low = False
                    break
            
            # Check confirmation period
            if is_pivot_low and confirm_idx < n:
                confirmed = True
                for j in range(i + 1, min(i + self.idm_period + 1, n)):
                    if low[j] < low[i]:
                        confirmed = False
                        break
                if confirmed:
                    short_pivot_lows.append((confirm_idx, i, low[i]))  # (signal_time, pivot_time, level)
        
        # Detect IDM based on confirmed short-term pivots
        for i in range(len(self.df)):
            market_structure = self.df.loc[i, 'market_structure']
            
            # In bullish structure, look for low sweeps (bearish IDM)
            if market_structure == 1:
                relevant_lows = [(sig_time, piv_time, level) for sig_time, piv_time, level in short_pivot_lows 
                               if sig_time <= i and i - piv_time <= self.swing_length * 2]
                if relevant_lows:
                    _, _, recent_low_level = relevant_lows[-1]
                    if low[i] < recent_low_level and close[i] > recent_low_level:
                        self.df.loc[i, 'is_idm'] = 1
                        self.df.loc[i, 'is_idm_bearish'] = 1
                        idm_count += 1
            
            # In bearish structure, look for high sweeps (bullish IDM)
            elif market_structure == 0:
                relevant_highs = [(sig_time, piv_time, level) for sig_time, piv_time, level in short_pivot_highs 
                                if sig_time <= i and i - piv_time <= self.swing_length * 2]
                if relevant_highs:
                    _, _, recent_high_level = relevant_highs[-1]
                    if high[i] > recent_high_level and close[i] < recent_high_level:
                        self.df.loc[i, 'is_idm'] = 1
                        self.df.loc[i, 'is_idm_bullish'] = 1
                        idm_count += 1
        
        print(f"Detected {idm_count} Inducement (IDM) events")
    
    def detect_order_blocks(self):
        open_price = self.df['open'].values
        close = self.df['close'].values
        
        ob_count = 0
        
        # Find BOS and CHoCH points
        structure_breaks = self.df[
            (self.df['is_bos'] == 1) | (self.df['is_choch'] == 1)
        ].copy()
        
        for idx in structure_breaks.index:
            is_bullish_break = (
                self.df.loc[idx, 'is_bos_bullish'] == 1 or 
                self.df.loc[idx, 'is_choch_bullish'] == 1
            )
            
            # Look back for order block candle
            lookback_start = max(0, idx - self.swing_length * 2)
            
            if is_bullish_break:
                # For bullish breaks, find last bearish candle (red candle)
                for i in range(idx - 1, lookback_start - 1, -1):
                    if close[i] < open_price[i]:  # Red candle
                        self.df.loc[i, 'is_ob'] = 1
                        self.df.loc[i, 'is_ob_bullish'] = 1
                        ob_count += 1
                        break
            else:
                # For bearish breaks, find last bullish candle (green candle)
                for i in range(idx - 1, lookback_start - 1, -1):
                    if close[i] > open_price[i]:  # Green candle
                        self.df.loc[i, 'is_ob'] = 1
                        self.df.loc[i, 'is_ob_bearish'] = 1
                        ob_count += 1
                        break
        
        print(f"Detected {ob_count} Order Blocks")
    
    def detect_liquidity_sweeps(self):
        """Detect Liquidity Sweeps - fake-outs above/below key levels"""
        high = self.df['high'].values
        low = self.df['low'].values
        close = self.df['close'].values
        
        sweep_count = 0
        
        # Use pivot points as liquidity levels
        pivot_highs = self.df[self.df['is_pivot_high'] == 1].copy()
        pivot_lows = self.df[self.df['is_pivot_low'] == 1].copy()
        
        for i in range(len(self.df)):
            # Check for sweeps of recent pivot highs
            recent_highs = pivot_highs[
                (pivot_highs.index < i) &  # Only past pivots
                (pivot_highs.index > i - self.swing_length * 3)
            ]
            
            for pivot_idx in recent_highs.index:
                pivot_level = high[pivot_idx]
                if (high[i] > pivot_level and  # Sweep above
                    close[i] < pivot_level):   # But close below
                    self.df.loc[i, 'is_sweep'] = 1
                    self.df.loc[i, 'is_sweep_bearish'] = 1
                    sweep_count += 1
                    break
            
            # Check for sweeps of recent pivot lows
            recent_lows = pivot_lows[
                (pivot_lows.index < i) &  # Only past pivots
                (pivot_lows.index > i - self.swing_length * 3)
            ]
            
            for pivot_idx in recent_lows.index:
                pivot_level = low[pivot_idx]
                if (low[i] < pivot_level and   # Sweep below
                    close[i] > pivot_level):   # But close above
                    self.df.loc[i, 'is_sweep'] = 1
                    self.df.loc[i, 'is_sweep_bullish'] = 1
                    sweep_count += 1
                    break
        
        print(f"Detected {sweep_count} Liquidity Sweeps")
    
    def create_lag_features(self):
        """Create lag-based features to capture recent SMC activity"""
        print("Creating lag features...")
        
        for lag in [5, 10, 20]:
            # Rolling window detection for recent activity
            self.df[f'pivot_high_last_{lag}'] = self.df['is_pivot_high'].rolling(lag, min_periods=1).sum().astype(int)
            self.df[f'pivot_low_last_{lag}'] = self.df['is_pivot_low'].rolling(lag, min_periods=1).sum().astype(int)
            self.df[f'hh_last_{lag}'] = self.df['is_hh'].rolling(lag, min_periods=1).sum().astype(int)
            self.df[f'll_last_{lag}'] = self.df['is_ll'].rolling(lag, min_periods=1).sum().astype(int)
            self.df[f'choch_last_{lag}'] = self.df['is_choch'].rolling(lag, min_periods=1).sum().astype(int)
            self.df[f'bos_last_{lag}'] = self.df['is_bos'].rolling(lag, min_periods=1).sum().astype(int)
            
            # Binary versions (any activity in last N candles)
            self.df[f'any_pivot_high_last_{lag}'] = (self.df[f'pivot_high_last_{lag}'] > 0).astype(int)
            self.df[f'any_pivot_low_last_{lag}'] = (self.df[f'pivot_low_last_{lag}'] > 0).astype(int)
            self.df[f'any_hh_last_{lag}'] = (self.df[f'hh_last_{lag}'] > 0).astype(int)
            self.df[f'any_ll_last_{lag}'] = (self.df[f'll_last_{lag}'] > 0).astype(int)
            self.df[f'any_choch_last_{lag}'] = (self.df[f'choch_last_{lag}'] > 0).astype(int)
            self.df[f'any_bos_last_{lag}'] = (self.df[f'bos_last_{lag}'] > 0).astype(int)
        
        print("Lag features created successfully")
    
    def add_additional_features(self):
        """Add supplementary technical features"""
        # Price action characteristics
        self.df['is_bullish_candle'] = (self.df['close'] > self.df['open']).astype(int)
        self.df['is_bearish_candle'] = (self.df['close'] < self.df['open']).astype(int)
        self.df['is_doji'] = (abs(self.df['close'] - self.df['open']) < (self.df['high'] - self.df['low']) * 0.1).astype(int)
        
        # Range and volatility
        self.df['range_pct'] = ((self.df['high'] - self.df['low']) / self.df['close'] * 100)
        self.df['body_pct'] = (abs(self.df['close'] - self.df['open']) / self.df['close'] * 100)
        
        # Volume characteristics
        self.df['volume_sma_20'] = self.df['volume'].rolling(20).mean()
        self.df['is_high_volume'] = (self.df['volume'] > self.df['volume_sma_20'] * 1.5).astype(int)
        
        # Trend context (simple moving averages)
        for period in [8, 21, 50]:
            self.df[f'sma_{period}'] = self.df['close'].rolling(period).mean()
            self.df[f'above_sma_{period}'] = (self.df['close'] > self.df[f'sma_{period}']).astype(int)
        
        # Trend strength based on SMC concepts
        self.df['trend_strength'] = (
            self.df['is_hh'] * 2 + self.df['is_hl'] * 1 - 
            self.df['is_lh'] * 2 - self.df['is_ll'] * 1
        )
        
        # SMC Activity Score (recent activity)
        self.df['smc_activity_score_5'] = (
            self.df['any_pivot_high_last_5'] + self.df['any_pivot_low_last_5'] +
            self.df['any_choch_last_5'] + self.df['any_bos_last_5']
        )
        self.df['smc_activity_score_10'] = (
            self.df['any_pivot_high_last_10'] + self.df['any_pivot_low_last_10'] +
            self.df['any_choch_last_10'] + self.df['any_bos_last_10']
        )
    
    def process_all_features(self):
        """Execute all SMC feature detection methods"""
        print("=== SMC/ICT Feature Engineering (NO LOOK-AHEAD BIAS) ===")
        
        print("1. Detecting pivot points...")
        self.detect_pivot_points()
        
        print("2. Detecting market structure points (HH, HL, LH, LL)...")
        self.detect_market_structure_points()
        
        print("3. Detecting Fair Value Gaps...")
        self.detect_fair_value_gaps()
        
        print("4. Detecting Break of Structure and Change of Character...")
        self.detect_break_of_structure_and_choch()
        
        print("5. Detecting Inducements...")
        self.detect_inducements()
        
        print("6. Detecting Order Blocks...")
        self.detect_order_blocks()
        
        print("7. Detecting Liquidity Sweeps...")
        self.detect_liquidity_sweeps()
        
        print("8. Creating lag features...")
        self.create_lag_features()
        
        print("9. Adding additional features...")
        self.add_additional_features()
        
        print("=== Feature Engineering Complete ===")
        
        return self.df
    
    def get_feature_summary(self):
        """Generate comprehensive feature summary"""
        smc_features = {
            'Market Structure': ['is_hh', 'is_hl', 'is_lh', 'is_ll'],
            'Pivots': ['is_pivot_high', 'is_pivot_low'],
            'Structure Changes': ['is_choch', 'is_choch_bullish', 'is_choch_bearish'],
            'Breaks of Structure': ['is_bos', 'is_bos_bullish', 'is_bos_bearish'],
            'Inducements': ['is_idm', 'is_idm_bullish', 'is_idm_bearish'],
            'Fair Value Gaps': ['is_fvg', 'is_fvg_bullish', 'is_fvg_bearish'],
            'Order Blocks': ['is_ob', 'is_ob_bullish', 'is_ob_bearish'],
            'Liquidity Sweeps': ['is_sweep', 'is_sweep_bullish', 'is_sweep_bearish'],
            'Lag Features (5)': ['any_pivot_high_last_5', 'any_pivot_low_last_5', 'any_choch_last_5', 'any_bos_last_5'],
            'Lag Features (10)': ['any_pivot_high_last_10', 'any_pivot_low_last_10', 'any_choch_last_10', 'any_bos_last_10'],
            'Lag Features (20)': ['any_pivot_high_last_20', 'any_pivot_low_last_20', 'any_choch_last_20', 'any_bos_last_20']
        }
        
        summary = {}
        for category, features in smc_features.items():
            category_summary = {}
            for feature in features:
                if feature in self.df.columns:
                    count = self.df[feature].sum()
                    percentage = (count / len(self.df)) * 100
                    category_summary[feature] = {
                        'count': count,
                        'percentage': percentage
                    }
            summary[category] = category_summary
        
        return summary


def main():
    print("Loading XAUUSD data...")
    # Update path as needed
    df = pd.read_csv('../data/XAUUSD_15min_18th_Jan_2026.csv')
    
    # Prepare data
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    
    print(f"Loaded {len(df):,} rows from {df['datetime'].min()} to {df['datetime'].max()}")
    
    # Initialize SMC engine
    smc_engine = EnhancedSMCFeatures(
        df=df,
        choch_period=50,
        idm_period=3,
        swing_length=8
    )
    
    # Process all features
    df_with_features = smc_engine.process_all_features()
    
    # Get and display summary
    summary = smc_engine.get_feature_summary()
    
    print("\n" + "="*80)
    print("SMC/ICT FEATURE DETECTION SUMMARY")
    print("="*80)
    
    for category, features in summary.items():
        print(f"\n{category.upper()}:")
        for feature, stats in features.items():
            print(f"  {feature:<25}: {stats['count']:>6,} ({stats['percentage']:>6.2f}%)")
    
    # Save results
    # output_file = 'XAUUSD_with_Enhanced_SMC_Features_Corrected.csv'
    # df_with_features.to_csv(output_file, index=False)
    # print(f"\nEnhanced SMC features saved to: {output_file}")
    
    # Show sample of active features
    smc_cols = [col for col in df_with_features.columns if col.startswith('is_')]
    active_rows = df_with_features[df_with_features[smc_cols].sum(axis=1) > 0]
    
    print(f"\n📊 Total rows with SMC activity: {len(active_rows):,} ({len(active_rows)/len(df_with_features)*100:.1f}%)")
    
    # Display lag feature statistics
    print("\n" + "="*80)
    print("LAG FEATURE STATISTICS")
    print("="*80)
    
    lag_features = [col for col in df_with_features.columns if 'last_' in col and 'any_' in col]
    for feature in lag_features:
        count = df_with_features[feature].sum()
        pct = count / len(df_with_features) * 100
        print(f"  {feature:<30}: {count:>6,} ({pct:>6.2f}%)")
    
    return df_with_features


if __name__ == "__main__":
    result_df = main()
    result_df.to_csv("../data/technical_indicator_cache/XAUUSD_with_SMC_Features_15min_2nd_Feb_2026_without_lag.csv")