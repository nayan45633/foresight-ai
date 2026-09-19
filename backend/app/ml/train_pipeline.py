"""Foresight AI - Master Training & Calibration Pipeline Execution Script.

Generates a realistic temporal flow progression benchmark, trains multi-horizon
gradient-boosted forecasters, applies probability calibration, evaluates against baselines,
and outputs model artifacts to disk.
"""

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Dict, List, Tuple
import numpy as np
from app.core.logging import logger, setup_logging
from app.ml.contracts import FlowDirectionEnum, FlowRecord, ProtocolEnum
from app.ml.dataset_builder import ForecastingDatasetBuilder
from app.ml.trainer import ModelTrainer
from app.telemetry.window_generator import SlidingWindowGenerator


def generate_benchmark_timeline(
    total_hours: int = 24,
    flows_per_minute: int = 35,
    random_seed: int = 42,
) -> Tuple[List[FlowRecord], List[Dict[str, Any]]]:
    """Generates a continuous 24-hour chronological sequence of network flows with multi-stage attack progressions across Train, Val, and Test."""
    np.random.seed(random_seed)
    base_time = datetime(2026, 9, 18, 0, 0, 0, tzinfo=timezone.utc)
    total_minutes = total_hours * 60
    
    flows: List[FlowRecord] = []
    ground_truth_events: List[Dict[str, Any]] = []

    # Scheduled multi-stage attack campaigns spanning all chronological partitions:
    # --- Train Partition (0h - 16.8h / 0 - 1008 mins) ---
    # Campaign 1: Port Scan Reconnaissance at Hour 2 (min 120)
    # Campaign 2: SYN Flood DDoS at Hour 6 (min 360)
    # Campaign 3: SSH Brute Force at Hour 10 (min 600)
    # Campaign 4: Data Exfiltration at Hour 14 (min 840)
    # --- Validation Partition (16.8h - 20.4h / 1008 - 1224 mins) ---
    # Campaign 5: SYN Flood DDoS at Hour 18 (min 1080)
    # --- Test Partition (20.4h - 24.0h / 1224 - 1440 mins) ---
    # Campaign 6: Port Scan Reconnaissance + Exfiltration at Hour 22 (min 1320)
    attack_schedules = [
        {"start_min": 120, "duration_min": 25, "type": "Port Scan Reconnaissance", "severity": "MEDIUM"},
        {"start_min": 360, "duration_min": 35, "type": "Distributed Denial of Service", "severity": "CRITICAL"},
        {"start_min": 600, "duration_min": 25, "type": "Brute Force Authentication", "severity": "HIGH"},
        {"start_min": 840, "duration_min": 30, "type": "Data Exfiltration", "severity": "HIGH"},
        {"start_min": 1080, "duration_min": 35, "type": "Distributed Denial of Service", "severity": "CRITICAL"},
        {"start_min": 1320, "duration_min": 30, "type": "Data Exfiltration", "severity": "HIGH"},
    ]

    for att in attack_schedules:
        ground_truth_events.append({
            "timestamp": base_time + timedelta(minutes=att["start_min"]),
            "threat_type": att["type"],
            "severity": att["severity"],
            "duration_minutes": att["duration_min"],
        })

    logger.info(f"Synthesizing {total_hours} hours of chronological flow telemetry with {len(attack_schedules)} attack campaigns...")

    for minute in range(total_minutes):
        t_curr = base_time + timedelta(minutes=minute)
        
        # Check active attack stage
        active_att = next(
            (a for a in attack_schedules if a["start_min"] <= minute < (a["start_min"] + a["duration_min"])),
            None
        )
        
        # Check pre-attack reconnaissance phase (5-15 mins before attack)
        pre_att = next(
            (a for a in attack_schedules if (a["start_min"] - 15) <= minute < a["start_min"]),
            None
        )

        n_flows = flows_per_minute
        if active_att:
            if active_att["type"] == "Distributed Denial of Service":
                n_flows = flows_per_minute * 4  # Volumetric spike
            elif active_att["type"] == "Port Scan Reconnaissance":
                n_flows = flows_per_minute * 2
        elif pre_att:
            n_flows = int(flows_per_minute * 1.5)  # Subtle precursor build-up

        for i in range(n_flows):
            sec_offset = np.random.uniform(0, 59.9)
            flow_ts = t_curr + timedelta(seconds=sec_offset)

            # Benign baseline characteristics
            src_ip = f"192.168.1.{np.random.randint(10, 200)}"
            dst_ip = f"10.0.0.{np.random.randint(1, 10)}"
            src_port = np.random.randint(1024, 65535)
            dst_port = np.random.choice([80, 443, 8080, 53, 22], p=[0.4, 0.4, 0.1, 0.05, 0.05])
            proto = ProtocolEnum.TCP
            duration_ms = float(np.random.exponential(150.0))
            pkts = int(np.random.geometric(0.1))
            bytes_cnt = pkts * np.random.randint(64, 1450)
            flags = "SYN,ACK" if np.random.rand() > 0.3 else "ACK"

            # Inject attack behavior signatures
            if active_att:
                if active_att["type"] == "Distributed Denial of Service":
                    src_ip = f"45.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}"
                    dst_port = 443
                    flags = "SYN"
                    pkts = np.random.randint(1, 3)
                    duration_ms = float(np.random.uniform(5.0, 30.0))
                elif active_att["type"] == "Port Scan Reconnaissance":
                    src_ip = "192.168.1.99"
                    dst_port = np.random.randint(1, 1024)  # Port scanning
                    flags = "SYN"
                elif active_att["type"] == "Brute Force Authentication":
                    dst_port = 22
                    flags = "SYN,ACK,PSH"
                    pkts = np.random.randint(10, 30)
                elif active_att["type"] == "Data Exfiltration":
                    dst_port = 443
                    bytes_cnt = np.random.randint(50000, 200000)  # Huge volume

            # Precursor subtle anomaly build-up (port exploration & SYN build-up)
            elif pre_att:
                if pre_att["type"] == "Distributed Denial of Service":
                    if np.random.rand() > 0.5:
                        flags = "SYN"
                        src_ip = f"45.33.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}"
                elif pre_att["type"] == "Port Scan Reconnaissance":
                    if np.random.rand() > 0.6:
                        dst_port = np.random.randint(1, 1000)

            flow_rec = FlowRecord(
                timestamp=flow_ts,
                source_ip=src_ip,
                destination_ip=dst_ip,
                source_port=src_port,
                destination_port=dst_port,
                protocol=proto,
                flow_duration_ms=duration_ms,
                packet_count=pkts,
                byte_count=bytes_cnt,
                packet_rate=float(pkts) / (duration_ms / 1000.0 + 0.001),
                byte_rate=float(bytes_cnt) / (duration_ms / 1000.0 + 0.001),
                tcp_flags=flags,
                direction=FlowDirectionEnum.INGRESS,
            )
            flows.append(flow_rec)

    flows.sort(key=lambda f: f.timestamp)
    logger.info(f"Generated {len(flows)} chronological flow records across {total_hours} hours.")
    return flows, ground_truth_events


