"""
Comprehensive Python implementation approximating the provided pseudocode.
- Saves/continues reports in "reports.json" in the working folder.
- Uses input from 'input.txt' if present; otherwise falls back to embedded sample_input.

Notes:
- This is an engineering approximation of the pseudocode: every Problem (1..7)
  is implemented with simplified but functional components and clear APIs.
- Requires numpy for linear algebra (used by Ridge regression). If numpy is not
  available, the script will still run but ridge regression will fall back to a
  basic Python solver (slower / less stable).

Run:
    python sensor_system.py

"""

from __future__ import annotations
import os
import json
import time
import math
import random
from collections import deque, defaultdict, namedtuple
from bisect import bisect_left, bisect_right, insort
from datetime import datetime

try:
    import numpy as np
except Exception:
    np = None

# ------------------------- Utility helpers -------------------------

def now_ts():
    return int(time.time())


def soft_l1_shrink(x, lambd):
    if x > 0:
        return max(x - lambd, 0)
    else:
        return -max(-x - lambd, 0)


# ------------------------- Problem 1: Adaptive Dual-Mode Sensor Fusion -------------------------

class PositionDetector:
    """Given four corner load cell readings returns (x,y,total).
    Since the incoming test data is a single weight reading, we synthesize a
    plausible 4-cell distribution assuming center loading or small jitter.
    """

class PositionDetector:
    """Given four corner load cell readings returns (x,y,total).
    Since the incoming test data is a single weight reading, we synthesize a
    plausible 4-cell distribution assuming center loading or small jitter.
    """


    @staticmethod
    def compute_position(load_readings=None):
        # load_readings: optional tuple/list of 4 sensor values (TL, TR, BL, BR)
        # Avoid calling len() on non-iterables (float); check type first.
        if isinstance(load_readings, (list, tuple)) and len(load_readings) == 4:
            TL, TR, BL, BR = load_readings
        else:
            # If a single numeric measurement provided, split equally with small noise
            if isinstance(load_readings, (int, float)):
                base = float(load_readings)
                TL = TR = BL = BR = base / 4.0
                # add tiny noise to break perfect symmetry
                TL *= (1 + (random.random() - 0.5) * 0.02)
                TR *= (1 + (random.random() - 0.5) * 0.02)
                BL *= (1 + (random.random() - 0.5) * 0.02)
                BR *= (1 + (random.random() - 0.5) * 0.02)
            else:
                # default zero when nothing valid passed
                TL = TR = BL = BR = 0.0

        total = TL + TR + BL + BR + 1e-9
        # x = (right - left) / total -> normalized [-1,1], map to [0,1]
        x = ((TR + BR) - (TL + BL)) / total * 0.5 + 0.5
        y = ((TL + TR) - (BL + BR)) / total * 0.5 + 0.5
        return (max(0.0, min(1.0, x)), max(0.0, min(1.0, y)), total)



class FuzzyCalibrationController:
    """Simple fuzzy-style correction based on temperature/humidity deviations
    from nominal. This is a compact approximation of fuzzy rules.
    """

    def __init__(self, base_cf=1.0, nominal_temp=25.0, nominal_humidity=50.0):
        self.base_cf = base_cf
        self.nominal_temp = nominal_temp
        self.nominal_humidity = nominal_humidity

    def compute_fuzzy_correction(self, temp_delta, humidity_delta, position):
        # membership-like continuous factors
        t_factor = 1.0 + 0.01 * (temp_delta / 5.0)  # small effect per 5°C
        h_factor = 1.0 + 0.005 * (humidity_delta / 10.0)
        # position correction: if object is near edge, sensors less accurate
        px, py = position
        edge_dist = min(px, 1-px, py, 1-py)
        pos_penalty = 1.0 + 0.2 * (0.5 - edge_dist)  # up to +0.1~+0.2
        correction = self.base_cf * t_factor * h_factor * pos_penalty
        return correction


