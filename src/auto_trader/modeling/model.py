from typing import Any, Optional, cast

import lightning.pytorch as pl
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from lightning.pytorch.utilities.types import LRSchedulerConfig
from numpy.typing import NDArray

from auto_trader.modeling import data


class PeriodicActivation(nn.Module):
    def __init__(self, num_coefs: int, sigma: float) -> None:
        super().__init__()
        self.params = nn.Parameter(torch.randn(num_coefs) * sigma)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        assert x.shape[-1] == 1
        # (...batch, num_coefs)
        x = x * self.params * 2 * np.pi
        # (...batch, num_coefs*2)
        return torch.cat([torch.sin(x), torch.cos(x)], dim=-1)


def build_fc_layer(
    input_dim: int,
    hidden_dims: list[int],
    batchnorm: bool,
    dropout: float,
    output_dim: Optional[int] = None,
) -> nn.Sequential:
    layers: list[nn.Module] = []
    for hidden_dim in hidden_dims:
        layers.append(nn.Linear(input_dim, hidden_dim, bias=not batchnorm))
        if batchnorm:
            layers.append(nn.BatchNorm1d(hidden_dim))
        layers.append(nn.ReLU())
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        input_dim = hidden_dim

    if output_dim is not None:
        layers.append(nn.Linear(input_dim, output_dim))

    return nn.Sequential(*layers)


class Net(nn.Module):
    def __init__(
        self,
        feature_stats: dict[data.FeatureName, data.FeatureStats],
        hist_len: int,
        numerical_emb_dim: int,
        periodic_activation_num_coefs: int,
        periodic_activation_sigma: float,
        categorical_emb_dim: int,
        out_channels: list[int],
        kernel_sizes: list[int],
        strides: list[int],
        batchnorm: bool,
        dropout: float,
        head_hidden_dims: list[int],
        head_batchnorm: bool,
        head_dropout: float,
        head_output_dim: int,
    ):
        super().__init__()

        self.emb_feature = nn.ModuleDict()
        emb_total_dim = 0
        for name, stats in feature_stats.items():
            if isinstance(stats, data.ContinuousFeatureStats):
                self.emb_feature[name] = nn.Sequential(
                    PeriodicActivation(
                        periodic_activation_num_coefs, periodic_activation_sigma
                    ),
                    nn.Linear(periodic_activation_num_coefs * 2, numerical_emb_dim),
                    nn.ReLU(),
                )
                emb_total_dim += numerical_emb_dim
            elif isinstance(stats, data.CategoricalFeatureStats):
                self.emb_feature[name] = nn.Embedding(
                    # vocab_size は OOV token
                    num_embeddings=stats.vocab_size + 1,
                    embedding_dim=categorical_emb_dim,
                )
                emb_total_dim += categorical_emb_dim

        self.conv = nn.Sequential()
        length = hist_len
        for i in range(len(out_channels)):
            self.conv.append(
                nn.Conv1d(
                    in_channels=emb_total_dim if i == 0 else out_channels[i - 1],
                    out_channels=out_channels[i],
                    kernel_size=kernel_sizes[i],
                    stride=strides[i],
                    bias=not batchnorm,
                )
            )
            if batchnorm:
                self.conv.append(nn.BatchNorm1d(out_channels[i]))
            self.conv.append(nn.ReLU())
            if dropout:
                self.conv.append(nn.Dropout(dropout))

            length = int((length - kernel_sizes[i]) / strides[i] + 1)

        self.head = build_fc_layer(
            input_dim=length * out_channels[-1],
            hidden_dims=head_hidden_dims,
            batchnorm=head_batchnorm,
            dropout=head_dropout,
            output_dim=head_output_dim,
        )

    def forward(self, features: dict[data.FeatureName, torch.Tensor]) -> torch.Tensor:
        # (batch, hist_len, emb_total_dim)
        x = torch.cat(
            [
                self.emb_feature[feature_name](features[feature_name])
                for feature_name in features
            ],
            dim=2,
        )
        # (batch, out_channels[-1], length)
        x = self.conv(x.transpose(1, 2))
        # (batch, head_output_dim)
        x = self.head(x.reshape(x.shape[0], -1))
        return x


