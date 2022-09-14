from typing import List, Any
from dataclasses import dataclass, field
from omegaconf import OmegaConf, MISSING
from hydra import compose, initialize
from hydra.core.config_store import ConfigStore

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "common"))
from common_config import GCPConfig, NeptuneConfig


@dataclass
class DataConfig:
    symbol: str = "usdjpy"
    first_year: int = 2020
    first_month: int = 11
    last_year: int = 2020
    last_month: int = 12


@dataclass
class FeatureConfig:
    timings: List[str] = field(default_factory=lambda: ["high", "low", "close"])
    freqs: List[str] = field(default_factory=lambda: ["1min", "5min", "15min", "1h", "4h"])
    sma_timing: str = "close"
    sma_window_sizes: List[int] = field(default_factory=lambda: [10])
    sma_window_size_center: int = 10
    sma_frac_ndigits: int = 2
    lag_max: int = 5
    start_hour: int = 2
    end_hour: int = 22


@dataclass
class CtiricalLabelConfig:
    label_type: str = "critical"
    # この値以上に上昇するならエントリーする
    thresh_entry: float = 0.05
    # この値を以下の下落であれば持ち続ける
    thresh_hold: float = 0.025


@dataclass
class SMADiffLabelConfig:
    label_type: str = "smadiff"
    window_size_before: int = 10
    window_size_after: int = 10
    thresh_entry: float = 0.025
    thresh_hold: float = 0.0


@dataclass
class FutureLabelConfig:
    label_type: str = "future"
    future_step: int = 10
    thresh_entry: float = 0.05
    thresh_hold: float = 0.0


@dataclass
class Dummy1LabelConfig:
    label_type: str = "dummy1"


@dataclass
class Dummy2LabelConfig:
    label_type: str = "dummy2"


@dataclass
class Dummy3LabelConfig:
    label_type: str = "dummy3"


@dataclass
class LGBMModelConfig:
    model_type: str = "lgbm"
    objective: str = "binary"
    num_iterations: int = 10
    num_leaves: int = 31
    learning_rate: float = 0.1
    lambda_l1: float = 0.0
    lambda_l2: float = 0.0
    feature_fraction: float = 1.0
    bagging_fraction: float = 1.0
    pos_bagging_fraction: float = 1.0
    neg_bagging_fraction: float = 1.0
    bagging_freq: int = 0
    is_unbalance: bool = False
    scale_pos_weight: float = 1.0
    verbosity: int = 1


@dataclass
class CNNModelConfig:
    model_type: str = "cnn"
    num_epochs: int = 1
    learning_rate: float = 1.0e-3
    pos_weight: float = 1.0
    batch_size: int = 256

    out_channels_list: List[int] = field(default_factory=lambda: [20, 40, 20])
    kernel_size_list: List[int] = field(default_factory=lambda: [5, 5, 5])
    max_pool_list: List[bool] = field(default_factory=lambda: [True, True, True])
    base_out_dim: int = 128
    hidden_dim_list: List[int] = field(default_factory=lambda: [256, 128])
    cnn_batch_norm: bool = True
    fc_batch_norm: bool = False
    cnn_dropout: float = 0.
    fc_dropout: float = 0.
    eval_on_valid: bool = True


@dataclass
class TrainConfig:
    defaults: List[Any] = field(default_factory=lambda: [
        "_self_",
        {"label": "critical"},
        {"model": "lgbm"},
    ])

    random_seed: int = 123
    valid_ratio: float = 0.1
    save_model: bool = True
    gcp: GCPConfig = GCPConfig()
    neptune: NeptuneConfig = NeptuneConfig()
    data: DataConfig = DataConfig()
    feature: FeatureConfig = FeatureConfig()
    label: Any = MISSING
    model: Any = MISSING


@dataclass
class EvalConfig:
    start_hour: int = 2
    end_hour: int = 22
    thresh_loss_cut: float = 0.05
    simulate_timing: str = "open"
    spread: float = 0.02
    percentile_entry_list: List[int] = field(default_factory=lambda: [75, 90, 95])
    percentile_exit_list: List[int] = field(default_factory=lambda: [75, 90, 95])

    gcp: GCPConfig = GCPConfig()
    neptune: NeptuneConfig = NeptuneConfig()
    data: DataConfig = DataConfig()


def validate_train_config(config: OmegaConf):
    assert "1min" in config.feature.freqs
    assert config.feature.sma_window_size_center in config.feature.sma_window_sizes


def get_train_config(argv: List[str] = None):
    cs = ConfigStore.instance(version_base=None)
    cs.store(name="data", node=DataConfig)
    cs.store(name="feature", node=FeatureConfig)
    cs.store(group="label", name="critical", node=CtiricalLabelConfig)
    cs.store(group="label", name="smadiff", node=SMADiffLabelConfig)
    cs.store(group="label", name="future", node=FutureLabelConfig)
    cs.store(group="label", name="dummy1", node=Dummy1LabelConfig)
    cs.store(group="label", name="dummy2", node=Dummy2LabelConfig)
    cs.store(group="label", name="dummy3", node=Dummy3LabelConfig)
    cs.store(group="model", name="lgbm", node=LGBMModelConfig)
    cs.store(group="model", name="cnn", node=CNNModelConfig)
    cs.store(name="train", node=TrainConfig)

    if argv is None:
        argv = sys.argv[1:]

    with initialize(version_base=None):
        config = compose(config_name="train", overrides=argv)

    OmegaConf.resolve(config)
    validate_train_config(config)
    return config