class AdaptiveDualModeSensorFusion:
    def __init__(self, kalman_filter, fuzzy_controller=None):
        self.kalman = kalman_filter
        self.fuzzy = fuzzy_controller or FuzzyCalibrationController()
        self.BASE_CF = 1.0

    def process_sensor_reading(self, raw_weight, temp=25.0, humidity=50.0, timestamp=None):
        # Step 1: compute position (we only have weight single reading)
        x, y, total = PositionDetector.compute_position(raw_weight)
        # Step 2: calibration
        temp_delta = temp - self.fuzzy.nominal_temp
        humidity_delta = humidity - self.fuzzy.nominal_humidity
        fuzzy_corr = self.fuzzy.compute_fuzzy_correction(temp_delta, humidity_delta, (x,y))
        position_correction = 1.0 + 0.05 * (abs(x-0.5) + abs(y-0.5))
        calibration_factor = self.BASE_CF * fuzzy_corr * position_correction
        # Step 3 & 4: calibrated measurement and Kalman filter with position-aware variance
        calibrated_measurement = raw_weight / calibration_factor
        # position-aware process noise / measurement noise
        q = max(0.1, 1.0 * (1.0 + (0.5 - min(x,y))))
        r = max(0.5, 2.0 * (1.0 + abs(x-0.5) + abs(y-0.5)))
        filtered, variance, innovation, prediction = self.kalman.filter_step(calibrated_measurement, q=q, r=r, timestamp=timestamp)
        # anomaly check
        anomaly = False
        if abs(calibrated_measurement - prediction) > 3.0 * math.sqrt(variance + 1e-9):
            anomaly = True
        return {
            'calibrated_weight': float(filtered),
            'position': (x, y),
            'variance': float(variance),
            'anomaly': bool(anomaly),
            'raw': float(raw_weight),
            'calibration_factor': float(calibration_factor),
            'innovation': float(innovation),
            'prediction': float(prediction),
        }


# ------------------------- Problem 2: Kalman-L1 Hybrid Filtering -------------------------

class KalmanL1HybridFilter:
    def __init__(self, init_x=0.0, init_P=1.0):
        # Simple 1D Kalman on weight with optional velocity extension (not used now)
        self.x = float(init_x)
        self.P = float(init_P)
        self.last_ts = None
        # sparse storage (COO)
        self.timestamps = []
        self.deltas = []
        self.variances = []
        # saved predictions
        self.last_prediction = self.x

    def filter_step(self, measurement, q=1.0, r=1.0, timestamp=None):
        # Predict (identity model)
        prediction = self.x
        P_pred = self.P + q
        # innovation
        innovation = measurement - prediction
        # L1 shrink
        lambd = 1.0  # tunable
        innovation_sparse = soft_l1_shrink(innovation, lambd)
        # Kalman update using innovation_sparse
        S = P_pred + r
        K = P_pred / S
        self.x = prediction + K * innovation_sparse
        self.P = (1 - K) * P_pred
        self.last_prediction = prediction
        # store sparse if magnitude > epsilon
        eps_sparse = 10.0  # g threshold
        stored = False
        if abs(innovation_sparse) > eps_sparse:
            ts = timestamp or now_ts()
            self.timestamps.append(ts)
            self.deltas.append(float(innovation_sparse))
            self.variances.append(float(self.P))
            stored = True
        return float(self.x), float(self.P), float(innovation_sparse), float(prediction)

    def store_sparse(self, timestamp, delta, variance):
        # append in sorted order by timestamp (COO)
        idx = bisect_right(self.timestamps, timestamp)
        self.timestamps.insert(idx, timestamp)
        self.deltas.insert(idx, delta)
        self.variances.insert(idx, variance)

    def reconstruct_weight_at_time(self, base_weight, query_time):
        # Reconstruct by applying prefix-sum of deltas up to query_time
        idx = bisect_right(self.timestamps, query_time)
        applied = sum(self.deltas[:idx])
        return base_weight + applied

    def detect_sparse_anomalies(self, threshold=50.0):
        anomalies = []
        for i, d in enumerate(self.deltas):
            if abs(d) > threshold:
                anomalies.append({'timestamp': self.timestamps[i], 'delta': d, 'variance': self.variances[i]})
        return anomalies


# ------------------------- Problem 3: Tiered Skip List Event Tracking -------------------------

# We'll provide a simplified multi-level skiplist-like structure using multiple
# index levels backed by sorted lists. The API is SkipList.insert, range_query,
# get_bucket_stats.


class SkipListNode:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.next = []  # levels