class Model(pl.LightningModule):
    def __init__(
        self,
        net: nn.Module,
        boundary: float,
        learning_rate: float = 1e-3,
        weight_decay: float = 0.0,
        cosine_decay_steps: int = 0,
        cosine_decay_min: float = 0.01,
        log_stdout: bool = False,
    ):
        super().__init__()
        self.net = net

        self.boundary = boundary
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.cosine_decay_steps = cosine_decay_steps
        self.cosine_decay_min = cosine_decay_min
        self.log_stdout = log_stdout

    def configure_optimizers(
        self,
    ) -> tuple[list[torch.optim.Optimizer], list[LRSchedulerConfig]]:
        optimizer: torch.optim.Optimizer
        if self.weight_decay == 0:
            optimizer = torch.optim.Adam(self.parameters(), lr=self.learning_rate)
        else:
            optimizer = torch.optim.AdamW(
                self.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay
            )

        scheduler_config = cast(
            LRSchedulerConfig,
            {
                "scheduler": torch.optim.lr_scheduler.CosineAnnealingLR(
                    optimizer=optimizer,
                    T_max=self.cosine_decay_steps if self.cosine_decay_steps > 0 else 1,
                    eta_min=self.learning_rate
                    * (self.cosine_decay_min if self.cosine_decay_steps > 0 else 1.0),
                ),
                "interval": "step",
                "frequency": 1,
            },
        )

        return [optimizer], [scheduler_config]

    def _to_torch_features(
        self,
        features_np: dict[data.FeatureName, data.FeatureValue],
    ) -> dict[data.FeatureName, torch.Tensor]:
        features_torch: dict[data.FeatureName, torch.Tensor] = {}
        for feature_name, value_np in features_np.items():
            if value_np.dtype == np.float32:
                # shape: (batch, hist_len, 1)
                features_torch[feature_name] = torch.unsqueeze(
                    torch.from_numpy(features_np[feature_name]),
                    dim=2,
                ).to(self.device)
            elif value_np.dtype == np.int64:
                # shape: (batch, hist_len)
                features_torch[feature_name] = torch.from_numpy(
                    features_np[feature_name]
                ).to(self.device)
            else:
                raise ValueError(
                    f"Data type of {feature_name} is not supported: "
                    f"{value_np.dtype}"
                )

        return features_torch

    def _predict_logits(
        self,
        features: dict[data.FeatureName, torch.Tensor],
    ) -> torch.Tensor:
        return cast(torch.Tensor, self.net(features))

    def _predict_score(
        self, features: dict[data.FeatureName, torch.Tensor]
    ) -> torch.Tensor:
        logit = self._predict_logits(features)
        prob = torch.softmax(logit, dim=1)
        return prob[:, 0] * -self.boundary + prob[:, 2] * self.boundary

    def _calc_loss(
        self,
        logit: torch.Tensor,
        label: torch.Tensor,
        log_prefix: str,
    ) -> torch.Tensor:
        loss = F.cross_entropy(logit, label).mean()
        with torch.no_grad():
            prob = torch.softmax(logit, dim=1).mean(dim=0)

        metrics = {f"{log_prefix}/loss": loss}
        for i in range(len(prob)):
            metrics[f"{log_prefix}/prob_{i}"] = prob[i]

        self.log_dict(
            metrics,
            # Accumulate metrics on epoch level
            on_step=False,
            on_epoch=True,
            batch_size=logit.shape[0],
        )
        return loss

    def training_step(
        self,
        batch: tuple[
            dict[data.FeatureName, data.FeatureValue],
            NDArray[np.float32],
        ],
        *args: Any,
        **kwargs: Any,
    ) -> torch.Tensor:
        features_np, label_np = batch
        features_torch = self._to_torch_features(features_np)
        label_torch = torch.from_numpy(label_np).to(self.device)
        return self._calc_loss(
            self._predict_logits(features_torch),
            label_torch,
            log_prefix="train",
        )

    def validation_step(
        self,
        batch: tuple[
            dict[data.FeatureName, data.FeatureValue],
            NDArray[np.float32],
        ],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        features_np, label_np = batch
        features_torch = self._to_torch_features(features_np)
        label_torch = torch.from_numpy(label_np).to(self.device)
        # ロギング目的
        _ = self._calc_loss(
            self._predict_logits(features_torch),
            label_torch,
            log_prefix="valid",
        )

    def predict_step(
        self,
        batch: tuple[
            dict[data.FeatureName, data.FeatureValue],
            None,
        ],
        *args: Any,
        **kwargs: Any,
    ) -> torch.Tensor:
        features_np, _ = batch
        features_torch = self._to_torch_features(features_np)
        return self._predict_score(features_torch)

    def on_train_epoch_end(self) -> None:
        if self.log_stdout:
            metrics = {k: float(v) for k, v in self.trainer.callback_metrics.items()}
            print(f"Training metrics: {metrics}")

    def on_validation_epoch_end(self) -> None:
        if self.log_stdout:
            metrics = {k: float(v) for k, v in self.trainer.callback_metrics.items()}
            print(f"Validation metrics: {metrics}")
