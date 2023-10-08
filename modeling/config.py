import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, List

from hydra import compose, initialize
from hydra.core.config_store import ConfigStore
from omegaconf import MISSING, OmegaConf

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
class CriticalConfig:
    thresh_hold: float = 0.02
    # TODO: FeatureConfig に置く方がいい
    prev_max: int = 4


@dataclass
class FeatureConfig:
    freqs: List[str] = field(default_factory=lambda: ["1min", "15min", "1h", "1d"])
    main_timing: str = "close"
    candle_usage: str = "sequential"
    sma_usage: str = "sequential"
    sma_window_sizes: List[int] = field(default_factory=lambda: [5, 8, 13])
    sma_window_size_center: int = 5
    sigma_usage: str = "sequential"
    sigma_window_size: int = 9
    macd_usage: str = "sequential"
    macd_ema_window_size_short: int = 9
    macd_ema_window_size_long: int = 26
    macd_sma_window_size: int = 9
    stochastics_usage: str = "sequential"
    stochastics_k_window_size: int = 9
    stochastics_d_window_size: int = 3
    stochastics_sd_window_size: int = 3
    rsi_usage: str = "sequential"
    rsi_window_size: int = 14
    sma_frac_usage: str = "continuous"
    sma_frac_ndigits: int = 2
    critical_values_usage: str = "continuous"
    critical_idxs_usage: str = "continuous"
    critical_trends_usage: str = ""
    time_usage: str = "continuous"
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
class Ctirical2LabelConfig:
    label_type: str = "critical2"
    thresh_entry: float = 0.05


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
    future_step_min: int = 8
    future_step_max: int = 12
    thresh_entry: float = 0.05
    thresh_hold: float = 0.0


@dataclass
class SMATrendLabelConfig:
    label_type: str = "smatrend"
    window_size: int = 9
    step_before: int = 5
    step_after: int = 5
    thresh_entry: float = 0.025


@dataclass
class GainLabelConfig:
    label_type: str = "gain"
    future_step_min: int = 8
    future_step_max: int = 12
    entry_bias: float = -0.02
    exit_bias: float = 0.0


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
class BinaryLossConfig:
    loss_type: str = "binary"
    pos_weight: float = 1.0


@dataclass
class GainLossConfig:
    loss_type: str = "gain"


@dataclass
class FocalLossConfig:
    loss_type: str = "focal"
    gamma: float = 1.0


@dataclass
class LGBMModelConfig:
    defaults: List[Any] = field(
        default_factory=lambda: [
            "_self_",
            {"loss": "binary"},
        ]
    )

    model_type: str = "lgbm"
    loss: Any = MISSING
    num_iterations: int = 10
    num_leaves: int = 31
    learning_rate: float = 0.1
    lambda_l1: float = 0.0
    lambda_l2: float = 0.0
    min_data_in_leaf: int = 20
    feature_fraction: float = 1.0
    bagging_fraction: float = 1.0
    pos_bagging_fraction: float = 1.0
    neg_bagging_fraction: float = 1.0
    bagging_freq: int = 0
    is_unbalance: bool = False
    verbosity: int = 1
    force_row_wise: bool = True


@dataclass
class CNNModelConfig:
    defaults: List[Any] = field(
        default_factory=lambda: [
            "_self_",
            {"loss": "binary"},
        ]
    )

    model_type: str = "cnn"
    loss: Any = MISSING
    num_epochs: int = 1
    learning_rate: float = 1.0e-3
    weight_decay: float = 0.0
    batch_size: int = 256

    out_channels_list: List[int] = field(default_factory=lambda: [20, 40, 20])
    kernel_size_list: List[int] = field(default_factory=lambda: [5, 5, 5])
    max_pool_list: List[bool] = field(default_factory=lambda: [True, True, True])
    base_out_dim: int = 128
    hidden_dim_list: List[int] = field(default_factory=lambda: [256, 128])
    cnn_batch_norm: bool = True
    fc_batch_norm: bool = False
    cnn_dropout: float = 0.0
    fc_dropout: float = 0.0
    eval_on_valid: bool = True


@dataclass
class TrainConfig:
    defaults: List[Any] = field(
        default_factory=lambda: [
            "_self_",
            {"label": "critical"},
            {"model": "lgbm"},
        ]
    )

    random_seed: int = 123
    valid_ratio: float = 0.1
    retrain: bool = True
    gcp: GCPConfig = GCPConfig()
    neptune: NeptuneConfig = NeptuneConfig()
    data: DataConfig = DataConfig()
    critical: CriticalConfig = CriticalConfig()
    feature: FeatureConfig = FeatureConfig()
    label: Any = MISSING
    model: Any = MISSING


@dataclass
class EvalConfig:
    model_type: str = "lgbm"
    start_hour: int = 2
    end_hour: int = 22
    thresh_loss_cut: float = 0.05
    simulate_timing: str = "open"
    spread: float = 0.02
    percentile_entry_list: List[float] = field(default_factory=lambda: [75, 90, 95])
    percentile_exit_list: List[float] = field(default_factory=lambda: [75, 90, 95])

    gcp: GCPConfig = GCPConfig()
    neptune: NeptuneConfig = NeptuneConfig()
    data: DataConfig = DataConfig()


cs = ConfigStore.instance(version_base=None)
cs.store(name="data", node=DataConfig)
cs.store(name="feature", node=FeatureConfig)
cs.store(name="critical", node=CriticalConfig)
cs.store(group="label", name="critical", node=CtiricalLabelConfig)
cs.store(group="label", name="critical2", node=Ctirical2LabelConfig)
cs.store(group="label", name="smadiff", node=SMADiffLabelConfig)
cs.store(group="label", name="future", node=FutureLabelConfig)
cs.store(group="label", name="smatrend", node=SMATrendLabelConfig)
cs.store(group="label", name="gain", node=GainLabelConfig)
cs.store(group="label", name="dummy1", node=Dummy1LabelConfig)
cs.store(group="label", name="dummy2", node=Dummy2LabelConfig)
cs.store(group="label", name="dummy3", node=Dummy3LabelConfig)
cs.store(group="model", name="lgbm", node=LGBMModelConfig)
cs.store(group="model", name="cnn", node=CNNModelConfig)
cs.store(group="model/loss", name="binary", node=BinaryLossConfig)
cs.store(group="model/loss", name="gain", node=GainLossConfig)
cs.store(group="model/loss", name="focal", node=FocalLossConfig)
cs.store(name="train", node=TrainConfig)
cs.store(name="eval", node=EvalConfig)


def validate_train_config(config: OmegaConf):
    assert "1min" in config.feature.freqs
    assert config.feature.sma_window_size_center in config.feature.sma_window_sizes
    assert bool(config.model.loss.loss_type == "gain") == bool(
        config.label.label_type == "gain"
    )


def get_train_config(argv: List[str] = None):
    if argv is None:
        argv = sys.argv[1:]

    with initialize(version_base=None):
        config = compose(config_name="train", overrides=argv)

    OmegaConf.resolve(config)
    validate_train_config(config)
    return config


def get_eval_config(argv: List[str] = None):
    if argv is None:
        argv = sys.argv[1:]

    with initialize(version_base=None):
        config = compose(config_name="eval", overrides=argv)

    OmegaConf.resolve(config)
    return config