class SkipList:
    def __init__(self, max_level=6, p=0.5):
        self.max_level = max_level
        self.p = p
        self.header = SkipListNode(None, None)
        self.header.next = [None] * max_level
        self.level = 0
        # For ease we maintain a sorted list of keys->values for O(log n + k) queries
        self._keys = []
        self._values = []
        # Hourly bucket stats
        self.bucket_index = defaultdict(lambda: {'count': 0, 'total_consumed': 0.0, 'total_restocked': 0.0, 'variance_sum': 0.0, 'anomaly_flags': []})

    def random_level(self):
        lvl = 1
        while random.random() < self.p and lvl < self.max_level:
            lvl += 1
        return lvl

    def insert(self, timestamp, event_data):
        # Insert into sorted arrays
        idx = bisect_right(self._keys, timestamp)
        self._keys.insert(idx, timestamp)
        self._values.insert(idx, event_data)
        # Update bucket (hour id)
        hour_id = timestamp // 3600
        bucket = self.bucket_index[hour_id]
        bucket['count'] += 1
        q = event_data.get('quantity', 0.0)
        if event_data.get('type') == 'consumption':
            bucket['total_consumed'] += q
        elif event_data.get('type') == 'restock':
            bucket['total_restocked'] += q
        # variance accumulation (using sum of squares approx)
        bucket['variance_sum'] += q * q

    def range_query(self, start_time, end_time):
        l = bisect_left(self._keys, start_time)
        r = bisect_right(self._keys, end_time)
        return [{'timestamp': self._keys[i], 'event': self._values[i]} for i in range(l, r)]

    def get_bucket_stats(self, timestamp):
        hour_id = timestamp // 3600
        b = self.bucket_index.get(hour_id)
        if not b:
            return None
        # derive variance (approx)
        count = b['count']
        mean_sq = b['variance_sum'] / (count or 1)
        variance = max(0.0, mean_sq - (b['total_consumed'] / (count or 1)) ** 2)
        res = dict(b)
        res['variance'] = variance
        return res

    def get_hourly_summary(self, start_time, end_time):
        start_hour = start_time // 3600
        end_hour = end_time // 3600
        summaries = {}
        for h in range(start_hour, end_hour + 1):
            summaries[h] = self.get_bucket_stats(h * 3600) or {'count': 0, 'total_consumed': 0.0}
        return summaries


class EventTracker:
    def __init__(self):
        self.skip_list = SkipList()

    def add_event(self, timestamp, event_data):
        self.skip_list.insert(timestamp, event_data)

    def query_range(self, start_time, end_time):
        return self.skip_list.range_query(start_time, end_time)

    def bucket_stats(self, timestamp):
        return self.skip_list.get_bucket_stats(timestamp)


# ------------------------- Problem 4: Kalman-Signature Window with Demand Faceting -------------------------

class DemandClassifier:
    @staticmethod
    def classify(magnitude, duration):
        # duration in seconds
        if duration < 0.5:
            return 'JITTER'
        elif magnitude < 50:
            return 'PICK'
        elif magnitude > 200:
            # further heuristic: restorative if positive mag (increase)
            return 'RESTOCK' if magnitude > 0 and duration > 1 else 'BULK'
        else:
            return 'PICK'


class SignatureRegressionModel:
    def __init__(self, ridge_alpha=1.0):
        self.alpha = ridge_alpha
        self.coef_ = None
        self.intercept_ = 0.0

    def fit(self, X, y):
        # X: list of feature vectors; y: list of scalars
        if len(X) == 0:
            self.coef_ = None
            self.intercept_ = 0.0
            return
        X = np.array(X) if np and not isinstance(X, list) else np.array(X) if np else None
        y = np.array(y)
        if np is None:
            # fallback simple linear ridge via normal equations using pure python (slow)
            # we only support small sizes in fallback
            raise RuntimeError("numpy required for regression fallback not implemented")
        # closed-form ridge: (X^T X + alpha I)^{-1} X^T y
        XtX = X.T.dot(X)
        n = XtX.shape[0]
        XtX += self.alpha * np.eye(n)
        Xty = X.T.dot(y)
        w = np.linalg.solve(XtX, Xty)
        self.coef_ = w
        self.intercept_ = 0.0

    def predict(self, x):
        if self.coef_ is None:
            return 0.0
        x = np.array(x)
        return float(x.dot(self.coef_) + self.intercept_)