def run_training_pipeline() -> Tuple[ModelTrainer, Dict[str, Any]]:
    """Master routine executing full training, calibration, evaluation, and artifact saving."""
    setup_logging()
    logger.info("=================================================================")
    logger.info("FORESIGHT AI — MASTER ML TRAINING & CALIBRATION PIPELINE")
    logger.info("=================================================================")

    # 1. Generate chronological flow stream
    flows, ground_truth_events = generate_benchmark_timeline(total_hours=24, flows_per_minute=35, random_seed=42)

    # 2. Slice into sliding temporal windows
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)
    logger.info(f"Generated {len(windows)} sliding temporal windows.")

    # 3. Construct chronological dataset
    builder = ForecastingDatasetBuilder(rolling_context_steps=4)
    dataset = builder.build_dataset_from_windows(windows, ground_truth_events)
    logger.info(f"Dataset constructed with shape: {dataset.X.shape} (28-D Base + 8-D Derivatives = 36 Features)")

    # 4. Chronological Splitting: 70% Train, 15% Val, 15% Test
    train_set, val_set, test_set = builder.chronological_train_val_test_split(dataset, train_ratio=0.70, val_ratio=0.15)
    logger.info(f"Chronological Split: Train={train_set.sample_count}, Val={val_set.sample_count}, Test={test_set.sample_count}")

    # 5. Initialize Trainer
    trainer = ModelTrainer(model_version="v1.0.0-temporal-gbm", random_state=42)

    # 6. Evaluate Baselines
    logger.info("Evaluating baseline models (Majority, Logistic Regression, Random Forest)...")
    baseline_res = trainer.evaluate_baselines(train_set, val_set)

    # 7. Train Candidate Production Model & Apply Probability Calibration
    logger.info("Training HistGradientBoosting forecasters and applying Platt Sigmoid calibration...")
    val_metrics = trainer.train_and_calibrate(train_set, val_set)

    # 8. Final Evaluation on Held-Out Test Set (Evaluated ONCE)
    logger.info("Evaluating final calibrated model bundle on held-out test partition...")
    test_metrics = trainer.evaluate_test_set_once(test_set)

    # 9. Save Artifacts
    artifact_path = trainer.save_artifacts(artifact_dir="artifacts/models")

    # Output concise summary table
    print("\n" + "=" * 80)
    print("FORESIGHT AI — MULTI-HORIZON EVALUATION RESULTS (HELD-OUT TEST SET)")
    print("=" * 80)
    print(f"{'Horizon':<10} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'PR-AUC':<10} | {'ROC-AUC':<10} | {'Brier Score':<12} | {'ECE':<8}")
    print("-" * 80)
    for h, m in test_metrics.items():
        print(f"{str(h)+'m':<10} | {m['precision']:<10.4f} | {m['recall']:<10.4f} | {m['f1']:<10.4f} | {m['pr_auc']:<10.4f} | {m['roc_auc']:<10.4f} | {m['brier_score']:<12.4f} | {m['expected_calibration_error']:<8.4f}")
    print("=" * 80 + "\n")

    return trainer, test_metrics


if __name__ == "__main__":
    run_training_pipeline()