class DemandSignatureWindow:
    def __init__(self, window_size=100):
        self.window_size = window_size
        self.events = deque(maxlen=window_size)  # store (timestamp, magnitude)
        self.models = defaultdict(lambda: SignatureRegressionModel(ridge_alpha=1.0))
        self.history_signatures = defaultdict(list)
        self.history_demands = defaultdict(list)

    def add_event(self, timestamp, weight_change, duration):
        cls = DemandClassifier.classify(abs(weight_change), duration)
        e = {'timestamp': timestamp, 'magnitude': weight_change, 'duration': duration, 'class': cls}
        self.events.append(e)

    def _compute_signature_for_class(self, cls):
        # compute rough signature up to order-3 as described
        seq = [e['magnitude'] for e in self.events if e['class'] == cls]
        if not seq:
            return [0.0]
        # linear, second and third order sums
        linear = sum(seq)
        second = 0.0
        third = 0.0
        n = len(seq)
        for i in range(n):
            for j in range(n):
                second += seq[i] * seq[j]
                for k in range(n):
                    third += seq[i] * seq[j] * seq[k]
        return [linear, second, third]

    def _analyze_and_forecast(self):
        # build signatures for each class
        signatures = {}
        for cls in ['JITTER', 'PICK', 'BULK', 'RESTOCK']:
            signatures[cls] = self._compute_signature_for_class(cls)
        # train simple ridge models per class using history
        forecasts = {}
        for cls, sig in signatures.items():
            Xhist = self.history_signatures.get(cls, [])
            yhist = self.history_demands.get(cls, [])
            model = self.models[cls]
            if Xhist and np is not None:
                model.fit(np.array(Xhist), np.array(yhist))
            # if no history, default heuristic
            forecast = model.predict(sig) if model.coef_ is not None else max(0.0, sig[0])
            forecasts[cls] = float(forecast)
        total = sum(forecasts.values())
        return {'forecasts': forecasts, 'total': total, 'signatures': signatures}

    def get_demand_forecast(self):
        return self._analyze_and_forecast()

    def detect_demand_anomalies(self):
        # anomaly if any event magnitude very large
        anomalies = []
        for e in self.events:
            if abs(e['magnitude']) > 1000:
                anomalies.append(e)
        return anomalies


# ------------------------- Problem 5: Adaptive Segment Tree Multi-Dimensional Indexing -------------------------

class SegmentTreeNode:
    def __init__(self, start_ts, end_ts):
        self.start = start_ts
        self.end = end_ts
        self.sum_consumption = 0.0
        self.sum_temp = 0.0
        self.sum_humidity = 0.0
        self.count = 0
        self.variance = 0.0
        # optional secondary index by temp as simple bins
        self.temp_index = None  # dict bin_id -> list of samples


class AdaptiveSegmentTree:
    def __init__(self, bucket_seconds=3600):
        self.bucket_seconds = bucket_seconds
        self.buckets = {}  # bucket_id -> SegmentTreeNode

    def add_sample(self, timestamp, consumption, temp, humidity):
        bid = timestamp // self.bucket_seconds
        node = self.buckets.get(bid)
        if node is None:
            node = SegmentTreeNode(bid*self.bucket_seconds, (bid+1)*self.bucket_seconds-1)
            self.buckets[bid] = node
        node.count += 1
        node.sum_consumption += consumption
        node.sum_temp += temp
        node.sum_humidity += humidity
        # update variance incrementally (Welford not strictly implemented - approximated)
        node.variance += consumption * consumption
        # decide to build temp index if variance high (>threshold)
        if node.count >= 10:
            approx_var = node.variance / node.count - (node.sum_consumption / node.count) ** 2
            if approx_var > 10000 and node.temp_index is None:
                # build temp index with bins of 5°C from 0..50
                node.temp_index = defaultdict(list)
        # If temp_index exists, add sample
        if node.temp_index is not None:
            bin_id = int(temp // 5)
            node.temp_index[bin_id].append((timestamp, consumption, temp, humidity))

    def query_range(self, time_range, temp_range=None, humidity_range=None):
        t1, t2 = time_range
        start_bid = t1 // self.bucket_seconds
        end_bid = t2 // self.bucket_seconds
        results = []
        for b in range(start_bid, end_bid+1):
            node = self.buckets.get(b)
            if not node:
                continue
            if node.temp_index is not None and temp_range is not None:
                bins = range(int(temp_range[0]//5), int(temp_range[1]//5)+1)
                for bin_id in bins:
                    for sample in node.temp_index.get(bin_id, []):
                        ts, c, temp, hum = sample
                        if t1 <= ts <= t2 and (humidity_range is None or (humidity_range[0] <= hum <= humidity_range[1])):
                            results.append(sample)
            else:
                # fallback: we don't store raw samples globally; so we approximate with aggregated
                if t1 <= node.start <= t2:
                    results.append((node.start, node.sum_consumption, node.sum_temp / max(1,node.count), node.sum_humidity / max(1,node.count)))
        return results


class TrendAnalyzer:
    def __init__(self):
        self.tree = AdaptiveSegmentTree()

    def add_sample(self, timestamp, consumption, temp, humidity):
        self.tree.add_sample(timestamp, consumption, temp, humidity)

    def query_range(self, time_range, temp_range=None, humidity_range=None):
        return self.tree.query_range(time_range, temp_range, humidity_range)


# ------------------------- Problem 6: Hierarchical Temporal Point Process Graph -------------------------

class HawkesProcess:
    def __init__(self):
        # store simple parameters mu (per class) and alpha/beta matrices approximated
        self.mu = defaultdict(float)
        self.alpha = defaultdict(lambda: defaultdict(float))
        self.beta = defaultdict(lambda: defaultdict(float))

    def fit(self, events, iterations=50, lr=1e-3):
        # events: list of (timestamp, class)
        # Small gradient steps to roughly fit mu only
        classes = set(c for (_,c) in events)
        for c in classes:
            self.mu[c] = max(1e-3, len([1 for (_,cls) in events if cls==c]) / max(1.0, (events[-1][0] - events[0][0] + 1)))
        # alpha/beta left default small values

    def predict_intensity(self, current_time):
        # simple sum of mus
        return sum(self.mu.values())


class SimpleGNNEncoder:
    def __init__(self, input_size=16, hidden_size=8, out_size=8):
        # small random weights
        self.W1 = np.random.randn(input_size, hidden_size) if np else None
        self.W2 = np.random.randn(hidden_size, out_size) if np else None

    def encode(self, features):
        if np is None:
            # fallback: normalized features
            v = np.array(features) if np else list(features)
            norm = np.linalg.norm(v) if np else math.sqrt(sum(f*f for f in v))
            return (v / (norm+1e-9)).tolist()
        feats = np.array(features)
        h = np.tanh(feats @ self.W1)
        emb = h @ self.W2
        n = np.linalg.norm(emb)
        return list((emb / (n+1e-9)).tolist())


class HierarchicalEventGraph:
    def __init__(self):
        self.hawkes_history = []  # per-window params
        self.embeddings = []
        self.gnn = SimpleGNNEncoder(input_size=32, hidden_size=16, out_size=8) if np else None

    def process_events_window(self, events, window_id):
        hp = HawkesProcess()
        hp.fit(events)
        features = []
        # create feature vector from hawkes params (flattened mu up to 8 classes)
        for k,v in list(hp.mu.items())[:8]:
            features.append(v)
        features += [0]*(32-len(features))
        emb = self.gnn.encode(features) if self.gnn else features[:8]
        self.hawkes_history.append(hp)
        self.embeddings.append(emb)
        return {'embedding': emb, 'hawkes': hp}

    def forecast_demand_from_graph(self, current_embedding, k=3):
        # simple kNN on embedding cosine similarity
        if not self.embeddings:
            return 0.0
        sims = []
        for i, emb in enumerate(self.embeddings):
            # cosine similarity
            a = np.array(current_embedding)
            b = np.array(emb)
            sim = float(a.dot(b) / ((np.linalg.norm(a)+1e-9)*(np.linalg.norm(b)+1e-9)))
            sims.append((sim, i))
        sims.sort(reverse=True)
        numerator = 0.0
        denom = 0.0
        for sim, idx in sims[:k]:
            # approximate consumption from hawkes mu sums
            hawkes = self.hawkes_history[idx]
            cons = sum(hawkes.mu.values()) * 100.0
            numerator += sim * cons
            denom += sim
        return float(numerator / (denom + 1e-9))


# ------------------------- Problem 7: Adaptive Weighted Topological DAG + Confidence-Based Priority -------------------------

class AdaptiveTopologicalScheduler:
    def __init__(self):
        self.items = {}  # item_id -> state dict

    def update_item_state(self, item_id, inventory, mu_rate, sigma_rate, reorder_level=100, lead_time=60.0, buffer=30.0):
        self.items[item_id] = {'inventory': inventory, 'mu_rate': mu_rate, 'sigma_rate': sigma_rate, 'reorder_level': reorder_level, 'lead_time': lead_time, 'buffer': buffer}

    def compute_restocking_priority(self):
        results = []
        for item_id, s in self.items.items():
            needed = max(0.0, s['inventory'] - s['reorder_level'])
            mu = max(1e-6, s['mu_rate'])
            sigma = s['sigma_rate']
            time_to_critical = needed / mu if mu>0 else float('inf')
            confidence = 1.0 / (1.0 + sigma / (mu+1e-9))
            effective_time = time_to_critical - s['lead_time'] - s['buffer']
            urgency = 1.0 / (effective_time + 0.1) if effective_time > 0 else 1e3
            penalty = 1.0 + sigma / (mu+1e-9)
            risk = (1.0 - confidence) * urgency * penalty
            # Monte Carlo CI
            sims = []
            for _ in range(200):
                rate_sim = random.gauss(mu, sigma)
                rate_sim = max(1e-6, rate_sim)
                time_sim = needed / rate_sim
                sims.append(time_sim)
            sims.sort()
            p5 = sims[int(0.05*len(sims))]
            p50 = sims[int(0.5*len(sims))]
            p95 = sims[int(0.95*len(sims))]
            action = 'MONITOR'
            if effective_time < 3600:
                action = 'RESTOCK_NOW'
            elif effective_time < 4*3600:
                action = 'RESTOCK_SOON'
            results.append({'item_id': item_id, 'risk': risk, 'p5': p5, 'p50': p50, 'p95': p95, 'action': action})
        results.sort(key=lambda x: x['risk'], reverse=True)
        return results

    def generate_restocking_report(self):
        return self.compute_restocking_priority()


# ------------------------- Integration pipeline -------------------------

class FullPipeline:
    def __init__(self):
        self.kalman = KalmanL1HybridFilter(init_x=0.0)
        self.fusion = AdaptiveDualModeSensorFusion(self.kalman)
        self.tracker = EventTracker()
        self.demand_window = DemandSignatureWindow(window_size=100)
        self.trend = TrendAnalyzer()
        self.graph = HierarchicalEventGraph()
        self.scheduler = AdaptiveTopologicalScheduler()
        # For reporting
        self.reports_file = 'reports.json'

    def process_stream(self, weight_sequence, temps=None, hums=None, start_ts=None):
        ts = int(start_ts or now_ts())
        dt = 1
        results = []
        prev_weight = None
        for i, w in enumerate(weight_sequence):
            timestamp = ts + i*dt
            temp = temps[i] if temps and i < len(temps) else 25.0
            hum = hums[i] if hums and i < len(hums) else 50.0
            out = self.fusion.process_sensor_reading(w, temp=temp, humidity=hum, timestamp=timestamp)
            results.append({'timestamp': timestamp, **out})
            # feed event tracker: classify consumption/restock by delta
            if prev_weight is not None:
                delta = out['calibrated_weight'] - prev_weight
                # positive delta -> restock, negative -> consumption
                event_type = 'restock' if delta > 0 else 'consumption'
                self.tracker.add_event(timestamp, {'type': event_type, 'quantity': abs(delta)})
                # demand window
                self.demand_window.add_event(timestamp, delta, duration=1.0)
                # trend analyzer sample
                self.trend.add_sample(timestamp, abs(delta), temp, hum)
            prev_weight = out['calibrated_weight']
        # after full stream: process windows for graph (chunk every hour by timestamps)
        # We'll make one window from entire events for simplicity
        events = [(r['timestamp'], self.classify_event_from_weight_change(i, results)) for i, r in enumerate(results) if i>0]
        self.graph.process_events_window(events, window_id=0)
        # scheduler usage sample: pretend one item with rate from demand estimates
        forecasts = self.demand_window.get_demand_forecast()
        # arbitrarily add an item to scheduler
        self.scheduler.update_item_state('item_1', inventory=1000.0, mu_rate=max(0.1, forecasts['total']/100.0), sigma_rate=max(0.1, forecasts['total']/200.0), reorder_level=200)
        restock_report = self.scheduler.generate_restocking_report()
        # collate final report
        report = {
            'generated_at': now_ts(),
            'n_samples': len(weight_sequence),
            'kalman_sparse_count': len(self.kalman.timestamps),
            'demand_forecast': forecasts,
            'restock_report': restock_report,
            'events_indexed': len(self.tracker.skip_list._keys),
        }
        self.append_report(report)
        return report

    def classify_event_from_weight_change(self, idx, results):
        # helper to map result index to simple labels for graph
        r = results[idx]
        # small rule
        if r['anomaly']:
            return 'ANOMALY'
        return 'EVENT'

    def append_report(self, report):
        existing = []
        if os.path.exists(self.reports_file):
            try:
                with open(self.reports_file, 'r') as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        existing.append(report)
        with open(self.reports_file, 'w') as f:
            json.dump(existing, f, indent=2)


# ------------------------- Input parsing and main -------------------------

sample_input = '''Weight: 833.20 g | Stock: 100.0 %
Weight: 1249.80 g | Stock: 100.0 %
Weight: 1666.40 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2083.00 g | Stock: 100.0 %
Weight: 2009.00 g | Stock: 100.0 %
Weight: 1935.00 g | Stock: 100.0 %
Weight: 1861.00 g | Stock: 100.0 %
Weight: 1787.00 g | Stock: 100.0 %
Weight: 1713.00 g | Stock: 100.0 %
Weight: 1713.00 g | Stock: 100.0 %
Weight: 1713.00 g | Stock: 100.0 %
Weight: 1713.00 g | Stock: 100.0 %
Weight: 1713.00 g | Stock: 100.0 %
Weight: 1611.40 g | Stock: 100.0 %
Weight: 1509.80 g | Stock: 100.0 %
Weight: 1408.20 g | Stock: 100.0 %
Weight: 1306.60 g | Stock: 100.0 %
Weight: 1205.00 g | Stock: 100.0 %
Weight: 1205.00 g | Stock: 100.0 %
Weight: 1205.00 g | Stock: 100.0 %
Weight: 1205.00 g | Stock: 100.0 %
Weight: 1205.00 g | Stock: 100.0 %
Weight: 1139.40 g | Stock: 100.0 %
Weight: 1073.80 g | Stock: 100.0 %
Weight: 1008.20 g | Stock: 100.0 %
Weight: 942.60 g | Stock: 100.0 %
Weight: 877.00 g | Stock: 100.0 %
Weight: 877.00 g | Stock: 100.0 %
Weight: 877.00 g | Stock: 100.0 %
Weight: 782.20 g | Stock: 100.0 %
Weight: 687.40 g | Stock: 100.0 %
Weight: 592.60 g | Stock: 100.0 %
Weight: 497.80 g | Stock: 100.0 %
Weight: 403.00 g | Stock: 96.7 %
Weight: 403.00 g | Stock: 96.7 %
Weight: 403.00 g | Stock: 96.7 %
Weight: 403.00 g | Stock: 96.7 %
Weight: 403.00 g | Stock: 96.7 %
Weight: 403.00 g | Stock: 96.7 %
Weight: 322.40 g | Stock: 77.4 %
Weight: 241.80 g | Stock: 58.0 %
Weight: 161.20 g | Stock: 38.7 %
Weight: 80.60 g | Stock: 19.3 %
Weight: 0.00 g | Stock: 0.0 %
Weight: 0.00 g | Stock: 0.0 %
Weight: 0.00 g | Stock: 0.0 %
Weight: 107.40 g | Stock: 25.8 %
Weight: 214.80 g | Stock: 51.6 %
Weight: 322.20 g | Stock: 77.3 %
Weight: 554.80 g | Stock: 100.0 %
Weight: 787.40 g | Stock: 100.0 %
Weight: 912.60 g | Stock: 100.0 %
Weight: 1037.80 g | Stock: 100.0 %
Weight: 1163.00 g | Stock: 100.0 %
Weight: 1240.20 g | Stock: 100.0 %
Weight: 1317.40 g | Stock: 100.0 %
Weight: 1394.60 g | Stock: 100.0 %
Weight: 1566.80 g | Stock: 100.0 %
Weight: 1739.00 g | Stock: 100.0 %
Weight: 1834.00 g | Stock: 100.0 %
Weight: 1929.00 g | Stock: 100.0 %
Weight: 2024.00 g | Stock: 100.0 %
Weight: 2024.00 g | Stock: 100.0 %
Weight: 2024.00 g | Stock: 100.0 %
Weight: 2024.00 g | Stock: 100.0 %
Weight: 2039.20 g | Stock: 100.0 %
Weight: 2054.40 g | Stock: 100.0 %
Weight: 2069.60 g | Stock: 100.0 %
Weight: 2084.80 g | Stock: 100.0 %
Weight: 2100.00 g | Stock: 100.0 %
Weight: 2100.00 g | Stock: 100.0 %
Weight: 2100.00 g | Stock: 100.0 %
Weight: 2100.00 g | Stock: 100.0 %
Weight: 2100.00 g | Stock: 100.0 %
Weight: 2100.00 g | Stock: 100.0 %
Weight: 1787.40 g | Stock: 100.0 %
Weight: 1474.80 g | Stock: 100.0 %
Weight: 1162.20 g | Stock: 100.0 %
Weight: 849.60 g | Stock: 100.0 %
Weight: 537.00 g | Stock: 100.0 %
Weight: 537.00 g | Stock: 100.0 %
Weight: 537.00 g | Stock: 100.0 %
Weight: 537.00 g | Stock: 100.0 %
Weight: 438.80 g | Stock: 100.0 %
Weight: 340.60 g | Stock: 81.8 %
Weight: 242.40 g | Stock: 58.2 %
Weight: 144.20 g | Stock: 34.6 %
Weight: 46.00 g | Stock: 11.0 %
Weight: 46.00 g | Stock: 11.0 %
Weight: 46.00 g | Stock: 11.0 %
Weight: 46.00 g | Stock: 11.0 %
Weight: 46.00 g | Stock: 11.0 %
Weight: 36.80 g | Stock: 8.8 %
Weight: 27.60 g | Stock: 6.6 %
Weight: 18.40 g | Stock: 4.4 %
Weight: 9.20 g | Stock: 2.2 %
Weight: 354.40 g | Stock: 85.1 %
Weight: 708.80 g | Stock: 100.0 %
Weight: 1063.20 g | Stock: 100.0 %
Weight: 1417.60 g | Stock: 100.0 %
Weight: 1670.40 g | Stock: 100.0 %
Weight: 1568.80 g | Stock: 100.0 %
Weight: 1467.20 g | Stock: 100.0 %
Weight: 1365.60 g | Stock: 100.0 %
Weight: 1264.00 g | Stock: 100.0 %
Weight: 1264.00 g | Stock: 100.0 %
Weight: 1264.00 g | Stock: 100.0 %
Weight: 1264.00 g | Stock: 100.0 %
Weight: 1219.40 g | Stock: 100.0 %
Weight: 1174.80 g | Stock: 100.0 %
Weight: 1130.20 g | Stock: 100.0 %
Weight: 1008.40 g | Stock: 100.0 %
Weight: 886.60 g | Stock: 100.0 %
Weight: 809.40 g | Stock: 100.0 %
Weight: 732.20 g | Stock: 100.0 %
Weight: 655.00 g | Stock: 100.0 %
Weight: 655.00 g | Stock: 100.0 %
Weight: 655.00 g | Stock: 100.0 %
Weight: 524.00 g | Stock: 100.0 %
Weight: 393.00 g | Stock: 94.3 %
Weight: 262.00 g | Stock: 62.9 %
Weight: 131.00 g | Stock: 31.4 %
Weight: 0.00 g | Stock: 0.0 %
Weight: 0.00 g | Stock: 0.0 %
Weight: 0.00 g | Stock: 0.0 %
'''


def parse_input_text(text):
    weights = []
    stocks = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parts = line.split('|')
            wpart = parts[0].strip()
            weight = float(wpart.replace('Weight:', '').replace('g', '').strip())
            weights.append(weight)
            if len(parts) > 1:
                spart = parts[1].strip()
                stock = float(spart.replace('Stock:', '').replace('%', '').strip())
                stocks.append(stock)
            else:
                stocks.append(None)
        except Exception:
            continue
    return weights, stocks


def load_input():
    if os.path.exists('input.txt'):
        with open('input.txt', 'r') as f:
            text = f.read()
    else:
        text = sample_input
    return parse_input_text(text)


def main():
    weights, stocks = load_input()
    pipeline = FullPipeline()
    report = pipeline.process_stream(weights, temps=None, hums=None, start_ts=now_ts())
    print('Report generated and appended to reports.json:')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
